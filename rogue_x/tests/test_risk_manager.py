"""Tests for RiskManager safety constraints."""

import pytest

from rogue_x.config import TradingConfig
from rogue_x.core import RiskManager


def make_rm(capital=100_000.0, warmed_up=True, **config_overrides):
    """Build a RiskManager; by default skip warmup so limit tests can run."""
    config_overrides.setdefault("warmup_bars", 0 if warmed_up else 210)
    config = TradingConfig(**config_overrides)
    return RiskManager(config, capital)


class TestInitialization:
    def test_rejects_zero_capital(self):
        with pytest.raises(ValueError):
            RiskManager(TradingConfig(), 0)

    def test_rejects_negative_capital(self):
        with pytest.raises(ValueError):
            RiskManager(TradingConfig(), -1000)

    def test_invalid_config_rejected_on_init(self):
        with pytest.raises(ValueError):
            RiskManager(TradingConfig(max_position_size=0.9), 100_000)


class TestWarmup:
    def test_no_positions_before_warmup(self):
        rm = make_rm(warmed_up=False)
        can_open, reason = rm.can_open_position("AAPL", 5, 100.0, 95.0)
        assert not can_open
        assert "Warmup" in reason

    def test_positions_allowed_after_warmup(self):
        rm = make_rm(warmed_up=False)
        for _ in range(210):
            rm.record_bar()
        can_open, _ = rm.can_open_position("AAPL", 5, 100.0, 95.0)
        assert can_open


class TestPositionLimits:
    def test_valid_position_approved(self):
        rm = make_rm()
        can_open, reason = rm.can_open_position("AAPL", 10, 100.0, 95.0)
        assert can_open, reason

    def test_oversized_position_rejected(self):
        rm = make_rm(max_position_size=0.02)  # $2,000 limit on $100k
        can_open, reason = rm.can_open_position("AAPL", 100, 100.0, 95.0)  # $10,000
        assert not can_open
        assert "exceeds limit" in reason

    def test_max_positions_enforced(self):
        rm = make_rm(max_positions=2)
        assert rm.open_position("AAPL", 5, 100.0, 95.0)
        assert rm.open_position("MSFT", 5, 100.0, 95.0)
        can_open, reason = rm.can_open_position("GOOG", 5, 100.0, 95.0)
        assert not can_open
        assert "Maximum" in reason

    def test_duplicate_symbol_rejected(self):
        rm = make_rm()
        assert rm.open_position("AAPL", 5, 100.0, 95.0)
        can_open, reason = rm.can_open_position("AAPL", 5, 100.0, 95.0)
        assert not can_open
        assert "already exists" in reason

    def test_portfolio_exposure_limit(self):
        # 2% per position, 10% portfolio: 6 positions of 2% would breach 10%
        rm = make_rm(max_positions=10, max_position_size=0.02, max_portfolio_risk=0.10)
        for i in range(5):
            assert rm.open_position(f"SYM{i}", 19, 100.0, 95.0)  # $1,900 each
        can_open, reason = rm.can_open_position("SYM5", 19, 100.0, 95.0)
        assert not can_open
        assert "exposure" in reason.lower()

    def test_invalid_inputs_rejected(self):
        rm = make_rm()
        assert not rm.can_open_position("AAPL", 0, 100.0, 95.0)[0]
        assert not rm.can_open_position("AAPL", -5, 100.0, 95.0)[0]
        assert not rm.can_open_position("AAPL", 5, 0.0, 95.0)[0]
        assert not rm.can_open_position("AAPL", 5, -100.0, 95.0)[0]


class TestStopLoss:
    def test_stop_loss_required_by_default(self):
        rm = make_rm()
        can_open, reason = rm.can_open_position("AAPL", 5, 100.0, stop_loss=None)
        assert not can_open
        assert "Stop loss is required" in reason

    def test_long_stop_must_be_below_entry(self):
        rm = make_rm()
        can_open, reason = rm.can_open_position("AAPL", 5, 100.0, stop_loss=105.0)
        assert not can_open

    def test_stop_hit_closes_at_market_price_not_stop_price(self):
        rm = make_rm()
        rm.open_position("AAPL", 10, 100.0, stop_loss=95.0)
        # Price gaps down through the stop
        rm.update_position_price("AAPL", 90.0)
        hit = rm.check_stop_losses()
        assert hit == ["AAPL"]
        assert "AAPL" not in rm.positions
        # Loss should reflect the gap fill at $90, not an optimistic $95 fill
        assert rm.current_capital == pytest.approx(100_000 - 100.0)


class TestDailyLossLimit:
    def test_realized_daily_loss_blocks_new_positions(self):
        rm = make_rm(max_daily_loss=0.05)
        rm.open_position("AAPL", 19, 100.0, 95.0)
        rm.close_position("AAPL", 0.01)  # near-total loss on the position
        rm.daily_pnl = -6_000  # force 6% daily loss
        can_open, reason = rm.can_open_position("MSFT", 5, 100.0, 95.0)
        assert not can_open
        assert "Daily loss limit" in reason

    def test_unrealized_losses_count_toward_daily_limit(self):
        rm = make_rm(max_daily_loss=0.02, max_position_size=0.05)
        rm.open_position("AAPL", 40, 100.0, 40.0)  # $4,000 position
        rm.update_position_price("AAPL", 40.0)  # -$2,400 unrealized = -2.4%
        can_open, reason = rm.can_open_position("MSFT", 5, 100.0, 95.0)
        assert not can_open
        assert "unrealized" in reason.lower() or "Daily loss" in reason


class TestCircuitBreaker:
    def test_drawdown_breach_halts_trading(self):
        rm = make_rm(max_drawdown=0.25, max_position_size=0.10, require_stop_loss=False)
        rm.open_position("AAPL", 100, 100.0)  # $10,000
        rm.update_position_price("AAPL", 10.0)  # unrealized -$9,000, but equity dd < 25%?
        # equity = 100000 - 9000 = 91000 -> 9% dd, no halt yet
        assert not rm.trading_halted
        rm.current_capital = 70_000  # simulate accumulated realized losses
        rm.check_circuit_breaker()  # equity 61,000 vs peak 100,000 = 39% dd
        assert rm.trading_halted
        can_open, reason = rm.can_open_position("MSFT", 1, 100.0)
        assert not can_open
        assert "halted" in reason.lower()

    def test_halt_latches_until_manual_reset(self):
        rm = make_rm(max_drawdown=0.25, require_stop_loss=False)
        rm.halt_trading("test halt")
        assert rm.trading_halted
        # Recovery of equity alone must not un-halt
        rm.check_circuit_breaker()
        assert rm.trading_halted
        rm.reset_halt()
        assert not rm.trading_halted

    def test_peak_capital_tracks_equity_high_water_mark(self):
        rm = make_rm(require_stop_loss=False)
        rm.open_position("AAPL", 10, 100.0)
        rm.update_position_price("AAPL", 200.0)  # +$1,000 unrealized
        assert rm.peak_capital == pytest.approx(101_000)


class TestAccounting:
    def test_close_position_updates_capital_and_daily_pnl(self):
        rm = make_rm()
        rm.open_position("AAPL", 10, 100.0, 95.0)
        pnl = rm.close_position("AAPL", 110.0)
        assert pnl == pytest.approx(100.0)
        assert rm.current_capital == pytest.approx(100_100.0)
        assert rm.daily_pnl == pytest.approx(100.0)

    def test_close_nonexistent_position_returns_none(self):
        rm = make_rm()
        assert rm.close_position("AAPL", 100.0) is None

    def test_reset_daily_metrics(self):
        rm = make_rm()
        rm.open_position("AAPL", 10, 100.0, 95.0)
        rm.close_position("AAPL", 110.0)
        rm.reset_daily_metrics()
        assert rm.daily_pnl == 0.0
        assert rm.daily_start_capital == pytest.approx(100_100.0)

    def test_portfolio_summary_reports_equity_and_halt_state(self):
        rm = make_rm()
        summary = rm.get_portfolio_summary()
        for key in ("capital", "equity", "peak_capital", "trading_halted", "bars_seen"):
            assert key in summary


class TestShortPolicy:
    def test_shorts_disabled_by_default(self):
        rm = make_rm()
        can_open, reason = rm.can_open_position("XYZ", -10, 100.0, stop_loss=110.0)
        assert not can_open
        assert "Short selling is disabled" in reason

    def test_shorts_work_when_explicitly_enabled(self):
        rm = make_rm(allow_short=True, max_position_size=0.05)
        assert rm.open_position("XYZ", -30, 100.0, stop_loss=110.0)
        rm.update_position_price("XYZ", 115.0)  # short losing, past stop
        assert rm.check_stop_losses() == ["XYZ"]
        # 30 shares short, entry 100, filled at market 115 => -$450
        assert rm.current_capital == pytest.approx(100_000 - 450)

    def test_short_stop_must_be_above_entry(self):
        rm = make_rm(allow_short=True)
        can_open, _ = rm.can_open_position("XYZ", -5, 100.0, stop_loss=95.0)
        assert not can_open

    def test_zero_quantity_rejected(self):
        rm = make_rm()
        can_open, reason = rm.can_open_position("XYZ", 0, 100.0, 95.0)
        assert not can_open
