"""Core data types for the Helios-X signal pipeline.

Every value that reaches a signal carries its provenance: which source produced
it and when. This is not decoration. The project's stated goal is to be
verifiably trustworthy rather than merely profitable-looking, and a number
whose origin cannot be traced cannot be audited.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    """Catalyst categories.

    PMA and CLEARANCE_510K are deliberately distinct. A PMA approval for a
    Class III device is a binary event comparable to a drug approval; a 510(k)
    clearance is a routine substantial-equivalence finding that usually moves
    nothing. Collapsing them into one "device" category would corrupt any base
    rate computed over it.
    """

    PHASE_3_COMPLETION = "phase_3_completion"
    PHASE_2_COMPLETION = "phase_2_completion"
    PDUFA = "pdufa"
    ADCOM = "adcom"
    PMA = "pma"
    CLEARANCE_510K = "clearance_510k"


class Tier(str, Enum):
    """Evidential weight of a knowledge claim.

    TIER_3 may never originate a signal. It exists for hypothesis generation
    only. See the knowledge-layer design in the project docs.
    """

    TIER_1_QUANTIFIED = "tier_1_quantified"
    TIER_2_MECHANISM = "tier_2_mechanism"
    TIER_3_LORE = "tier_3_lore"


class SponsorClass(str, Enum):
    """Who is running the trial.

    Only INDUSTRY trials are tradeable. An NIH- or university-sponsored trial
    has no listed sponsor whose stock can move on the result, and academic
    trials dominate clinicaltrials.gov by volume -- so without this filter the
    catalyst feed is mostly noise.
    """

    INDUSTRY = "INDUSTRY"
    NIH = "NIH"
    FED = "FED"
    OTHER_GOV = "OTHER_GOV"
    NETWORK = "NETWORK"
    INDIV = "INDIV"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class InterventionType(str, Enum):
    """What is being tested.

    A DRUG or BIOLOGICAL readout is a binary company-making event. A
    BEHAVIORAL or DIETARY_SUPPLEMENT trial is not, even at Phase 3, even from
    a listed sponsor.
    """

    DRUG = "DRUG"
    BIOLOGICAL = "BIOLOGICAL"
    DEVICE = "DEVICE"
    GENETIC = "GENETIC"
    RADIATION = "RADIATION"
    PROCEDURE = "PROCEDURE"
    COMBINATION = "COMBINATION_PRODUCT"
    DIAGNOSTIC = "DIAGNOSTIC_TEST"
    BEHAVIORAL = "BEHAVIORAL"
    DIETARY = "DIETARY_SUPPLEMENT"
    OTHER = "OTHER"

    @classmethod
    def tradeable(cls) -> set:
        """Types whose readout can plausibly re-rate a company."""
        return {cls.DRUG, cls.BIOLOGICAL, cls.GENETIC, cls.COMBINATION, cls.DEVICE}


@dataclass
class TrialDesign:
    """Design attributes that separate a real catalyst from a formality.

    A 30-patient open-label single-arm study labelled Phase 3 is not the same
    event as an 800-patient randomised double-blind trial, and treating them
    alike is how a catalyst feed fills with things that will never move a
    stock. All fields are optional because registry data is inconsistently
    completed -- absence is recorded, never guessed.
    """

    enrollment: Optional[int] = None
    enrollment_is_estimated: bool = True
    allocation: Optional[str] = None          # RANDOMIZED / NON_RANDOMIZED
    masking: Optional[str] = None             # NONE / SINGLE / DOUBLE / ...
    primary_purpose: Optional[str] = None     # TREATMENT / PREVENTION / ...

    @property
    def is_randomised(self) -> bool:
        return (self.allocation or "").upper() == "RANDOMIZED"

    @property
    def is_masked(self) -> bool:
        return (self.masking or "NONE").upper() not in ("", "NONE")


class Decision(str, Enum):
    BUY = "buy"
    EXIT = "exit"
    VETO = "veto"
    NO_ACTION = "no_action"


@dataclass(frozen=True)
class Provenance:
    """Where a fact came from."""

    source: str
    url: Optional[str] = None
    retrieved_at: str = field(default_factory=lambda: utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Catalyst:
    """A dated, forward-looking event for a single sponsor."""

    event_type: EventType
    event_date: date
    sponsor: str
    title: str
    external_id: str
    provenance: Provenance
    ticker: Optional[str] = None
    cik: Optional[str] = None
    intervention_names: List[str] = field(default_factory=list)
    intervention_types: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    date_is_estimated: bool = True
    sponsor_class: SponsorClass = SponsorClass.UNKNOWN
    design: TrialDesign = field(default_factory=TrialDesign)
    phase_label: str = ""

    def days_until(self, as_of: date) -> int:
        return (self.event_date - as_of).days

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["event_date"] = self.event_date.isoformat()
        d["sponsor_class"] = self.sponsor_class.value
        return d


@dataclass
class CashRunway:
    """Months of operating runway, derived from XBRL company facts.

    Dilution is the failure mode most likely to convert a correct thesis into a
    loss: a clinical-stage company with no revenue funds itself by selling
    shares, classically straight into good news. This is why runway is a hard
    veto rather than a scored input.
    """

    cik: str
    months: Optional[float]
    cash_usd: Optional[float]
    quarterly_burn_usd: Optional[float]
    provenance: Provenance
    note: str = ""

    @property
    def is_known(self) -> bool:
        return self.months is not None and math.isfinite(self.months)


@dataclass
class ScreenResult:
    """Outcome of a single screen. Screens veto; they do not score."""

    name: str
    passed: bool
    reason: str
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Signal:
    """An advisory recommendation. Helios never executes; Andrew does."""

    decision: Decision
    ticker: str
    catalyst: Catalyst
    reason: str
    generated_at: str = field(default_factory=lambda: utcnow().isoformat())
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    quantity: Optional[float] = None
    position_value: Optional[float] = None
    exit_by: Optional[date] = None
    screens: List[ScreenResult] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "ticker": self.ticker,
            "reason": self.reason,
            "generated_at": self.generated_at,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "quantity": self.quantity,
            "position_value": self.position_value,
            "exit_by": self.exit_by.isoformat() if self.exit_by else None,
            "catalyst": self.catalyst.to_dict(),
            "screens": [asdict(s) for s in self.screens],
            "caveats": self.caveats,
        }


@dataclass
class SourceReport:
    """Health of one data source for one run.

    This exists because of a specific lesson from this project's own history: a
    scheduled job failed roughly 195 consecutive times and nobody saw it,
    because the failure-reporting path had never itself been tested. A source
    that silently returns zero rows looks identical to a quiet market unless
    the run explicitly reports what each source produced.
    """

    name: str
    ok: bool
    records: int
    elapsed_ms: int
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunReport:
    """Everything one nightly run did. Serialised into the ledger."""

    run_id: str
    started_at: str
    finished_at: Optional[str] = None
    dry_run: bool = True
    sources: List[SourceReport] = field(default_factory=list)
    catalysts_found: int = 0
    catalysts_in_window: int = 0
    signals: List[Signal] = field(default_factory=list)
    vetoes: List[Dict[str, Any]] = field(default_factory=list)
    fatal_error: Optional[str] = None

    @property
    def healthy(self) -> bool:
        """Fail closed: if any source failed, the run is not trustworthy."""
        return self.fatal_error is None and all(s.ok for s in self.sources)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
            "healthy": self.healthy,
            "sources": [s.to_dict() for s in self.sources],
            "catalysts_found": self.catalysts_found,
            "catalysts_in_window": self.catalysts_in_window,
            "signals": [s.to_dict() for s in self.signals],
            "vetoes": self.vetoes,
            "fatal_error": self.fatal_error,
        }
