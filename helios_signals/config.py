"""Configuration for the signal pipeline.

Constants here are deliberately conservative and deliberately *not* derived
from any backtest, because no validated backtest exists yet. They are stated
priors, and they are labelled as such so nobody later mistakes them for
fitted parameters. When the event-outcome dataset exists, these get replaced
with fitted values and this note gets deleted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class SignalConfig:
    """Thresholds governing signal generation."""

    # --- Catalyst timing window ---
    # Enter no earlier than T-60 and exit no later than T-5. The exit is the
    # load-bearing half: holding a clinical-stage biotech through a binary
    # readout is the single most reliable way to lose the account. A failed
    # Phase 3 does not drift through a stop, it gaps 40-70% in one print, and
    # a stop order does not protect against a gap.
    entry_window_max_days: int = 60
    entry_window_min_days: int = 20
    hard_exit_days_before: int = 5

    # --- Dilution veto (hard) ---
    # Runway below this many months means an equity offering is close to
    # certain, and offerings are priced at a discount to market.
    min_cash_runway_months: float = 6.0
    # If runway cannot be determined at all, veto. Fail closed, not open.
    veto_on_unknown_runway: bool = True

    # --- Universe filters ---
    min_price: float = 5.0
    max_price: float = 500.0

    # --- Biotech discriminators ---
    # Registrational-scale floor. A 25-patient open-label study labelled
    # "Phase 3" is not the event a Phase 3 readout is supposed to be.
    min_enrollment: int = 100
    veto_on_unknown_enrollment: bool = True
    # Above this, one readout among many programmes rarely re-rates the stock.
    # Crude proxy for "is this company's value concentrated in this asset".
    max_market_cap_usd: float = 10_000_000_000.0
    # Only industry-sponsored trials have a ticker attached to the outcome.
    require_industry_sponsor: bool = True

    # --- Sizing ---
    # Fraction of account risked per position (distance to stop), not
    # position size as a fraction of the account.
    risk_per_trade: float = 0.02
    # Stop distance as a fraction of entry. Wide, because biotech is volatile
    # and a tight stop in this sector just guarantees noise-outs.
    stop_loss_pct: float = 0.15

    # --- Operational ---
    max_signals_per_run: int = 3
    request_timeout_s: int = 30
    max_retries: int = 4
    user_agent: str = "Helios-X/0.1 (research; andrewncooper@gmail.com)"

    # Phases worth tracking. Phase 1 readouts rarely move a stock in a
    # tradeable, predictable way and add noise to a thin universe.
    tracked_phases: List[str] = field(default_factory=lambda: ["PHASE3", "PHASE2"])

    @classmethod
    def from_env(cls) -> "SignalConfig":
        cfg = cls()
        if ua := os.environ.get("HELIOS_USER_AGENT"):
            cfg.user_agent = ua
        if v := os.environ.get("HELIOS_MIN_RUNWAY_MONTHS"):
            cfg.min_cash_runway_months = float(v)
        if v := os.environ.get("HELIOS_MAX_SIGNALS"):
            cfg.max_signals_per_run = int(v)
        return cfg

    def validate(self) -> None:
        if not 0 < self.risk_per_trade <= 0.05:
            raise ValueError("risk_per_trade must be in (0, 0.05]")
        if self.entry_window_min_days <= self.hard_exit_days_before:
            raise ValueError(
                "entry_window_min_days must exceed hard_exit_days_before, "
                "otherwise a position could be opened inside its own exit window"
            )
        if self.entry_window_max_days <= self.entry_window_min_days:
            raise ValueError("entry_window_max_days must exceed entry_window_min_days")
        if self.min_cash_runway_months <= 0:
            raise ValueError("min_cash_runway_months must be positive")
        if self.min_enrollment < 1:
            raise ValueError("min_enrollment must be at least 1")
        if self.max_market_cap_usd <= 0:
            raise ValueError("max_market_cap_usd must be positive")


@dataclass
class AccountConfig:
    """Andrew's account. TFSA: cash, non-margin, long-only.

    Shorting and option writing are not merely disabled here, they are absent
    from the codebase. Confirmed TFSA rules: no short selling, no naked option
    writing, and multi-leg spreads are generally restricted because they imply
    margin. There is no configuration flag that turns them on, because there
    is no code path that could honour one.
    """

    capital: float = 1000.0
    monthly_deposit: float = 50.0
    currency: str = "USD"
    account_type: str = "TFSA"
    long_only: bool = True

    def validate(self) -> None:
        if self.capital <= 0:
            raise ValueError("capital must be positive")
        if not self.long_only:
            raise ValueError(
                "long_only cannot be disabled: shorting is prohibited in a TFSA"
            )
