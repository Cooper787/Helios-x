"""System-level tests: performance monitor, helios_core, governance fail-closed, CLI."""

import asyncio

from argus import ArgusCTO, GovernanceEnforcer
from argus_gov.cli import main as argus_gov_main
from helios_core.message_bus import MessageBus
from helios_core.orchestrator import Orchestrator
from rogue_x.core.performance_monitor import PerformanceMonitor


class TestPerformanceMonitor:
    def test_daily_summary_matches_recorded_trades(self):
        pm = PerformanceMonitor()
        pm.record_trade({"symbol": "AAPL", "pnl": 50.0})
        pm.record_trade({"symbol": "MSFT", "pnl": -20.0})
        summary = pm.get_daily_summary()
        # Regression test for the '%Y-%m-% d' format-string bug:
        # today's trades must actually appear in today's summary.
        assert summary["trades"] == 2
        assert summary["pnl"] == 50.0 - 20.0

    def test_win_rate(self):
        pm = PerformanceMonitor()
        pm.record_trade({"symbol": "A", "pnl": 10})
        pm.record_trade({"symbol": "B", "pnl": -5})
        assert pm.get_win_rate() == 50.0

    def test_total_pnl(self):
        pm = PerformanceMonitor()
        pm.record_trade({"symbol": "A", "pnl": 10})
        pm.record_trade({"symbol": "B", "pnl": -3})
        assert pm.get_total_pnl() == 7


class TestMessageBus:
    def test_publish_reaches_sync_and_async_subscribers(self):
        bus = MessageBus()
        received = []

        def sync_cb(msg):
            received.append(("sync", msg["payload"]))

        async def async_cb(msg):
            received.append(("async", msg["payload"]))

        bus.subscribe("trades", sync_cb)
        bus.subscribe("trades", async_cb)
        asyncio.run(bus.publish("trades", {"payload": 42}))

        assert ("sync", 42) in received
        assert ("async", 42) in received

    def test_history_filtered_by_topic(self):
        bus = MessageBus()
        asyncio.run(bus.publish("a", {"payload": 1}))
        asyncio.run(bus.publish("b", {"payload": 2}))
        assert len(bus.get_history("a")) == 1

    def test_failing_subscriber_does_not_break_publish(self):
        bus = MessageBus()

        def bad_cb(msg):
            raise RuntimeError("boom")

        bus.subscribe("t", bad_cb)
        assert asyncio.run(bus.publish("t", {"payload": 1}))


class TestOrchestratorFailClosed:
    def test_task_without_handler_fails_not_completes(self):
        orch = Orchestrator({})
        orch.queue_task({"id": "t1"})
        assert orch.execute_task("t1") is False
        assert orch.execution_history[0]["status"] == "failed"

    def test_task_with_handler_runs(self):
        orch = Orchestrator({})
        orch.queue_task({"id": "t2", "handler": lambda task: "done"})
        assert orch.execute_task("t2") is True
        assert orch.execution_history[0]["result"] == "done"

    def test_raising_handler_marks_failed(self):
        def boom(task):
            raise RuntimeError("nope")

        orch = Orchestrator({})
        orch.queue_task({"id": "t3", "handler": boom})
        assert orch.execute_task("t3") is False
        assert orch.execution_history[0]["status"] == "failed"


class TestGovernanceFailClosed:
    def test_unimplemented_validation_never_auto_approves(self):
        cto = ArgusCTO(config_path="/nonexistent/config.yaml")
        result = cto.review_architecture_proposal({"id": "p1"})
        assert result["status"] == "manual_review_required"
        assert cto.architecture_decisions == []
        assert len(cto.review_queue) == 1

    def test_enforce_standards_fails_closed(self):
        cto = ArgusCTO(config_path="/nonexistent/config.yaml")
        assert cto.enforce_standards("rogue_x", ["pep8"]) is False

    def test_governance_enforcer_flags_unreviewed_change(self):
        enforcer = GovernanceEnforcer()
        result = enforcer.validate_change({"id": "c1", "test_coverage": 0})
        assert result["compliant"] is False
        assert any("review" in v.lower() for v in result["violations"])


class TestArgusGovCLI:
    def test_init_creates_structure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert argus_gov_main(["init"]) == 0
        assert (tmp_path / "docs" / "decisions").is_dir()

    def test_validate_missing_path_returns_error_code(self):
        assert argus_gov_main(["validate", "/nonexistent/file.md"]) == 2

    def test_index_runs_on_docs(self, tmp_path):
        (tmp_path / "doc.md").write_text("# Decision\n\nStatus: approved\n")
        out = tmp_path / "index.json"
        assert argus_gov_main(["index", str(tmp_path), "--output", str(out)]) == 0
        assert out.exists()
