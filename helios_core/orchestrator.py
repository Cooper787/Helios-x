"""Orchestrator

Central coordination layer for the Helios autonomous system.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates activities across multiple agents and subsystems."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.subsystems: Dict[str, Any] = {}
        self.task_queue: List[Dict[str, Any]] = []
        self.execution_history: List[Dict[str, Any]] = []
        logger.info("Orchestrator initialized")

    def register_subsystem(self, name: str, subsystem: Any) -> bool:
        """Register a subsystem with the orchestrator."""
        try:
            self.subsystems[name] = subsystem
            logger.info(f"Subsystem '{name}' registered")
            return True
        except Exception as e:
            logger.error(f"Failed to register subsystem '{name}': {e}")
            return False

    def queue_task(self, task: Dict[str, Any]) -> bool:
        """Add a task to the execution queue."""
        try:
            task["queued_at"] = datetime.now().isoformat()
            task["status"] = "queued"
            self.task_queue.append(task)
            logger.info(f"Task queued: {task.get('id', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to queue task: {e}")
            return False

    def execute_task(self, task_id: str) -> bool:
        """Execute a specific task from the queue."""
        for task in self.task_queue:
            if task.get("id") == task_id:
                task["status"] = "executing"
                task["started_at"] = datetime.now().isoformat()
                logger.info(f"Executing task: {task_id}")

                handler = task.get("handler")
                if not callable(handler):
                    # FAIL-CLOSED: no handler means the task cannot run.
                    # Never mark unexecuted work as completed.
                    task["status"] = "failed"
                    task["error"] = "No callable handler attached to task"
                    task["completed_at"] = datetime.now().isoformat()
                    self.execution_history.append(task)
                    self.task_queue.remove(task)
                    logger.error(f"Task {task_id} failed: no handler")
                    return False

                try:
                    task["result"] = handler(task)
                    task["status"] = "completed"
                except Exception as e:
                    task["status"] = "failed"
                    task["error"] = str(e)
                    logger.error(f"Task {task_id} raised: {e}")

                task["completed_at"] = datetime.now().isoformat()
                self.execution_history.append(task)
                self.task_queue.remove(task)
                return task["status"] == "completed"
        logger.warning(f"Task not found: {task_id}")
        return False

    def get_system_status(self) -> Dict[str, Any]:
        """Get current status of all subsystems."""
        return {
            "subsystems": list(self.subsystems.keys()),
            "queued_tasks": len(self.task_queue),
            "completed_tasks": len(self.execution_history),
            "timestamp": datetime.now().isoformat(),
        }
