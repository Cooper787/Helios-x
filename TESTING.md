# Helios-X Phase 3: Testing & Deployment Guide

## Quick Start (Development)

### 1. Setup Environment

```bash
# Clone repository
git clone https://github.com/Cooper787/Helios-x.git
cd Helios-x

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install with dev dependencies
pip install -e ".[dev]"
pip install -r requirements-ui.txt
```

### 2. Run Phase 3 Unit Tests

```bash
# Test individual modules
python tests/test_paper_trading.py

# Run with pytest
pytest tests/test_paper_trading.py -v

# Run all tests
pytest tests/ -v
```

### 3. Deploy UI Dashboard (2 Terminals)

**Terminal 1: Start FastAPI Server**
```bash
cd /path/to/Helios-x
uvicorn helios_api.server:app --port 8000 --reload
```

**Terminal 2: Start Streamlit Dashboard**
```bash
cd /path/to/Helios-x
streamlit run ui/app.py
```

Then open: http://localhost:8501

### 4. Paper Trading Test

In the Streamlit dashboard:
1. Symbol: SPLG
2. Capital: $500
3. Qty: 1 share
4. Duration: 30 minutes (1800 seconds)
5. Click "Start Trading"
6. View audit log to confirm trades

## Testing Checklist

### Unit Tests (Memory)
- [ ] Memory store creates append-only JSONL log
- [ ] SHA256 hash chain validates integrity
- [ ] Episodic memory records trades correctly

### Unit Tests (OpenClaw - NLU)
- [ ] Parse "buy 10 SPLG" → {action: buy, qty: 10, symbol: SPLG}
- [ ] Parse "sell 5 SPLG" → {action: sell, qty: 5, symbol: SPLG}
- [ ] Parse "status" → {action: status}
- [ ] Parse invalid command → {error: ...}

### Unit Tests (Strategy)
- [ ] SMA calculation with period=20 works correctly
- [ ] Signal generation produces buy/sell/hold
- [ ] Handles price lists of varying lengths

### Integration Tests
- [ ] Parse command → Record in memory → Generate signal
- [ ] Multiple trades recorded sequentially
- [ ] Audit log contains all trades with timestamps

### UI Tests
- [ ] Dashboard loads at http://localhost:8501
- [ ] API status shows correct running state
- [ ] Start trading button sends request
- [ ] Stop button triggers graceful shutdown
- [ ] Kill button triggers hard stop
- [ ] Audit log displays trade history

### API Tests
- [ ] GET /status returns running status
- [ ] POST /start launches paper trading
- [ ] POST /stop creates kill switch file
- [ ] POST /kill terminates process
- [ ] GET /audit/tail returns last N records

## GitHub Actions CI

Automatically runs on:
- Push to main or phase3-integration
- Pull requests to main

Tests:
- Python 3.11 and 3.12
- Linting (ruff, black)
- Unit tests (pytest)
- Integration tests
- Security scan

View results: https://github.com/Cooper787/Helios-x/actions

## Paper Trading Workflow

1. **Start Trading**
   - FastAPI server must be running
   - Click "Start Trading" in dashboard
   - Monitor PID in status

2. **During Trading**
   - Memory records each trade
   - Strategy generates signals
   - Audit log timestamps all events

3. **Stop Trading**
   - Click "Stop (Graceful)" for clean shutdown
   - Or "Kill (Hard Stop)" for emergency stop
   - Check "Kill switch" status

4. **Review Results**
   - Load audit log in dashboard
   - Each trade shows symbol, qty, price, side
   - Check memory/episodes.jsonl for full history

## Safety Features

✅ Paper trading enforced by default
✅ Kill switch can stop all trading instantly
✅ Append-only audit logs (immutable)
✅ SHA256 hash chain for integrity
✅ No external credentials required
✅ No live trading without explicit approval

## Troubleshooting

### "Cannot reach API"
- Ensure `uvicorn` is running on port 8000
- Check: `ps aux | grep uvicorn`

### "No module named 'fastapi'"
- Install UI requirements: `pip install -r requirements-ui.txt`

### "Memory not recording"
- Check: `ls -la memory/`
- Verify: `cat memory/episodes.jsonl`

### Tests failing
- Run individually: `python tests/test_paper_trading.py`
- Check Python version: `python --version` (should be 3.11+)

## Next Steps

1. ✅ PR #5 created and tests passing
2. ✅ UI deployed (Streamlit + FastAPI)
3. ⏳ Run full CI pipeline
4. ⏳ Paper trading tests this week
5. ⏳ Tag v0.3.0 release
6. ⏳ Begin IBKR integration for live trading
