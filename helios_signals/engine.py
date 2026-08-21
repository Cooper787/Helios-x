"""Orchestration: sources -> screens -> sizing -> signals.

Two properties matter more than any strategy detail here.

**Fail closed.** If any source errors, the run issues no signals at all. Partial
data produces a plausible-looking recommendation built on an incomplete view,
which is worse than silence because it is indistinguishable from a good one.

**Report everything.** Every source reports records and timing, every rejection
carries a reason. A source that silently returns zero rows must be visibly
different from a genuinely quiet night.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from .config import AccountConfig, SignalConfig
from .knowledge import PhasePriors
from .models import (
    Catalyst,
    Decision,
    RunReport,
    ScreenResult,
    Signal,
    SourceReport,
    utcnow,
)
from .profiles import BIOTECH, SectorProfile
from .screens import screen_catalyst_window, screen_dilution
from .screens.biotech import screen_materiality
from .sources.base import SourceError
from .sources.clinicaltrials import ClinicalTrialsSource
from .sources.sec import CompanyFactsSource, TickerResolver

logger = logging.getLogger(__name__)


class SignalEngine:
    def __init__(
        self,
        catalysts_source: ClinicalTrialsSource,
        resolver: TickerResolver,
        facts: CompanyFactsSource,
        config: SignalConfig,
        account: AccountConfig,
        price_lookup=None,
        profile: SectorProfile = BIOTECH,
        market_cap_lookup=None,
    ) -> None:
        self.catalysts_source = catalysts_source
        self.resolver = resolver
        self.facts = facts
        self.config = config
        self.account = account
        # price_lookup(ticker) -> float | None. Injected so the pipeline can be
        # exercised end-to-end before a price source exists, and so tests never
        # touch the network.
        self.price_lookup = price_lookup
        self.profile = profile
        self.priors = PhasePriors()
        # market_cap_lookup(ticker) -> float | None. Needs a price, so it is
        # unavailable until a price source is wired; materiality annotates
        # rather than vetoes while it returns None.
        self.market_cap_lookup = market_cap_lookup

    def run(self, as_of: Optional[date] = None, dry_run: bool = True) -> RunReport:
        as_of = as_of or date.today()
        report = RunReport(
            run_id=f"{as_of.isoformat()}-{uuid.uuid4().hex[:8]}",
            started_at=utcnow().isoformat(),
            dry_run=dry_run,
        )

        try:
            self.config.validate()
            self.account.validate()
        except ValueError as exc:
            report.fatal_error = f"Invalid configuration: {exc}"
            report.finished_at = utcnow().isoformat()
            return report

        catalysts = self._load_catalysts(report)
        if not report.healthy:
            report.finished_at = utcnow().isoformat()
            return report

        catalysts = self._dedupe(catalysts)
        report.catalysts_found = len(catalysts)

        if not self._load_resolver(report):
            report.finished_at = utcnow().isoformat()
            return report

        in_window = self._apply_timing(catalysts, as_of, report)
        report.catalysts_in_window = len(in_window)

        report.signals = self._build_signals(in_window, as_of, report)
        report.finished_at = utcnow().isoformat()
        return report

    # ---------------------------------------------------------------- sources

    def _load_catalysts(self, report: RunReport) -> List[Catalyst]:
        started = time.monotonic()
        try:
            catalysts = self.catalysts_source.fetch(self.config.tracked_phases)
        except SourceError as exc:
            report.sources.append(
                SourceReport(
                    self.catalysts_source.name, False, 0,
                    int((time.monotonic() - started) * 1000), str(exc),
                )
            )
            return []

        elapsed = int((time.monotonic() - started) * 1000)
        report.sources.append(
            SourceReport(self.catalysts_source.name, True, len(catalysts), elapsed)
        )
        if not catalysts:
            logger.warning(
                "%s returned zero catalysts. This is unusual and may indicate a "
                "schema change rather than a quiet calendar.",
                self.catalysts_source.name,
            )
        return catalysts

    def _load_resolver(self, report: RunReport) -> bool:
        started = time.monotonic()
        try:
            count = self.resolver.load()
        except SourceError as exc:
            report.sources.append(
                SourceReport(
                    self.resolver.name, False, 0,
                    int((time.monotonic() - started) * 1000), str(exc),
                )
            )
            return False
        report.sources.append(
            SourceReport(
                self.resolver.name, True, count, int((time.monotonic() - started) * 1000)
            )
        )
        return True

    @staticmethod
    def _dedupe(catalysts: List[Catalyst]) -> List[Catalyst]:
        """Collapse the same trial appearing more than once.

        Trials are frequently registered against multiple phases (PHASE2 and
        PHASE3 on one record), so querying per phase returns the same NCT ID
        twice. Without this, one trial produces two identical signals and the
        run looks twice as productive as it is.
        """
        seen: Dict[str, Catalyst] = {}
        for cat in catalysts:
            existing = seen.get(cat.external_id)
            if existing is None or cat.event_date < existing.event_date:
                seen[cat.external_id] = cat
        return list(seen.values())

    # ---------------------------------------------------------------- screens

    def _apply_timing(
        self, catalysts: List[Catalyst], as_of: date, report: RunReport
    ) -> List[Tuple[Catalyst, ScreenResult]]:
        kept: List[Tuple[Catalyst, ScreenResult]] = []
        for cat in catalysts:
            result = screen_catalyst_window(cat, as_of, self.config)
            if result.passed:
                kept.append((cat, result))
        # Soonest catalyst first: the exit deadline is nearest, so it is the
        # most time-sensitive to act on.
        kept.sort(key=lambda pair: pair[0].event_date)
        return kept

    def _build_signals(
        self,
        in_window: List[Tuple[Catalyst, ScreenResult]],
        as_of: date,
        report: RunReport,
    ) -> List[Signal]:
        signals: List[Signal] = []
        tickers_signalled: set[str] = set()
        runway_calls = 0
        runway_started = time.monotonic()

        for catalyst, timing in in_window:
            if len(signals) >= self.config.max_signals_per_run:
                break

            # Sector screens first: they are free (no network) and remove the
            # bulk of the candidates, so running them before ticker resolution
            # and the runway fetch saves the majority of API calls.
            sector_results = self.profile.apply(catalyst, self.config)
            sector_failure = self.profile.first_failure(sector_results)
            if sector_failure is not None:
                report.vetoes.append(
                    {
                        "sponsor": catalyst.sponsor,
                        "external_id": catalyst.external_id,
                        "screen": sector_failure.name,
                        "reason": sector_failure.reason,
                        "detail": sector_failure.detail,
                    }
                )
                continue

            resolved = self.resolver.resolve(catalyst.sponsor)
            if resolved is None:
                report.vetoes.append(
                    {
                        "sponsor": catalyst.sponsor,
                        "external_id": catalyst.external_id,
                        "screen": "ticker_resolution",
                        "reason": "Sponsor name did not resolve to a listed ticker "
                                  "(private, subsidiary, foreign, or renamed)",
                    }
                )
                continue

            ticker, cik = resolved
            catalyst.ticker, catalyst.cik = ticker, cik

            # One position per name. A sponsor with three trials in the window
            # is still one company, one balance sheet, and one bankruptcy. On a
            # small account, stacking correlated positions in a single
            # small-cap biotech is the fastest route to a concentrated loss.
            if ticker in tickers_signalled:
                report.vetoes.append(
                    {
                        "ticker": ticker,
                        "external_id": catalyst.external_id,
                        "screen": "one_position_per_ticker",
                        "reason": f"A signal for {ticker} was already issued this run "
                                  "from an earlier catalyst.",
                    }
                )
                continue

            runway = self.facts.fetch(cik)
            runway_calls += 1
            dilution = screen_dilution(runway, self.config)
            if not dilution.passed:
                report.vetoes.append(
                    {
                        "ticker": ticker,
                        "sponsor": catalyst.sponsor,
                        "external_id": catalyst.external_id,
                        "screen": dilution.name,
                        "reason": dilution.reason,
                        "detail": dilution.detail,
                    }
                )
                continue

            materiality = screen_materiality(
                catalyst, self._market_cap(ticker), self.config
            )
            if not materiality.passed:
                report.vetoes.append(
                    {
                        "ticker": ticker,
                        "external_id": catalyst.external_id,
                        "screen": materiality.name,
                        "reason": materiality.reason,
                        "detail": materiality.detail,
                    }
                )
                continue

            price = self._price(ticker)
            screens = [timing, *sector_results, dilution, materiality]

            if price is None:
                signals.append(
                    Signal(
                        decision=Decision.NO_ACTION,
                        ticker=ticker,
                        catalyst=catalyst,
                        reason=(
                            "Passed timing and dilution screens, but no price source is "
                            "wired up, so position size cannot be computed. Review manually."
                        ),
                        screens=screens,
                        exit_by=catalyst.event_date
                        - timedelta(days=self.config.hard_exit_days_before),
                        caveats=self._caveats(catalyst),
                    )
                )
                tickers_signalled.add(ticker)
                continue

            if not (self.config.min_price <= price <= self.config.max_price):
                report.vetoes.append(
                    {
                        "ticker": ticker,
                        "screen": "price_band",
                        "reason": f"Price ${price:,.2f} outside "
                                  f"${self.config.min_price:g}-${self.config.max_price:g}",
                    }
                )
                continue

            qty, value, stop = self._size(price)
            if qty < 1:
                report.vetoes.append(
                    {
                        "ticker": ticker,
                        "screen": "sizing",
                        "reason": f"Risk budget affords {qty:.2f} shares at ${price:,.2f}; "
                                  "below one whole share.",
                    }
                )
                continue

            signals.append(
                Signal(
                    decision=Decision.BUY,
                    ticker=ticker,
                    catalyst=catalyst,
                    reason=(
                        f"{timing.reason}; {dilution.reason.lower()}"
                    ),
                    entry_price=price,
                    stop_loss=stop,
                    quantity=qty,
                    position_value=value,
                    exit_by=catalyst.event_date
                    - timedelta(days=self.config.hard_exit_days_before),
                    screens=screens,
                    caveats=self._caveats(catalyst),
                )
            )
            tickers_signalled.add(ticker)

        if runway_calls:
            report.sources.append(
                SourceReport(
                    self.facts.name, True, runway_calls,
                    int((time.monotonic() - runway_started) * 1000),
                )
            )
        return signals

    # ----------------------------------------------------------------- sizing

    def _size(self, price: float) -> Tuple[float, float, float]:
        """Risk-based sizing: risk_per_trade of capital between entry and stop.

        Sizing is by *risk*, not by position value. Position value follows from
        the stop distance, which is the quantity actually being controlled.
        """
        stop = round(price * (1.0 - self.config.stop_loss_pct), 2)
        risk_per_share = price - stop
        if risk_per_share <= 0:
            return 0.0, 0.0, stop
        budget = self.account.capital * self.config.risk_per_trade
        qty = float(int(budget / risk_per_share))
        return qty, round(qty * price, 2), stop

    def _market_cap(self, ticker: str) -> Optional[float]:
        if self.market_cap_lookup is None:
            return None
        try:
            return self.market_cap_lookup(ticker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Market cap lookup failed for %s: %s", ticker, exc)
            return None

    def _price(self, ticker: str) -> Optional[float]:
        if self.price_lookup is None:
            return None
        try:
            return self.price_lookup(ticker)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Price lookup failed for %s: %s", ticker, exc)
            return None

    def _caveats(self, catalyst: Catalyst) -> List[str]:
        out = [
            "Primary completion date is when data collection ends, not when results "
            "are announced. The real catalyst may land weeks later.",
            "Exit before the readout. A failed trial gaps 40-70% pre-market and a stop "
            "order will not protect you.",
        ]
        if catalyst.date_is_estimated:
            out.append("Event date is the sponsor's estimate and can move without notice.")
        if self.market_cap_lookup is None:
            out.append(
                "Market cap unknown, so materiality was not checked. Confirm this "
                "readout is large relative to the company before acting."
            )
        out.append(self.priors.annotate(catalyst.phase_label, catalyst.conditions))
        return out
