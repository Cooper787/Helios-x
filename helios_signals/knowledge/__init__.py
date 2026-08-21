"""Tier 1 knowledge: quantified, citable base rates.

Tiering is enforced structurally, not by convention. An unverified prior is
annotation-only and cannot influence any decision -- see phase_priors for why.
"""

from .phase_priors import PhasePriors, Prior, classify_therapeutic_area

__all__ = ["PhasePriors", "Prior", "classify_therapeutic_area"]
