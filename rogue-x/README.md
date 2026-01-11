# ROGUE-X Trading Engine

**Revenue Optimizing Growth & Utility Engine - eXperimental**

Professional-grade algorithmic trading system with comprehensive safety constraints.

## Overview

ROGUE-X is the execution layer of the Helios-x autonomous trading ecosystem. It implements a quantitative trading strategy with strict risk management and safety protocols.

## Key Features

- **13 Critical Safety Fixes Implemented**
- **Realistic Performance Targets**: 15-35% annual returns
- **Strict Risk Management**: 15% max position size, -25% circuit breaker
- **Production-Ready**: No stubs, full error handling
- **Multi-Symbol Support**: Consistent validation across assets

## Architecture

```
Data → Features → Signals → Risk → Execution → Backtest → Analytics
```

### 7 Layers:

1. **Data Layer**: Validation, warmup, quality checks
2. **Feature Layer**: Technical indicators with error handling
3. **Signal Layer**: Aggregated signals with balanced weights
4. **Risk Layer**: Position sizing, drawdown protection
5. **Execution Layer**: Order management (future IBKR integration)
6. **Backtest Layer**: Walk-forward validation
7. **Analytics Layer**: Performance metrics

## Safety Constraints

### Hard Limits (NEVER VIOLATE):

- **Position Size**: 15% maximum (current: 10%)
- **Warmup Period**: 210 bars minimum (EMA 200 + buffer)
- **Circuit Breaker**: -25% drawdown halt
- **Safety Validations**: All 5 must remain enabled

### Realistic Targets:

- Annual returns: 15-35%
- Sharpe ratio: 0.8-1.5
- Max drawdown: -15% to -25%
- Win rate: 52-58%
- Trades: 8-15/month

## Quick Start

### Installation

```bash
# Python 3.10 or 3.11 required
cd rogue-x/
pip install -r requirements.txt
```

### Run Backtest

```python
from config.tradingconfig import TradingConfig
from core.tradingengine import TradingEngine
from core.riskmanager import RiskManager
from core.backtester import Backtester

# Configure
config = TradingConfig(
    symbol='NVDA',  # Required
    starting_capital=100000.0,  # Required
    data_period='2y',  # Optional (default: '2y')
    verbose=True  # Optional (default: False)
)

# Initialize
engine = TradingEngine(config)
risk_mgr = RiskManager(config)
backtester = Backtester(config, engine, risk_mgr)

# Run
results = backtester.run(period='2y')
```

### Safety Check

```bash
# Verify all safety constraints
python scripts/safety_check.py
```

### Multi-Symbol Validation

```bash
# Test consistency across 5+ symbols
python scripts/run_multi_symbol.py
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Specific components
pytest tests/test_data_validator.py -v
pytest tests/test_signal_aggregator.py -v
```

## Project Status

✅ **Integration & Validation Phase**
- All 13 critical fixes implemented
- Safety constraints enforced
- Production-ready code
- Ready for extended validation

❌ **NOT Ready For:**
- Paper trading (requires 3-month backtest validation)
- Live trading (requires 3-month paper validation)

## 13 Critical Fixes

1. ✅ Data validation (DataValidator)
2. ✅ Warmup period (210 bars minimum)
3. ✅ Signal weighting (50/30/20 balanced)
4. ✅ Error handling (@safe_indicator decorator)
5. ✅ Confidence threshold (lowered to 70%)
6. ✅ Drawdown protection (adaptive sizing)
7. ✅ Max holding period (10-40 bars)
8. ✅ Data frequency validation
9. ✅ Liquidity checks (volume/spread)
10. ✅ Sentiment removed from backtest
11. ✅ Parameter optimization framework
12. ✅ Paper trading framework (disabled)
13. ✅ Multi-symbol backtester

## Governance

ROGUE-X follows Helios-x governance rules:
- No autonomous capital deployment
- No silent behavior changes
- All actions auditable
- Human approval required for execution

## Documentation

- `docs/SAFETY_HOOKS.md` - Safety constraint details
- `docs/INTEGRATION_GUIDE.md` - Integration instructions
- `docs/FAQ.md` - Common questions
- `docs/HANDOFF_DOCUMENT.md` - Complete system overview

## Performance Philosophy

**310% → 35% is SUCCESS, not failure**

Old 310% came from 13 bugs (random decisions, no costs, excessive leverage).
New 15-35% is realistic, achievable, professional-grade performance.

Compare to:
- S&P 500: ~10% annually
- Professional quant funds: 15-30% annually
- ROGUE-X: 15-35% annually ✅

## License

Private - Part of Helios-x ecosystem

## Contact

Part of the Helios-x autonomous trading ecosystem.
Governed by Argus (Autonomous CTO).
