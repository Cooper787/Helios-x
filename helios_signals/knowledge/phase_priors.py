"""Phase-transition base rates: how often a trial at each phase succeeds.

This is the Tier 1 layer -- the closest thing to a quantified answer to "how
does each type of drug behave". It is the difference between a system that
knows a Phase 3 oncology readout is roughly a coin flip and one that treats
every catalyst as equally likely to be good news.

## Why every prior here is marked unverified

The canonical free source is the BIO / Informa / QLS report *Clinical
Development Success Rates*. The values below are approximate figures recalled
from that literature, **not** read from the report in this session. They are
therefore flagged verified=False, and an unverified prior is annotation-only:
it can appear on a signal as context, and it can never veto, size, or rank.

That restriction is deliberate and it is the whole point of this module.
Precise-looking base rates that nobody checked are exactly the failure mode
this project has already been burned by -- a 1,278% backtest presented as fact,
a conviction score whose weights were guesses in LaTeX. A number that looks
like evidence must either be evidence or be unable to affect a decision.

## To promote these to usable

Download the current BIO/QLS report, replace the values with the figures as
published, set verified=True, and record the edition and page in source. At
that point PhasePriors.is_usable becomes true and the priors may inform
sizing. Until then they only ever add a sentence to a Telegram message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class Prior:
    """One base rate, with its own provenance and verification state."""

    label: str
    probability: float
    source: str
    verified: bool = False
    n: Optional[int] = None

    def describe(self) -> str:
        pct = f"{self.probability * 100:.0f}%"
        mark = "" if self.verified else " (UNVERIFIED)"
        sample = f", n={self.n}" if self.n else ""
        return f"{self.label}: {pct}{sample}{mark}"


_UNVERIFIED_SOURCE = (
    "Approximate, recalled from BIO/Informa/QLS 'Clinical Development Success "
    "Rates' literature. NOT read from the report. Must be replaced with "
    "published figures before use in any decision."
)

# Phase-transition success probabilities, all-indication.
PHASE_TRANSITION: Dict[str, Prior] = {
    "PHASE1": Prior("Phase 1 to Phase 2", 0.52, _UNVERIFIED_SOURCE),
    "PHASE2": Prior("Phase 2 to Phase 3", 0.29, _UNVERIFIED_SOURCE),
    "PHASE3": Prior("Phase 3 to filing", 0.58, _UNVERIFIED_SOURCE),
    "FILED": Prior("Filing to approval", 0.91, _UNVERIFIED_SOURCE),
}

# Therapeutic areas differ enough that an all-indication number is misleading:
# oncology is materially worse than the average and haematology materially
# better. These are the coarse buckets the design doc argues for -- anything
# finer would be overfitting a thin sample.
THERAPEUTIC_AREA_LOA: Dict[str, Prior] = {
    "oncology": Prior("Oncology, Phase 1 to approval", 0.05, _UNVERIFIED_SOURCE),
    "haematology": Prior("Haematology, Phase 1 to approval", 0.24, _UNVERIFIED_SOURCE),
    "infectious_disease": Prior("Infectious disease, Phase 1 to approval", 0.19, _UNVERIFIED_SOURCE),
    "cardiovascular": Prior("Cardiovascular, Phase 1 to approval", 0.25, _UNVERIFIED_SOURCE),
    "neurology": Prior("Neurology, Phase 1 to approval", 0.06, _UNVERIFIED_SOURCE),
    "all": Prior("All indications, Phase 1 to approval", 0.08, _UNVERIFIED_SOURCE),
}

# Keyword routing from a registry condition string to a coarse area. Crude on
# purpose: a mapping with a hundred rules invites the belief that the buckets
# are precise, and they are not.
_AREA_KEYWORDS = {
    "oncology": ("cancer", "carcinoma", "tumor", "tumour", "oncolog", "melanoma",
                 "sarcoma", "glioma", "myeloma", "neoplasm"),
    "haematology": ("leukemia", "leukaemia", "lymphoma", "anemia", "anaemia",
                    "hemophilia", "haemophilia", "thalassemia", "sickle"),
    "infectious_disease": ("infection", "viral", "hiv", "hepatitis", "influenza",
                           "tuberculosis", "covid", "bacterial", "sepsis"),
    "cardiovascular": ("cardiac", "heart", "hypertension", "atherosclerosis",
                       "arrhythmia", "cardiomyopathy", "stroke"),
    "neurology": ("alzheimer", "parkinson", "epilep", "multiple sclerosis", "als",
                  "neurodegener", "huntington", "migraine", "dementia"),
}


def classify_therapeutic_area(conditions) -> str:
    """Map registry condition strings to a coarse therapeutic area.

    Returns "all" when nothing matches, so the caller falls back to the
    all-indication prior rather than receiving a confident wrong bucket.
    """
    blob = " ".join(str(c).lower() for c in (conditions or []))
    if not blob:
        return "all"
    for area, keywords in _AREA_KEYWORDS.items():
        if any(kw in blob for kw in keywords):
            return area
    return "all"


@dataclass
class PhasePriors:
    """Lookup for phase and therapeutic-area base rates."""

    @property
    def is_usable(self) -> bool:
        """True only when every prior has been verified against the source.

        While false, priors may be shown to a human but must not influence
        sizing, ranking, or any veto.
        """
        return all(p.verified for p in PHASE_TRANSITION.values()) and all(
            p.verified for p in THERAPEUTIC_AREA_LOA.values()
        )

    def for_phase(self, phase_label: str) -> Optional[Prior]:
        return PHASE_TRANSITION.get((phase_label or "").upper())

    def for_conditions(self, conditions) -> Prior:
        return THERAPEUTIC_AREA_LOA[classify_therapeutic_area(conditions)]

    def annotate(self, phase_label: str, conditions) -> str:
        """One human-readable line of base-rate context for a Telegram signal."""
        parts = []
        if (phase := self.for_phase(phase_label)) is not None:
            parts.append(phase.describe())
        area = self.for_conditions(conditions)
        parts.append(area.describe())

        line = "Base rates - " + "; ".join(parts)
        if not self.is_usable:
            line += (
                ". These are unverified approximations shown for context only; "
                "they do not affect sizing or selection."
            )
        return line
