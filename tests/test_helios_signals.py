"""Tests for the Helios-X signal pipeline.

No network. Sources are driven by fixtures shaped like the real API responses,
so schema assumptions are at least explicit and a future change to them breaks
a test rather than a 09:00 UTC production run.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from helios_signals.config import AccountConfig, SignalConfig
from helios_signals.engine import SignalEngine
from helios_signals.ledger import RunLedger
from helios_signals.models import (
    CashRunway,
    Catalyst,
    Decision,
    EventType,
    Provenance,
    RunReport,
    SourceReport,
)
from helios_signals.notify.telegram import (
    TelegramNotifier,
    render_run_summary,
    render_signal,
)
from helios_signals.screens.catalyst_window import screen_catalyst_window
from helios_signals.screens.dilution import screen_dilution
from helios_signals.sources.base import HttpJsonClient, SourceError, dig
from helios_signals.sources.clinicaltrials import ClinicalTrialsSource, parse_ct_date
from helios_signals.sources.sec import (
    CompanyFactsSource,
    TickerResolver,
    normalise_company_name,
)

TODAY = date(2026, 8, 17)


def make_study(
    nct,
    sponsor,
    pcd,
    date_type="ESTIMATED",
    phase="PHASE3",
    sponsor_class="INDUSTRY",
    intervention_type="DRUG",
    enrollment=400,
    allocation="RANDOMIZED",
    masking="DOUBLE",
):
    """A realistic industry-sponsored registrational trial by default.

    Defaults deliberately clear every sector screen, so a test that wants to
    exercise one screen overrides just that field and the failure is
    unambiguous.
    """
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct, "briefTitle": f"Study {nct}"},
            "statusModule": {
                "overallStatus": "RECRUITING",
                "primaryCompletionDateStruct": {"date": pcd, "type": date_type},
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": sponsor, "class": sponsor_class}
            },
            "armsInterventionsModule": {
                "interventions": [{"type": intervention_type, "name": "ABC-123"}]
            },
            "conditionsModule": {"conditions": ["Non-Small Cell Lung Cancer"]},
            "designModule": {
                "phases": [phase],
                "enrollmentInfo": {"count": enrollment, "type": "ESTIMATED"},
                "designInfo": {
                    "allocation": allocation,
                    "maskingInfo": {"masking": masking},
                    "primaryPurpose": "TREATMENT",
                },
            },
        }
    }


class FakeClient:
    """Stands in for HttpJsonClient; returns canned payloads by URL substring."""

    def __init__(self, routes, fail_on=None):
        self.routes = routes
        self.fail_on = fail_on or []
        self.calls = []

    def get_json(self, url, headers=None):
        self.calls.append(url)
        for frag in self.fail_on:
            if frag in url:
                raise SourceError(f"simulated failure for {frag}")
        for frag, payload in self.routes.items():
            if frag in url:
                return payload
        raise SourceError(f"no route for {url}")


# --------------------------------------------------------------- http client


class TestHttpJsonClient:
    def test_requires_contactable_user_agent(self):
        """SEC fair-access policy requires an identifiable operator."""
        with pytest.raises(ValueError):
            HttpJsonClient(user_agent="bot")

    def test_accepts_user_agent_with_email(self):
        assert HttpJsonClient(user_agent="Helios/1 (a@b.com)").user_agent

    def test_dig_survives_missing_keys(self):
        assert dig({"a": {"b": 1}}, "a", "b") == 1
        assert dig({"a": {}}, "a", "b", default="x") == "x"
        assert dig({}, "a", "b", "c") is None
        assert dig(None, "a") is None

    def test_dig_treats_none_as_default(self):
        assert dig({"a": None}, "a", default=5) == 5


# ------------------------------------------------------------ clinicaltrials


class TestDateParsing:
    def test_full_date(self):
        assert parse_ct_date("2026-11-30") == date(2026, 11, 30)

    def test_month_only_becomes_month_end(self):
        """Conservative: the later date keeps us out of the position longer."""
        assert parse_ct_date("2026-02") == date(2026, 2, 28)
        assert parse_ct_date("2024-02") == date(2024, 2, 29)  # leap year
        assert parse_ct_date("2026-12") == date(2026, 12, 31)

    @pytest.mark.parametrize("bad", [None, "", "not-a-date", "2026/11/30", 20261130])
    def test_rejects_garbage(self, bad):
        assert parse_ct_date(bad) is None


class TestClinicalTrialsSource:
    def test_parses_studies(self):
        client = FakeClient({"clinicaltrials.gov": {
            "studies": [make_study("NCT001", "Acme Therapeutics Inc", "2026-10-15")]
        }})
        got = ClinicalTrialsSource(client).fetch(["PHASE3"])
        assert len(got) == 1
        c = got[0]
        assert c.external_id == "NCT001"
        assert c.sponsor == "Acme Therapeutics Inc"
        assert c.event_date == date(2026, 10, 15)
        assert c.event_type is EventType.PHASE_3_COMPLETION
        assert c.intervention_types == ["DRUG"]

    def test_skips_actual_dates(self):
        """An ACTUAL completion date has already happened; not a catalyst."""
        client = FakeClient({"clinicaltrials.gov": {
            "studies": [make_study("NCT002", "Acme Inc", "2026-01-01", date_type="ACTUAL")]
        }})
        assert ClinicalTrialsSource(client).fetch(["PHASE3"]) == []

    def test_skips_studies_missing_required_fields(self):
        client = FakeClient({"clinicaltrials.gov": {"studies": [
            {"protocolSection": {}},
            {"protocolSection": {"identificationModule": {"nctId": "NCT003"}}},
            make_study("NCT004", "", "2026-10-15"),
        ]}})
        assert ClinicalTrialsSource(client).fetch(["PHASE3"]) == []

    def test_raises_on_unexpected_shape(self):
        """Schema drift must fail loudly, not silently yield zero catalysts."""
        client = FakeClient({"clinicaltrials.gov": {"results": []}})
        with pytest.raises(SourceError, match="Unexpected response shape"):
            ClinicalTrialsSource(client).fetch(["PHASE3"])

    def test_follows_pagination(self):
        class Paged:
            def __init__(self):
                self.n = 0
            def get_json(self, url, headers=None):
                self.n += 1
                if self.n == 1:
                    return {"studies": [make_study("NCT1", "A Inc", "2026-10-15")],
                            "nextPageToken": "tok"}
                return {"studies": [make_study("NCT2", "B Inc", "2026-10-16")]}

        assert len(ClinicalTrialsSource(Paged()).fetch(["PHASE3"])) == 2


# ----------------------------------------------------------------------- SEC


class TestNameNormalisation:
    def test_strips_suffixes_and_punctuation(self):
        assert normalise_company_name("Acme Therapeutics, Inc.") == "acme"
        assert normalise_company_name("ACME PHARMACEUTICALS CORP") == "acme"

    def test_distinct_companies_stay_distinct(self):
        """The whole point: near-names must not collapse together."""
        assert normalise_company_name("Arcus Biosciences") != normalise_company_name(
            "Arcturus Therapeutics"
        )

    def test_empty_input(self):
        assert normalise_company_name("") == ""


class TestTickerResolver:
    @staticmethod
    def _payload():
        return {
            "0": {"cik_str": 1234567, "ticker": "ACME", "title": "Acme Therapeutics Inc"},
            "1": {"cik_str": 7654321, "ticker": "BETA", "title": "Beta Pharma Corp"},
        }

    def test_resolves_despite_suffix_differences(self):
        r = TickerResolver(FakeClient({"company_tickers": self._payload()}))
        r.load()
        assert r.resolve("Acme Therapeutics, Inc.") == ("ACME", "0001234567")
        assert r.resolve("ACME THERAPEUTICS") == ("ACME", "0001234567")

    def test_unknown_sponsor_returns_none(self):
        r = TickerResolver(FakeClient({"company_tickers": self._payload()}))
        r.load()
        assert r.resolve("Some Private Biotech GmbH") is None

    def test_ambiguous_names_are_dropped_not_guessed(self):
        """Two companies normalising alike must both be refused."""
        payload = {
            "0": {"cik_str": 1, "ticker": "AAA", "title": "Vertex Pharmaceuticals Inc"},
            "1": {"cik_str": 2, "ticker": "BBB", "title": "Vertex Pharma Corp"},
        }
        r = TickerResolver(FakeClient({"company_tickers": payload}))
        r.load()
        assert r.resolve("Vertex Pharmaceuticals") is None

    def test_resolve_before_load_raises(self):
        r = TickerResolver(FakeClient({}))
        with pytest.raises(SourceError, match="load"):
            r.resolve("Acme")


def facts_payload(cash=None, ocf=None, ocf_start="2026-01-01", ocf_end="2026-03-31"):
    gaap = {}
    if cash is not None:
        gaap["CashAndCashEquivalentsAtCarryingValue"] = {
            "units": {"USD": [{"end": "2026-03-31", "val": cash, "form": "10-Q"}]}
        }
    if ocf is not None:
        gaap["NetCashProvidedByUsedInOperatingActivities"] = {
            "units": {"USD": [
                {"start": ocf_start, "end": ocf_end, "val": ocf, "form": "10-Q"}
            ]}
        }
    return {"entityName": "Test", "facts": {"us-gaap": gaap}}


class TestCashRunway:
    def _fetch(self, payload):
        return CompanyFactsSource(FakeClient({"companyfacts": payload})).fetch("0001234567")

    def test_computes_runway_from_quarterly_burn(self):
        # $30M cash, $10M burned in the quarter -> 3 quarters -> 9 months
        r = self._fetch(facts_payload(cash=30_000_000, ocf=-10_000_000))
        assert r.months == pytest.approx(9.0)
        assert r.quarterly_burn_usd == pytest.approx(10_000_000)

    def test_annual_burn_is_divided_by_four(self):
        """Mixing 10-K and 10-Q spans would overstate runway 4x."""
        r = self._fetch(facts_payload(
            cash=40_000_000, ocf=-40_000_000,
            ocf_start="2025-01-01", ocf_end="2025-12-31",
        ))
        # $40M/yr -> $10M/qtr -> 4 quarters -> 12 months
        assert r.months == pytest.approx(12.0)

    def test_positive_cash_flow_is_infinite_runway(self):
        r = self._fetch(facts_payload(cash=10_000_000, ocf=5_000_000))
        assert r.months == float("inf")

    def test_missing_cash_yields_unknown(self):
        r = self._fetch(facts_payload(cash=None, ocf=-1_000_000))
        assert r.months is None and not r.is_known

    def test_missing_burn_yields_unknown(self):
        r = self._fetch(facts_payload(cash=10_000_000, ocf=None))
        assert r.months is None

    def test_source_failure_yields_unknown_not_exception(self):
        src = CompanyFactsSource(FakeClient({}, fail_on=["companyfacts"]))
        r = src.fetch("0001234567")
        assert r.months is None
        assert "facts unavailable" in r.note


# ------------------------------------------------------------------- screens


def make_catalyst(days_out, sponsor="Acme Therapeutics Inc", **kw):
    from helios_signals.models import SponsorClass, TrialDesign
    return Catalyst(
        event_type=EventType.PHASE_3_COMPLETION,
        event_date=TODAY + timedelta(days=days_out),
        sponsor=sponsor,
        title="A study",
        external_id="NCT001",
        provenance=Provenance(source="test"),
        sponsor_class=kw.get("sponsor_class", SponsorClass.INDUSTRY),
        intervention_types=kw.get("intervention_types", ["DRUG"]),
        conditions=kw.get("conditions", ["Non-Small Cell Lung Cancer"]),
        design=kw.get("design", TrialDesign(enrollment=400, allocation="RANDOMIZED",
                                            masking="DOUBLE")),
        phase_label=kw.get("phase_label", "PHASE3"),
    )


class TestCatalystWindow:
    cfg = SignalConfig()

    @pytest.mark.parametrize("days", [20, 35, 60])
    def test_inside_window_passes(self, days):
        assert screen_catalyst_window(make_catalyst(days), TODAY, self.cfg).passed

    @pytest.mark.parametrize("days", [0, 3, 5])
    def test_inside_exit_window_is_refused(self, days):
        r = screen_catalyst_window(make_catalyst(days), TODAY, self.cfg)
        assert not r.passed
        assert "binary" in r.reason.lower()

    def test_past_event_refused(self):
        r = screen_catalyst_window(make_catalyst(-1), TODAY, self.cfg)
        assert not r.passed and "passed" in r.reason.lower()

    def test_too_early_refused(self):
        assert not screen_catalyst_window(make_catalyst(120), TODAY, self.cfg).passed

    def test_between_exit_and_entry_min_refused(self):
        """T-10 is past the entry floor but not yet the exit window."""
        r = screen_catalyst_window(make_catalyst(10), TODAY, self.cfg)
        assert not r.passed
        assert "too close" in r.reason.lower()


class TestDilutionScreen:
    cfg = SignalConfig()

    def _runway(self, months, note=""):
        return CashRunway("0001", months, 1e7, 1e6, Provenance(source="test"), note)

    def test_ample_runway_passes(self):
        assert screen_dilution(self._runway(18.0), self.cfg).passed

    def test_short_runway_vetoed(self):
        r = screen_dilution(self._runway(3.0), self.cfg)
        assert not r.passed and "below" in r.reason.lower()

    def test_boundary_is_exclusive(self):
        assert screen_dilution(self._runway(6.0), self.cfg).passed
        assert not screen_dilution(self._runway(5.99), self.cfg).passed

    def test_unknown_runway_vetoes_by_default(self):
        """Unknown is not safe. Failing open would reward opacity."""
        r = screen_dilution(self._runway(None, "no cash tag"), self.cfg)
        assert not r.passed
        assert "unknown is not the same as safe" in r.reason

    def test_unknown_can_be_allowed_explicitly(self):
        cfg = SignalConfig()
        cfg.veto_on_unknown_runway = False
        assert screen_dilution(self._runway(None), cfg).passed

    def test_nan_runway_vetoed(self):
        assert not screen_dilution(self._runway(float("nan")), self.cfg).passed

    def test_infinite_runway_passes(self):
        assert screen_dilution(self._runway(float("inf")), self.cfg).passed


# -------------------------------------------------------------------- config


class TestConfigValidation:
    def test_rejects_oversized_risk(self):
        cfg = SignalConfig()
        cfg.risk_per_trade = 0.5
        with pytest.raises(ValueError, match="risk_per_trade"):
            cfg.validate()

    def test_entry_floor_must_clear_exit_window(self):
        """Otherwise a position could open inside its own exit window."""
        cfg = SignalConfig()
        cfg.entry_window_min_days = 3
        cfg.hard_exit_days_before = 5
        with pytest.raises(ValueError, match="entry_window_min_days"):
            cfg.validate()

    def test_long_only_cannot_be_disabled(self):
        acct = AccountConfig()
        acct.long_only = False
        with pytest.raises(ValueError, match="TFSA"):
            acct.validate()

    def test_defaults_are_valid(self):
        SignalConfig().validate()
        AccountConfig().validate()


# -------------------------------------------------------------------- engine


def build_engine(studies, tickers, facts, price=None, fail_on=None, **overrides):
    client = FakeClient(
        {"clinicaltrials.gov": {"studies": studies},
         "company_tickers": tickers,
         "companyfacts": facts},
        fail_on=fail_on,
    )
    cfg = SignalConfig()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return SignalEngine(
        catalysts_source=ClinicalTrialsSource(client),
        resolver=TickerResolver(client),
        facts=CompanyFactsSource(client),
        config=cfg,
        account=AccountConfig(capital=1000.0),
        price_lookup=(lambda t: price) if price is not None else None,
    )


TICKERS = {"0": {"cik_str": 1234567, "ticker": "ACME", "title": "Acme Therapeutics Inc"}}


class TestEngine:
    def test_healthy_run_produces_a_buy(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat())]
        eng = build_engine(studies, TICKERS, facts_payload(30_000_000, -1_000_000), price=20.0)
        rep = eng.run(as_of=TODAY)

        assert rep.healthy
        assert len(rep.signals) == 1
        sig = rep.signals[0]
        assert sig.decision is Decision.BUY
        assert sig.ticker == "ACME"
        # $1000 * 2% = $20 risk; stop 15% below $20 = $17 -> $3/share -> 6 shares
        assert sig.quantity == 6
        assert sig.stop_loss == pytest.approx(17.0)
        assert sig.exit_by == TODAY + timedelta(days=35)

    def test_source_failure_fails_closed(self):
        """A failed source must yield zero signals, not partial ones."""
        eng = build_engine([], TICKERS, facts_payload(1e7, -1e6),
                           price=20.0, fail_on=["clinicaltrials.gov"])
        rep = eng.run(as_of=TODAY)
        assert not rep.healthy
        assert rep.signals == []
        assert any(not s.ok for s in rep.sources)

    def test_dilution_veto_blocks_signal(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat())]
        # $3M cash against $3M/quarter burn -> 3 months
        eng = build_engine(studies, TICKERS, facts_payload(3_000_000, -3_000_000), price=20.0)
        rep = eng.run(as_of=TODAY)
        assert rep.signals == []
        assert rep.vetoes and rep.vetoes[0]["screen"] == "dilution"

    def test_unresolvable_sponsor_is_recorded_not_guessed(self):
        studies = [make_study("NCT1", "Some Private GmbH",
                              (TODAY + timedelta(days=40)).isoformat())]
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6), price=20.0)
        rep = eng.run(as_of=TODAY)
        assert rep.signals == []
        assert rep.vetoes[0]["screen"] == "ticker_resolution"

    def test_no_price_source_yields_no_action_not_a_buy(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat())]
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6), price=None)
        rep = eng.run(as_of=TODAY)
        assert rep.signals[0].decision is Decision.NO_ACTION

    def test_respects_max_signals(self):
        names = [f"Sponsor{i} Therapeutics Inc" for i in range(10)]
        studies = [
            make_study(f"NCT{i}", names[i], (TODAY + timedelta(days=30 + i)).isoformat())
            for i in range(10)
        ]
        tickers = {
            str(i): {"cik_str": 1000000 + i, "ticker": f"SP{i}", "title": names[i]}
            for i in range(10)
        }
        eng = build_engine(studies, tickers, facts_payload(1e8, -1e6),
                           price=20.0, max_signals_per_run=2)
        assert len(eng.run(as_of=TODAY).signals) == 2

    def test_one_position_per_ticker(self):
        """Three trials from one sponsor is still one company and one balance sheet."""
        studies = [
            make_study(f"NCT{i}", "Acme Therapeutics Inc",
                       (TODAY + timedelta(days=30 + i)).isoformat())
            for i in range(3)
        ]
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6),
                           price=20.0, max_signals_per_run=5)
        rep = eng.run(as_of=TODAY)
        assert len(rep.signals) == 1
        assert sum(v["screen"] == "one_position_per_ticker" for v in rep.vetoes) == 2

    def test_same_trial_from_two_phase_queries_is_deduped(self):
        """A PHASE2|PHASE3 trial appears in both queries; it is one catalyst."""
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat())]
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6), price=20.0)
        rep = eng.run(as_of=TODAY)
        # tracked_phases has two entries, so the fake source yields it twice
        assert rep.catalysts_found == 1

    def test_sub_share_budget_is_vetoed(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat())]
        # $20 risk budget, $450 stop distance -> 0 shares
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6), price=3000.0,
                           max_price=5000.0)
        rep = eng.run(as_of=TODAY)
        assert rep.signals == []
        assert any(v["screen"] == "sizing" for v in rep.vetoes)

    def test_invalid_config_is_fatal_not_silent(self):
        eng = build_engine([], TICKERS, facts_payload(1e8, -1e6), risk_per_trade=0.9)
        rep = eng.run(as_of=TODAY)
        assert rep.fatal_error and not rep.healthy

    def test_signals_carry_the_gap_risk_caveat(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat())]
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6), price=20.0)
        caveats = " ".join(eng.run(as_of=TODAY).signals[0].caveats).lower()
        assert "gap" in caveats and "stop" in caveats


# ------------------------------------------------------------------ telegram


class TestTelegram:
    def test_dry_run_without_token(self):
        n = TelegramNotifier(token="", chat_id="")
        assert not n.configured and n.mode == "dry-run"
        d = n.send("hello")
        assert d.ok and d.dry_run

    def test_partial_credentials_still_dry_run(self):
        assert not TelegramNotifier(token="abc", chat_id="").configured
        assert not TelegramNotifier(token="", chat_id="123").configured

    def test_summary_renders_when_degraded(self):
        rep = RunReport(run_id="r1", started_at="now")
        rep.sources.append(SourceReport("ct.gov", False, 0, 12, "boom"))
        text = render_run_summary(rep)
        assert "DEGRADED" in text and "No signals were issued" in text

    def test_html_is_escaped(self):
        """A sponsor name with angle brackets must not break the message."""
        rep = RunReport(run_id="<b>x</b>", started_at="now")
        assert "&lt;b&gt;" in render_run_summary(rep)

    def test_signal_renders_key_fields(self):
        from helios_signals.models import Signal
        sig = Signal(
            decision=Decision.BUY, ticker="ACME", catalyst=make_catalyst(40),
            reason="in window", entry_price=20.0, stop_loss=17.0,
            quantity=6, position_value=120.0,
            exit_by=TODAY + timedelta(days=35),
        )
        text = render_signal(sig)
        assert "BUY ACME" in text
        assert "$20.00" in text and "$17.00" in text
        assert "HARD EXIT BY" in text
        assert "Advisory only" in text

    def test_degraded_run_sends_summary_but_no_signals(self):
        from helios_signals.models import Signal
        rep = RunReport(run_id="r", started_at="now")
        rep.sources.append(SourceReport("x", False, 0, 1, "err"))
        rep.signals = [Signal(Decision.BUY, "ACME", make_catalyst(40), "r")]
        assert len(TelegramNotifier(token="", chat_id="").dispatch_run(rep)) == 1


# -------------------------------------------------------------------- ledger


class TestLedger:
    def test_append_and_read(self, tmp_path):
        led = RunLedger(tmp_path / "runs.jsonl")
        led.append(RunReport(run_id="r1", started_at="t"))
        led.append(RunReport(run_id="r2", started_at="t"))
        assert [r["run_id"] for r in led.read()] == ["r1", "r2"]

    def test_corrupt_line_does_not_hide_the_rest(self, tmp_path):
        p = tmp_path / "runs.jsonl"
        led = RunLedger(p)
        led.append(RunReport(run_id="r1", started_at="t"))
        with p.open("a") as fh:
            fh.write("{not json\n")
        led.append(RunReport(run_id="r2", started_at="t"))
        assert [r["run_id"] for r in led.read()] == ["r1", "r2"]

    def test_read_missing_file_is_empty(self, tmp_path):
        assert list(RunLedger(tmp_path / "nope.jsonl").read()) == []

    def test_latest_is_valid_json(self, tmp_path):
        led = RunLedger(tmp_path / "runs.jsonl")
        p = led.write_latest(RunReport(run_id="r1", started_at="t"), tmp_path / "latest.json")
        assert json.loads(p.read_text())["run_id"] == "r1"


# ------------------------------------------------------------ biotech screens


from helios_signals.knowledge import PhasePriors, classify_therapeutic_area  # noqa: E402
from helios_signals.models import SponsorClass, TrialDesign  # noqa: E402
from helios_signals.profiles import BIOTECH, get_profile  # noqa: E402
from helios_signals.screens.biotech import (  # noqa: E402
    screen_intervention_type,
    screen_materiality,
    screen_sponsor_class,
    screen_trial_quality,
)

CFG = SignalConfig()


class TestSponsorClassScreen:
    """The largest noise filter: the registry is mostly academic trials."""

    def test_industry_passes(self):
        assert screen_sponsor_class(make_catalyst(40), CFG).passed

    @pytest.mark.parametrize(
        "cls", [SponsorClass.NIH, SponsorClass.FED, SponsorClass.OTHER,
                SponsorClass.INDIV, SponsorClass.NETWORK]
    )
    def test_non_industry_vetoed(self, cls):
        r = screen_sponsor_class(make_catalyst(40, sponsor_class=cls), CFG)
        assert not r.passed
        assert "INDUSTRY" in r.reason

    def test_unknown_vetoes(self):
        """A missing class means a malformed record, not a shy industry sponsor."""
        r = screen_sponsor_class(make_catalyst(40, sponsor_class=SponsorClass.UNKNOWN), CFG)
        assert not r.passed
        assert "missing" in r.reason.lower()


class TestInterventionTypeScreen:
    @pytest.mark.parametrize("t", ["DRUG", "BIOLOGICAL", "GENETIC", "DEVICE"])
    def test_tradeable_types_pass(self, t):
        assert screen_intervention_type(make_catalyst(40, intervention_types=[t]), CFG).passed

    @pytest.mark.parametrize("t", ["BEHAVIORAL", "DIETARY_SUPPLEMENT", "PROCEDURE"])
    def test_non_tradeable_types_vetoed(self, t):
        """A real Phase 3 result, but not a binary corporate event."""
        assert not screen_intervention_type(
            make_catalyst(40, intervention_types=[t]), CFG
        ).passed

    def test_mixed_passes_if_any_tradeable(self):
        c = make_catalyst(40, intervention_types=["BEHAVIORAL", "DRUG"])
        assert screen_intervention_type(c, CFG).passed

    def test_missing_type_vetoed(self):
        assert not screen_intervention_type(make_catalyst(40, intervention_types=[]), CFG).passed


class TestTrialQualityScreen:
    def test_registrational_scale_passes(self):
        r = screen_trial_quality(make_catalyst(40), CFG)
        assert r.passed and "randomised, masked" in r.reason

    def test_undersized_trial_vetoed(self):
        """A 25-patient study labelled Phase 3 is not the event it claims."""
        c = make_catalyst(40, design=TrialDesign(enrollment=25))
        r = screen_trial_quality(c, CFG)
        assert not r.passed and "below" in r.reason

    def test_unknown_enrollment_vetoes(self):
        r = screen_trial_quality(make_catalyst(40, design=TrialDesign()), CFG)
        assert not r.passed and "not recorded" in r.reason

    def test_single_arm_annotates_but_does_not_veto(self):
        """Single-arm is legitimate in rare disease and oncology."""
        c = make_catalyst(40, design=TrialDesign(enrollment=300, allocation="NON_RANDOMIZED",
                                                 masking="NONE"))
        r = screen_trial_quality(c, CFG)
        assert r.passed
        assert "single-arm" in r.reason and "open-label" in r.reason

    def test_boundary_is_inclusive(self):
        assert screen_trial_quality(
            make_catalyst(40, design=TrialDesign(enrollment=100)), CFG).passed
        assert not screen_trial_quality(
            make_catalyst(40, design=TrialDesign(enrollment=99)), CFG).passed


class TestMaterialityScreen:
    def test_small_cap_passes(self):
        assert screen_materiality(make_catalyst(40), 400_000_000, CFG).passed

    def test_large_cap_vetoed(self):
        """One readout among forty programmes does not re-rate a large cap."""
        r = screen_materiality(make_catalyst(40), 90_000_000_000, CFG)
        assert not r.passed and "ceiling" in r.reason

    def test_unknown_cap_annotates_rather_than_vetoes(self):
        """Unlike other screens: no price source exists, so vetoing would
        silently reject everything and look like a quiet market."""
        r = screen_materiality(make_catalyst(40), None, CFG)
        assert r.passed
        assert "could not be assessed" in r.reason


# -------------------------------------------------------------- phase priors


class TestPhasePriors:
    def test_priors_are_unverified_and_therefore_unusable(self):
        """The guardrail: unchecked numbers must not be able to affect a decision."""
        assert PhasePriors().is_usable is False

    def test_every_prior_declares_itself_unverified(self):
        from helios_signals.knowledge.phase_priors import (
            PHASE_TRANSITION,
            THERAPEUTIC_AREA_LOA,
        )
        for prior in {**PHASE_TRANSITION, **THERAPEUTIC_AREA_LOA}.values():
            assert prior.verified is False
            assert "UNVERIFIED" in prior.describe()

    @pytest.mark.parametrize("condition,area", [
        ("Non-Small Cell Lung Cancer", "oncology"),
        ("Acute Myeloid Leukemia", "haematology"),
        ("Chronic Hepatitis B", "infectious_disease"),
        ("Alzheimer Disease", "neurology"),
        ("Heart Failure", "cardiovascular"),
    ])
    def test_classifies_therapeutic_area(self, condition, area):
        assert classify_therapeutic_area([condition]) == area

    def test_unmatched_falls_back_to_all_not_a_guess(self):
        assert classify_therapeutic_area(["Some Rare Idiopathic Condition"]) == "all"
        assert classify_therapeutic_area([]) == "all"

    def test_annotation_flags_its_own_unreliability(self):
        text = PhasePriors().annotate("PHASE3", ["Lung Cancer"])
        assert "UNVERIFIED" in text
        assert "do not affect sizing or selection" in text


# ------------------------------------------------------------------ profiles


class TestSectorProfile:
    def test_biotech_profile_is_registered(self):
        assert get_profile("biotech") is BIOTECH

    def test_unknown_profile_raises_with_available_list(self):
        with pytest.raises(ValueError, match="biotech"):
            get_profile("crypto")

    def test_apply_returns_every_result_not_just_the_first_failure(self):
        """A rejected candidate is more useful with all its reasons attached."""
        c = make_catalyst(40, sponsor_class=SponsorClass.NIH, intervention_types=["BEHAVIORAL"])
        results = BIOTECH.apply(c, CFG)
        assert len(results) == 3
        assert sum(not r.passed for r in results) == 2

    def test_first_failure_identifies_the_blocking_screen(self):
        c = make_catalyst(40, sponsor_class=SponsorClass.NIH)
        assert BIOTECH.first_failure(BIOTECH.apply(c, CFG)).name == "sponsor_class"

    def test_clean_catalyst_has_no_failure(self):
        assert BIOTECH.first_failure(BIOTECH.apply(make_catalyst(40), CFG)) is None


class TestEngineWithSectorScreens:
    def test_academic_trial_never_reaches_a_signal(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat(),
                              sponsor_class="NIH")]
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6), price=20.0)
        rep = eng.run(as_of=TODAY)
        assert rep.signals == []
        assert any(v["screen"] == "sponsor_class" for v in rep.vetoes)

    def test_undersized_trial_never_reaches_a_signal(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat(), enrollment=20)]
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6), price=20.0)
        rep = eng.run(as_of=TODAY)
        assert rep.signals == []
        assert any(v["screen"] == "trial_quality" for v in rep.vetoes)

    def test_sector_screens_run_before_network_calls(self):
        """Vetoing early saves the SEC round trip on the majority of candidates."""
        client = FakeClient(
            {"clinicaltrials.gov": {"studies": [
                make_study("NCT1", "Acme Therapeutics Inc",
                           (TODAY + timedelta(days=40)).isoformat(), sponsor_class="NIH")
            ]},
             "company_tickers": TICKERS,
             "companyfacts": facts_payload(1e8, -1e6)},
        )
        eng = SignalEngine(
            catalysts_source=ClinicalTrialsSource(client),
            resolver=TickerResolver(client),
            facts=CompanyFactsSource(client),
            config=SignalConfig(),
            account=AccountConfig(capital=1000.0),
            price_lookup=lambda t: 20.0,
        )
        eng.run(as_of=TODAY)
        assert not any("companyfacts" in c for c in client.calls)

    def test_large_cap_sponsor_vetoed_on_materiality(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat())]
        client = FakeClient({"clinicaltrials.gov": {"studies": studies},
                             "company_tickers": TICKERS,
                             "companyfacts": facts_payload(1e8, -1e6)})
        eng = SignalEngine(
            catalysts_source=ClinicalTrialsSource(client),
            resolver=TickerResolver(client),
            facts=CompanyFactsSource(client),
            config=SignalConfig(),
            account=AccountConfig(capital=1000.0),
            price_lookup=lambda t: 20.0,
            market_cap_lookup=lambda t: 90_000_000_000.0,
        )
        rep = eng.run(as_of=TODAY)
        assert rep.signals == []
        assert any(v["screen"] == "materiality" for v in rep.vetoes)

    def test_signal_carries_base_rate_and_materiality_caveats(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat())]
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6), price=20.0)
        caveats = " ".join(eng.run(as_of=TODAY).signals[0].caveats)
        assert "UNVERIFIED" in caveats
        assert "Market cap unknown" in caveats

    def test_signal_records_every_screen_it_passed(self):
        studies = [make_study("NCT1", "Acme Therapeutics Inc",
                              (TODAY + timedelta(days=40)).isoformat())]
        eng = build_engine(studies, TICKERS, facts_payload(1e8, -1e6), price=20.0)
        names = {s.name for s in eng.run(as_of=TODAY).signals[0].screens}
        assert names == {"catalyst_window", "sponsor_class", "intervention_type",
                         "trial_quality", "dilution", "materiality"}
