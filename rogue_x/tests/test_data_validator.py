"""Tests for DataValidator and TradingConfig."""

import pytest

from rogue_x.config import TradingConfig
from rogue_x.core import DataValidator


class TestPriceValidation:
    def test_valid_price(self):
        assert DataValidator.validate_price(100.5, "AAPL")

    @pytest.mark.parametrize("bad", [0, -1, -0.01])
    def test_non_positive_price_rejected(self, bad):
        with pytest.raises(ValueError):
            DataValidator.validate_price(bad, "AAPL")

    def test_non_numeric_price_rejected(self):
        with pytest.raises(ValueError):
            DataValidator.validate_price("100", "AAPL")

    def test_absurd_price_rejected(self):
        with pytest.raises(ValueError):
            DataValidator.validate_price(1e10, "AAPL")


class TestQuantityValidation:
    def test_valid_quantities(self):
        assert DataValidator.validate_quantity(10, "AAPL")
        assert DataValidator.validate_quantity(-10, "AAPL")  # shorts allowed

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValueError):
            DataValidator.validate_quantity(0, "AAPL")

    def test_absurd_quantity_rejected(self):
        with pytest.raises(ValueError):
            DataValidator.validate_quantity(1e10, "AAPL")


class TestMarketDataValidation:
    def test_valid_market_data(self):
        assert DataValidator.validate_market_data(
            {"symbol": "AAPL", "price": 100.0, "volume": 1_000_000}
        )

    @pytest.mark.parametrize("missing", ["symbol", "price", "volume"])
    def test_missing_field_rejected(self, missing):
        data = {"symbol": "AAPL", "price": 100.0, "volume": 1_000_000}
        del data[missing]
        with pytest.raises(ValueError):
            DataValidator.validate_market_data(data)

    def test_negative_volume_rejected(self):
        with pytest.raises(ValueError):
            DataValidator.validate_market_data(
                {"symbol": "AAPL", "price": 100.0, "volume": -1}
            )


class TestOrderValidation:
    def test_valid_order(self):
        assert DataValidator.validate_order(
            {"symbol": "AAPL", "quantity": 10, "price": 100.0, "side": "buy"}
        )

    def test_invalid_side_rejected(self):
        with pytest.raises(ValueError):
            DataValidator.validate_order(
                {"symbol": "AAPL", "quantity": 10, "price": 100.0, "side": "hold"}
            )

    def test_invalid_stop_loss_rejected(self):
        with pytest.raises(ValueError):
            DataValidator.validate_order(
                {
                    "symbol": "AAPL",
                    "quantity": 10,
                    "price": 100.0,
                    "side": "buy",
                    "stop_loss": -5,
                }
            )


class TestTradingConfig:
    def test_defaults_are_valid(self):
        assert TradingConfig().validate()

    def test_defaults_are_conservative(self):
        cfg = TradingConfig()
        assert cfg.max_position_size <= 0.15
        assert cfg.max_drawdown == pytest.approx(0.25)
        assert cfg.warmup_bars == 210
        assert cfg.require_stop_loss is True
        assert cfg.max_leverage == 1.0

    @pytest.mark.parametrize(
        "field,value",
        [
            ("max_position_size", 0.30),
            ("max_position_size", 0),
            ("max_portfolio_risk", 0.60),
            ("max_daily_loss", 0.25),
            ("max_drawdown", 0.60),
            ("max_drawdown", 0),
            ("warmup_bars", -1),
            ("max_positions", 0),
            ("max_leverage", 5.0),
        ],
    )
    def test_out_of_bounds_values_rejected(self, field, value):
        with pytest.raises(ValueError):
            TradingConfig(**{field: value}).validate()
