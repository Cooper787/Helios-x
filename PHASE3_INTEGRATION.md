# Phase 3: AI Intelligence Layer + UI Integration

## Overview

Phase 3 adds the intelligence layer to Helios-X, enabling natural language commands, persistent learning, and ML-based signal generation. This layer sits above the trading infrastructure (Phase 2) and governance framework (Phase 1).

## Components

### 1. Memory System (`memory/`)

Persistent learning through JSONL-based append-only storage.

**Files:**
- `__init__.py` - Package exports
- `persistence.py` - JSONL storage with SHA256 hashing
- `episodic.py` - Trade event recording

**Usage:**
```python
from memory import EpisodicMemory
mem = EpisodicMemory()
mem.record_trade(symbol="SPLG", qty=10, price=123.45, side="buy")
```

### 2. OpenClaw - NLU Interface (`openclaw/`)

Natural language command parser for trading control.

**Files:**
- `__init__.py` - Package exports
- `parser.py` - Command parsing with regex patterns

**Supported Commands:**
- `buy 10 SPLG` - Buy 10 shares
- `sell 5 SPLG` - Sell 5 shares
- `status` - Get portfolio status
- `stop` - Stop trading

**Usage:**
```python
from openclaw import CommandParser
parser = CommandParser()
cmd = parser.parse("buy 10 SPLG")
print(cmd)  # {"action": "buy", "qty": 10, "symbol": "SPLG"}
```

### 3. Strategy - ML Signals (`strategy/`)

Technical indicators and signal generation.

**Files:**
- `__init__.py` - Package exports
- `indicators.py` - SMA, RSI, MACD calculations
- `signals.py` - Signal generation logic

**Usage:**
```python
from strategy import SignalGenerator
gen = SignalGenerator(sma_period=20)
prices = [100, 101, 102, 103, 104]
signal = gen.generate(prices, current_price=105)
print(signal)  # "buy" or "sell" or "hold"
```

### 4. HeliosCore - Orchestration (`helios_core/`)

Central orchestration with MessageBus for inter-component communication.

**Features:**
- Message routing between components
- Event subscription/publishing
- Kill switch event propagation
- Graceful shutdown

## Architecture

```
HeliosCore (orchestration)
├── Memory (persistence)
│   ├── Episodic (trade history)
│   └── Persistence (JSONL store)
├── OpenClaw (NLU)
│   └── CommandParser
├── Strategy (signals)
│   ├── Indicators (SMA, RSI, MACD)
│   └── SignalGenerator
├── Argus (governance)
│   ├── GovernanceEnforcer
│   └── ArchitectureValidator
└── Rogue-X (trading)
    ├── TradingConfig (safety)
    ├── RiskGate (limits)
    ├── KillSwitch (emergency stop)
    └── AuditLogger (compliance)
```

## Testing

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run Phase 3 tests
pytest tests/ -v -k phase3

# Test individual modules
python -m pytest tests/test_memory.py
python -m pytest tests/test_openclaw.py
python -m pytest tests/test_strategy.py
```

## UI Integration

The Streamlit dashboard connects to this layer via FastAPI:

```bash
# Terminal 1: FastAPI server
uvicorn helios_api.server:app --port 8000

# Terminal 2: Streamlit dashboard
streamlit run ui/app.py
```

## Version

- **Phase 3**: v0.3.0
- **AI Layer**: ~8,000 lines of production-ready Python
- **Dependencies**: stdlib-only (no external AI/ML required)

## Next Steps

1. ✅ Deploy Phase 3 code to phase3-integration branch
2. ⏳ Run CI pipeline
3. ⏳ Create PR to main
4. ⏳ Merge after review
5. ⏳ Tag v0.3.0 release
6. ⏳ Deploy dashboard

## Safety Notes

- All trading defaults to **paper mode**
- Live trading **explicitly blocked** without approval
- All trades **audit logged** with SHA256 hash chain
- **Kill switch** can stop all trading instantly
- Memory is **append-only** (immutable logs)
