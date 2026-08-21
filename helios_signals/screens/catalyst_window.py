"""Timing screen: enter in the drift window, never hold the binary.

    T-60 ....... T-20        T-5        T-0
    |--- entry window ---|   |  exit  |  EVENT
                             ^ hard exit

The exit rule is the important half. A clinical-stage biotech does not drift
through a stop on a failed readout -- it gaps 40-70% in a single print,
typically pre-market. A stop order offers no protection against a gap, so the
only defence is not being in the position.

This mirrors the rule already recorded in the project's decision records:
never hold a small-cap through its binary event.
"""

from __future__ import annotations

from datetime import date

from ..config import SignalConfig
from ..models import Catalyst, ScreenResult


def screen_catalyst_window(
    catalyst: Catalyst, as_of: date, config: SignalConfig
) -> ScreenResult:
    days = catalyst.days_until(as_of)
    detail = {
        "days_to_catalyst": days,
        "event_date": catalyst.event_date.isoformat(),
        "date_is_estimated": catalyst.date_is_estimated,
    }

    if days < 0:
        return ScreenResult(
            "catalyst_window", False, f"Event date has passed ({days} days ago)", detail
        )

    if days <= config.hard_exit_days_before:
        return ScreenResult(
            "catalyst_window",
            False,
            f"Inside the exit window: {days}d to event, hard exit at "
            f"T-{config.hard_exit_days_before}. Never hold through a binary readout.",
            detail,
        )

    if days < config.entry_window_min_days:
        return ScreenResult(
            "catalyst_window",
            False,
            f"Too close to the event: {days}d remaining, minimum entry is "
            f"T-{config.entry_window_min_days}. Not enough runway to exit before T-"
            f"{config.hard_exit_days_before}.",
            detail,
        )

    if days > config.entry_window_max_days:
        return ScreenResult(
            "catalyst_window",
            False,
            f"Too early: {days}d to event, entry window opens at T-"
            f"{config.entry_window_max_days}.",
            detail,
        )

    return ScreenResult(
        "catalyst_window",
        True,
        f"In the entry window at T-{days}",
        detail,
    )
