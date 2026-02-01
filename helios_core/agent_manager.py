"""Agent Manager

Manages the lifecycle and coordination of autonomous agents.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentManager:
    """Manages autonomous agents in the Helios system."""

    def __init__(self):
        self.agents: Dict[str, dict] = {}
        self.active_agents: List[str] = []
        logger.info("AgentManager initialized")

    def register_agent(self, agent_id: str, agent_config: dict) -> bool:
        """Register a new agent with the manager."""
        try:
            self.agents[agent_id] = {
                "config": agent_config,
                "status": "registered",
                "registered_at": datetime.now().isoformat(),
            }
            logger.info(f"Agent {agent_id} registered successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to register agent {agent_id}: {e}")
            return False

    def activate_agent(self, agent_id: str) -> bool:
        """Activate a registered agent."""
        if agent_id not in self.agents:
            logger.error(f"Agent {agent_id} not found")
            return False

        self.agents[agent_id]["status"] = "active"
        self.active_agents.append(agent_id)
        logger.info(f"Agent {agent_id} activated")
        return True

    def deactivate_agent(self, agent_id: str) -> bool:
        """Deactivate an active agent."""
        if agent_id in self.active_agents:
            self.active_agents.remove(agent_id)
            self.agents[agent_id]["status"] = "inactive"
            logger.info(f"Agent {agent_id} deactivated")
            return True
        return False

    def get_agent_status(self, agent_id: str) -> Optional[dict]:
        """Get the status of a specific agent."""
        return self.agents.get(agent_id)

    def list_active_agents(self) -> List[str]:
        """List all currently active agents."""
        return self.active_agents.copy()
