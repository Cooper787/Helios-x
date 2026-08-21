"""Biotech-specific screens.

These are what make the pipeline a *biotech* system rather than a generic
catalyst scanner. Each is a hard veto with a stated reason, and each exists
because without it the catalyst feed fills with events that cannot move a
stock.

The ordering below is roughly by how much noise each removes. Sponsor class
removes the most by a wide margin -- clinicaltrials.gov is dominated by
academic and government trials, none of which have a listed sponsor whose
shares can re-rate on the result.
"""

from __future__ import annotations

from typing import Optional

from ..config import SignalConfig
from ..models import Catalyst, InterventionType, ScreenResult, SponsorClass


def screen_sponsor_class(catalyst: Catalyst, config: SignalConfig) -> ScreenResult:
    """Only industry-sponsored trials are tradeable.

    An NIH- or university-run Phase 3 has no ticker attached to its outcome.
    These make up the large majority of the registry, so this screen is the
    single biggest noise filter in the pipeline.

    UNKNOWN vetoes. The registry field is well populated; a missing value more
    often means a malformed record than an industry sponsor being coy.
    """
    detail = {"sponsor_class": catalyst.sponsor_class.value, "sponsor": catalyst.sponsor}

    if catalyst.sponsor_class is SponsorClass.INDUSTRY:
        return ScreenResult("sponsor_class", True, "Industry-sponsored", detail)

    if catalyst.sponsor_class is SponsorClass.UNKNOWN:
        return ScreenResult(
            "sponsor_class",
            False,
            "Sponsor class missing from the registry record; vetoing rather than assuming industry",
            detail,
        )

    return ScreenResult(
        "sponsor_class",
        False,
        f"Sponsor class is {catalyst.sponsor_class.value}, not INDUSTRY. "
        "Academic and government trials have no listed sponsor to re-rate.",
        detail,
    )


def screen_intervention_type(catalyst: Catalyst, config: SignalConfig) -> ScreenResult:
    """The thing being tested must be capable of re-rating a company.

    A Phase 3 readout on a behavioural intervention or a dietary supplement is
    a real trial and a real result, but it is not a binary corporate event. A
    drug, biologic, gene therapy, or Class III device is.
    """
    seen = set()
    for raw in catalyst.intervention_types:
        try:
            seen.add(InterventionType(raw.upper()))
        except ValueError:
            continue

    tradeable = seen & InterventionType.tradeable()
    detail = {
        "intervention_types": sorted(catalyst.intervention_types),
        "tradeable_types": sorted(t.value for t in tradeable),
    }

    if not catalyst.intervention_types:
        return ScreenResult(
            "intervention_type",
            False,
            "No intervention type recorded; cannot confirm this is a drug or device trial",
            detail,
        )

    if not tradeable:
        return ScreenResult(
            "intervention_type",
            False,
            f"No tradeable intervention type. Found {sorted(seen and {t.value for t in seen}) or catalyst.intervention_types}; "
            "a behavioural or dietary trial is not a binary corporate event.",
            detail,
        )

    return ScreenResult(
        "intervention_type",
        True,
        f"Tradeable intervention: {', '.join(sorted(t.value for t in tradeable))}",
        detail,
    )


def screen_trial_quality(catalyst: Catalyst, config: SignalConfig) -> ScreenResult:
    """A registrational-scale trial, not a formality.

    A 25-patient open-label single-arm study carrying a "Phase 3" label is not
    the same event as a randomised, masked, several-hundred-patient trial, and
    only the second reliably produces the kind of readout that moves a stock.

    Enrollment is the primary gate because it is the field most consistently
    populated. Randomisation and masking are recorded but only *annotate* --
    single-arm designs are legitimate in rare disease and oncology, so vetoing
    on them would systematically exclude a whole therapeutic area.
    """
    design = catalyst.design
    detail = {
        "enrollment": design.enrollment,
        "enrollment_is_estimated": design.enrollment_is_estimated,
        "allocation": design.allocation,
        "masking": design.masking,
        "primary_purpose": design.primary_purpose,
        "min_enrollment": config.min_enrollment,
    }

    if design.enrollment is None:
        if config.veto_on_unknown_enrollment:
            return ScreenResult(
                "trial_quality",
                False,
                "Enrollment not recorded; vetoing rather than assuming registrational scale",
                detail,
            )
        return ScreenResult(
            "trial_quality", True, "Enrollment unknown, veto disabled by config", detail
        )

    if design.enrollment < config.min_enrollment:
        return ScreenResult(
            "trial_quality",
            False,
            f"Enrollment {design.enrollment} is below the {config.min_enrollment}-patient "
            "floor for a registrational-scale readout.",
            detail,
        )

    notes = []
    if not design.is_randomised:
        notes.append("single-arm or non-randomised")
    if not design.is_masked:
        notes.append("open-label")
    suffix = f" ({'; '.join(notes)})" if notes else " (randomised, masked)"

    return ScreenResult(
        "trial_quality",
        True,
        f"Enrollment {design.enrollment} clears the {config.min_enrollment} floor{suffix}",
        detail,
    )


def screen_materiality(
    catalyst: Catalyst, market_cap_usd: Optional[float], config: SignalConfig
) -> ScreenResult:
    """The catalyst must matter to the company carrying it.

    This is the discriminator that separates a tradeable biotech catalyst from
    a non-event. A Phase 3 readout at a large-cap pharma with forty programmes
    in flight is noise: one asset failing moves the stock a percent or two. The
    same readout at a company whose entire value is that one asset is the whole
    thesis.

    Market cap is a crude proxy for "how concentrated is this company's value
    in this programme", but it is the best one available from free data, and it
    is directionally right: small caps are single-asset, large caps are not.

    Unknown market cap does NOT veto here, unlike the other screens. Cap
    requires a price, and no free price source is wired yet -- vetoing on it
    would silently reject everything and make the pipeline look quiet rather
    than incomplete. It annotates instead, and the caveat travels with the
    signal.
    """
    detail = {
        "market_cap_usd": market_cap_usd,
        "max_market_cap_usd": config.max_market_cap_usd,
    }

    if market_cap_usd is None:
        return ScreenResult(
            "materiality",
            True,
            "Market cap unavailable (no price source wired), so materiality could not be "
            "assessed. A readout at a large-cap sponsor may not move the stock.",
            detail,
        )

    if market_cap_usd > config.max_market_cap_usd:
        return ScreenResult(
            "materiality",
            False,
            f"Market cap ${market_cap_usd/1e9:.1f}B exceeds the "
            f"${config.max_market_cap_usd/1e9:.1f}B ceiling. One readout among many "
            "programmes is unlikely to re-rate a company this size.",
            detail,
        )

    return ScreenResult(
        "materiality",
        True,
        f"Market cap ${market_cap_usd/1e6:,.0f}M is small enough for a single readout to matter",
        detail,
    )
