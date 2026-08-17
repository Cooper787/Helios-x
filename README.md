# Helios-x

Helios-x is a private architectural umbrella for autonomous systems. This repository defines:

- system architecture (`helios_core/`)
- governance and safety boundaries (`docs/`, `argus_gov/`)
- agent coordination workflows
- Argus, the Autonomous CTO (`argus/`)
- Rogue-X trading engine core: risk management, validation, and safety gates (`rogue_x/`)

This repository does NOT:

- execute live trades (order execution is a stub by design until validation is complete)
- manage credentials
- control capital directly

## Safety invariants (enforced in code and tests)

- Long-only by default (`allow_short=False`)
- No leverage by default (`max_leverage=1.0`)
- Stop loss required on every position
- 210-bar warmup before any position may open
- Daily loss limit includes unrealized PnL
- Circuit breaker halts all trading at 25% equity drawdown from peak; the halt latches until a human resets it
- Governance validators fail closed: unimplemented checks route to manual review, never auto-approval

## Development

```bash
pip install -e ".[dev]"
pytest -q                              # full test suite
python rogue_x/scripts/safety_check.py # standalone safety verification
argus-gov --help                       # governance toolkit CLI
```

**If it is not committed here, it is not authoritative.**
