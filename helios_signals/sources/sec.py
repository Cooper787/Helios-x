"""SEC EDGAR sources: sponsor-to-ticker resolution and XBRL cash runway.

Two jobs:

1. **Linkage.** Map a clinical-trial sponsor name to a traded ticker. This is
   the hard part of the whole design and the number that governs everything
   downstream is the fraction of catalysts that resolve. A conservative
   matcher that resolves 60% honestly beats a fuzzy one that resolves 90% with
   silent mismatches -- a wrong ticker produces a confident recommendation to
   buy the wrong company.

2. **Cash runway.** Derived from XBRL company facts and used as a hard veto.

EDGAR never deletes filings, including those of companies that later went
bankrupt or delisted. That makes the event and linkage sides of this pipeline
survivorship-bias-free at zero cost -- unlike price data, where the bias is
unavoidable without paying.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..models import CashRunway, Provenance
from .base import HttpJsonClient, SourceError

logger = logging.getLogger(__name__)

TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Corporate suffixes and filler stripped before matching. Sponsor names in
# ClinicalTrials.gov and company names in EDGAR are entered by different people
# for different purposes and rarely agree on punctuation or suffix.
_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
    "limited", "llc", "lp", "plc", "sa", "nv", "ag", "gmbh", "as", "ab",
    "holdings", "holding", "group", "the", "pharmaceuticals", "pharmaceutical",
    "pharma", "therapeutics", "biosciences", "bioscience", "biotech",
    "biopharma", "biopharmaceuticals", "laboratories", "labs", "sciences",
    "science", "medical", "health", "healthcare", "technologies", "technology",
}

_CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "CashAndDueFromBanks",
]
_BURN_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]


def normalise_company_name(name: str) -> str:
    """Reduce a company name to comparable tokens."""
    if not name:
        return ""
    lowered = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    tokens = [t for t in lowered.split() if t and t not in _SUFFIXES]
    return " ".join(tokens)


class TickerResolver:
    """Resolves sponsor names to (ticker, CIK).

    Matching is exact-on-normalised-name only. Fuzzy matching is deliberately
    omitted: "Arcus Biosciences" and "Arcturus Therapeutics" are different
    companies, and a near-match that silently picks the wrong one produces a
    buy recommendation for a company with no catalyst at all. An unresolved
    catalyst is dropped and counted; a mis-resolved one becomes a bad trade.
    """

    name = "sec.company_tickers"

    def __init__(self, client: HttpJsonClient) -> None:
        self.client = client
        self._by_name: Dict[str, Tuple[str, int]] = {}
        self._ambiguous: set[str] = set()
        self._loaded = False

    def load(self) -> int:
        payload = self.client.get_json(TICKER_URL)
        if not isinstance(payload, dict):
            raise SourceError(f"Unexpected shape from {TICKER_URL}")

        for entry in payload.values():
            if not isinstance(entry, dict):
                continue
            ticker = entry.get("ticker")
            cik = entry.get("cik_str")
            title = entry.get("title")
            if not (ticker and cik and title):
                continue
            key = normalise_company_name(str(title))
            if not key:
                continue
            if key in self._by_name and self._by_name[key] != (str(ticker), int(cik)):
                # Two distinct companies normalise to the same key. Refuse
                # both rather than guessing.
                self._ambiguous.add(key)
                continue
            self._by_name[key] = (str(ticker), int(cik))

        for key in self._ambiguous:
            self._by_name.pop(key, None)

        self._loaded = True
        logger.info(
            "%s: %d names indexed, %d dropped as ambiguous",
            self.name,
            len(self._by_name),
            len(self._ambiguous),
        )
        return len(self._by_name)

    def resolve(self, sponsor: str) -> Optional[Tuple[str, str]]:
        """Return (ticker, zero-padded CIK) or None."""
        if not self._loaded:
            raise SourceError("TickerResolver.load() must be called before resolve()")
        key = normalise_company_name(sponsor)
        if not key:
            return None
        hit = self._by_name.get(key)
        if hit is None:
            return None
        ticker, cik = hit
        return ticker, f"{cik:010d}"


class CompanyFactsSource:
    """Computes cash runway from XBRL company facts.

        runway_months = (cash on hand / quarterly operating burn) * 3

    Returns a CashRunway with months=None when it cannot be computed. The
    caller must treat unknown as a veto, not as a pass -- a company whose
    filings cannot be parsed is not thereby safe.
    """

    name = "sec.companyfacts"

    def __init__(self, client: HttpJsonClient) -> None:
        self.client = client

    def fetch(self, cik: str) -> CashRunway:
        cik_int = int(cik)
        url = FACTS_URL.format(cik=cik_int)
        prov = Provenance(source=self.name, url=url)

        try:
            payload = self.client.get_json(url)
        except SourceError as exc:
            return CashRunway(
                cik=cik, months=None, cash_usd=None, quarterly_burn_usd=None,
                provenance=prov, note=f"facts unavailable: {exc}",
            )

        gaap = (payload.get("facts") or {}).get("us-gaap") or {}
        if not gaap:
            return CashRunway(
                cik=cik, months=None, cash_usd=None, quarterly_burn_usd=None,
                provenance=prov, note="no us-gaap facts present",
            )

        cash = self._latest_instant(gaap, _CASH_TAGS)
        burn = self._quarterly_burn(gaap)

        if cash is None:
            return CashRunway(
                cik=cik, months=None, cash_usd=None, quarterly_burn_usd=burn,
                provenance=prov, note="no cash tag found",
            )
        if burn is None:
            return CashRunway(
                cik=cik, months=None, cash_usd=cash, quarterly_burn_usd=None,
                provenance=prov, note="no operating cash flow tag found",
            )
        if burn <= 0:
            # Operating cash flow positive: the company funds itself and the
            # dilution thesis does not apply. Not infinite runway as a claim
            # about the future, just "not burning right now".
            return CashRunway(
                cik=cik, months=float("inf"), cash_usd=cash, quarterly_burn_usd=burn,
                provenance=prov, note="operating cash flow non-negative",
            )

        months = (cash / burn) * 3.0
        return CashRunway(
            cik=cik, months=months, cash_usd=cash, quarterly_burn_usd=burn, provenance=prov,
        )

    @staticmethod
    def _usd_facts(gaap: Dict[str, Any], tag: str) -> List[Dict[str, Any]]:
        units = ((gaap.get(tag) or {}).get("units") or {})
        facts = units.get("USD") or []
        return [f for f in facts if isinstance(f, dict) and isinstance(f.get("val"), (int, float))]

    def _latest_instant(self, gaap: Dict[str, Any], tags: List[str]) -> Optional[float]:
        best_date, best_val = None, None
        for tag in tags:
            for fact in self._usd_facts(gaap, tag):
                end = fact.get("end")
                if not isinstance(end, str):
                    continue
                try:
                    parsed = datetime.strptime(end, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if best_date is None or parsed > best_date:
                    best_date, best_val = parsed, float(fact["val"])
            if best_val is not None:
                break  # prefer the earlier (more specific) tag
        return best_val

    def _quarterly_burn(self, gaap: Dict[str, Any]) -> Optional[float]:
        """Most recent quarterly operating cash outflow, as a positive number.

        Operating cash flow is a duration fact, so a 10-K value covers a year
        and a 10-Q value covers a quarter. Mixing them silently would overstate
        runway by 4x -- exactly the direction that lets a dilution risk through
        the veto. Annual figures are therefore divided by four.
        """
        best_end, best_val = None, None

        for tag in _BURN_TAGS:
            for fact in self._usd_facts(gaap, tag):
                start, end = fact.get("start"), fact.get("end")
                if not (isinstance(start, str) and isinstance(end, str)):
                    continue
                try:
                    s = datetime.strptime(start, "%Y-%m-%d").date()
                    e = datetime.strptime(end, "%Y-%m-%d").date()
                except ValueError:
                    continue

                span_days = (e - s).days
                if span_days <= 0:
                    continue

                val = float(fact["val"])
                if 60 <= span_days <= 130:
                    quarterly = val
                elif 300 <= span_days <= 400:
                    quarterly = val / 4.0
                else:
                    continue  # half-year or other odd spans: skip rather than guess

                if best_end is None or e > best_end:
                    best_end, best_val = e, quarterly

            if best_val is not None:
                break

        if best_val is None:
            return None
        # XBRL reports an operating outflow as negative. Flip the sign so that
        # a burning company yields a positive burn, and a cash-generative one
        # yields a non-positive burn (handled as "not diluting" by the caller).
        return -best_val
