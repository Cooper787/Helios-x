"""Dilution veto: refuse candidates that are about to sell shares.

A clinical-stage biotech has no revenue. It funds itself by issuing equity, and
the classic pattern is an offering priced immediately into good news -- so
being right about the science and still losing money is the normal outcome, not
the unlucky one.

This is a hard veto rather than a scored input for two reasons: it is objective
(a number from a filing, not a judgement), and it is the failure mode most
likely to turn a correct thesis into a loss.

**Unknown runway vetoes.** A company whose filings cannot be parsed is not
thereby safe. Failing open here would mean the least transparent companies
receive the most lenient treatment, which is precisely backwards.
"""

from __future__ import annotations

import math

from ..config import SignalConfig
from ..models import CashRunway, ScreenResult


def screen_dilution(runway: CashRunway, config: SignalConfig) -> ScreenResult:
    detail = {
        "cik": runway.cik,
        "runway_months": None if runway.months is None else (
            "infinite" if math.isinf(runway.months) else round(runway.months, 1)
        ),
        "cash_usd": runway.cash_usd,
        "quarterly_burn_usd": runway.quarterly_burn_usd,
        "source": runway.provenance.source,
        "note": runway.note,
    }

    if runway.months is None:
        if config.veto_on_unknown_runway:
            return ScreenResult(
                "dilution",
                False,
                f"Cash runway could not be determined ({runway.note or 'no reason given'}). "
                "Vetoing: unknown is not the same as safe.",
                detail,
            )
        return ScreenResult(
            "dilution", True, "Runway unknown, veto disabled by config", detail
        )

    if math.isnan(runway.months):
        return ScreenResult(
            "dilution", False, "Cash runway computed as NaN; vetoing", detail
        )

    if math.isinf(runway.months):
        return ScreenResult(
            "dilution",
            True,
            "Operating cash flow is non-negative; no near-term dilution pressure",
            detail,
        )

    if runway.months < config.min_cash_runway_months:
        return ScreenResult(
            "dilution",
            False,
            f"Cash runway {runway.months:.1f} months is below the "
            f"{config.min_cash_runway_months:.0f}-month floor. An equity offering is "
            "likely and would be priced at a discount to market.",
            detail,
        )

    return ScreenResult(
        "dilution",
        True,
        f"Cash runway {runway.months:.1f} months clears the "
        f"{config.min_cash_runway_months:.0f}-month floor",
        detail,
    )
