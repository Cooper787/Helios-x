"""Sector profiles: the seam that lets Helios cover other sectors later.

## Why this is small on purpose

The natural instinct on hearing "I want other sectors later" is to build a
plugin framework -- registries, entry points, abstract base classes. That would
be the wrong move here, and Argus is flagging it rather than doing it.

The reason: Helios has not yet produced a single verified signal. Generalising
an architecture before its first concrete case has been validated means
designing an abstraction against imagined requirements, and the usual result is
an abstraction that fits nothing well. The biotech case is the one with a real
edge behind it -- the catalyst calendar, the dilution dynamic, the binary-event
structure. That is where effort belongs.

So the seam is one dataclass. It changes nothing about how the engine runs; it
just names the thing that varies by sector, so that when a second sector
actually arrives the shape of the change is obvious rather than archaeological.

## What a sector profile actually is

Three things:

1. **A catalyst source** -- what dated event drives the trade. For biotech,
   trial completions. For earnings-driven equities it would be an earnings
   calendar. This is genuinely different per sector.
2. **Sector screens** -- the discriminators that separate a real catalyst from
   noise *in that sector*. Sponsor class and enrollment mean nothing outside
   biotech.
3. **Universe constraints** -- what the sector's tradeable set looks like.

Everything else -- timing, dilution, sizing, fail-closed behaviour, the ledger,
Telegram -- is sector-agnostic and already lives in the engine.

## Adding a sector later

Write a new SectorProfile, give it a catalyst source and its own screens,
select it by name. No engine change should be required. If one is, that is the
signal that this seam was drawn in the wrong place -- and it should be moved
then, with a real second case in hand, not guessed at now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .config import SignalConfig
from .models import Catalyst, ScreenResult
from .screens import (
    screen_intervention_type,
    screen_sponsor_class,
    screen_trial_quality,
)

# A sector screen takes a catalyst and config, and returns a pass/fail with a
# reason. Screens that need external data (market cap, cash runway) are applied
# by the engine after resolution, not here.
SectorScreen = Callable[[Catalyst, SignalConfig], ScreenResult]


@dataclass
class SectorProfile:
    """What varies between sectors. Everything else is shared."""

    name: str
    description: str
    screens: List[SectorScreen] = field(default_factory=list)
    knowledge_note: Optional[str] = None

    def apply(self, catalyst: Catalyst, config: SignalConfig) -> List[ScreenResult]:
        """Run every sector screen. Returns all results, passes and failures.

        Runs all of them rather than short-circuiting on the first failure,
        because a rejected candidate is more useful with every reason attached
        -- that is what makes the veto log diagnosable rather than just a count.
        """
        return [screen(catalyst, config) for screen in self.screens]

    def first_failure(self, results: List[ScreenResult]) -> Optional[ScreenResult]:
        return next((r for r in results if not r.passed), None)


BIOTECH = SectorProfile(
    name="biotech",
    description=(
        "Clinical-stage biotech and pharmaceutical companies traded around dated "
        "regulatory and trial catalysts. Entry in the pre-readout drift window, "
        "hard exit before the binary event."
    ),
    screens=[
        # Ordered by how much noise each removes. Sponsor class first by a wide
        # margin: clinicaltrials.gov is dominated by academic and government
        # trials that have no ticker attached to the outcome.
        screen_sponsor_class,
        screen_intervention_type,
        screen_trial_quality,
    ],
    knowledge_note=(
        "Phase-transition base rates are available but unverified, so they annotate "
        "signals and never influence selection or sizing."
    ),
)


PROFILES = {BIOTECH.name: BIOTECH}


def get_profile(name: str) -> SectorProfile:
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(
            f"Unknown sector profile {name!r}. Available: {sorted(PROFILES)}"
        ) from None
