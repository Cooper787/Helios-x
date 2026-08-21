"""Screens veto candidates. They never score, rank, or boost.

A scoring system with hand-chosen weights looks quantitative and is not; it
launders guesses into apparent rigour. Until an event-outcome dataset exists to
fit weights against, every filter here is a binary gate with a stated reason,
so a rejection is always explainable in one sentence.

Generic screens (timing, dilution) apply to any sector. The biotech module
holds the sector-specific ones.
"""

from .biotech import (
    screen_intervention_type,
    screen_materiality,
    screen_sponsor_class,
    screen_trial_quality,
)
from .catalyst_window import screen_catalyst_window
from .dilution import screen_dilution

__all__ = [
    "screen_catalyst_window",
    "screen_dilution",
    "screen_sponsor_class",
    "screen_intervention_type",
    "screen_trial_quality",
    "screen_materiality",
]
