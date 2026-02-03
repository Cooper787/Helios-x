"""Shared pytest fixtures for UI tests."""
import pytest

@pytest.fixture
def sample_metrics():
    """Fixture providing sample metrics data."""
    return {
        'total_pnl': 1250.75,
        'win_rate': 0.68,
        'trades_executed': 42,
        'avg_win': 125.50,
        'avg_loss': -75.25
    }

@pytest.fixture
def sample_agents():
    """Fixture providing sample agent data."""
    return [
        {"id": "agent_1", "name": "Trader", "status": "active"},
        {"id": "agent_2", "name": "Analyst", "status": "idle"},
        {"id": "agent_3", "name": "Risk Manager", "status": "active"}
    ]

@pytest.fixture
def sample_trades():
    """Fixture providing sample trade data."""
    return [
        {"id": 1, "symbol": "AAPL", "quantity": 100, "entry": 150.0, "exit": 155.0, "pnl": 500.0},
        {"id": 2, "symbol": "GOOGL", "quantity": 50, "entry": 140.0, "exit": 138.0, "pnl": -100.0}
    ]

