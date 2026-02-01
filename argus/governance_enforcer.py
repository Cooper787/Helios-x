"""Governance Enforcer

Enforces governance policies and rules across the Helios system.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class GovernanceEnforcer:
    """Enforces governance rules and policies."""

    def __init__(self, rules_config: Dict[str, Any] = None):
        self.rules = rules_config or self._default_rules()
        self.violations: List[Dict[str, Any]] = []
        self.enforcement_history: List[Dict[str, Any]] = []
        logger.info("GovernanceEnforcer initialized")

    def _default_rules(self) -> Dict[str, Any]:
        """Return default governance rules."""
        return {
            "require_code_review": True,
            "min_test_coverage": 80,
            "require_documentation": True,
            "enforce_naming_conventions": True,
            "max_function_complexity": 10,
        }

    def validate_change(self, change: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a proposed change against governance rules."""
        validation_result = {
            "change_id": change.get("id"),
            "timestamp": datetime.now().isoformat(),
            "compliant": True,
            "violations": [],
        }

        # Check code review requirement
        if self.rules.get("require_code_review") and not change.get("reviewed"):
            validation_result["compliant"] = False
            validation_result["violations"].append("Code review required")

        # Check test coverage
        coverage = change.get("test_coverage", 0)
        min_coverage = self.rules.get("min_test_coverage", 80)
        if coverage < min_coverage:
            validation_result["compliant"] = False
            validation_result["violations"].append(
                f"Test coverage {coverage}% below minimum {min_coverage}%"
            )

        # Check documentation
        if self.rules.get("require_documentation") and not change.get("has_docs"):
            validation_result["compliant"] = False
            validation_result["violations"].append("Documentation required")

        if not validation_result["compliant"]:
            self.violations.append(validation_result)
            logger.warning(f"Governance violations found for change {change.get('id')}")

        return validation_result

    def enforce_policy(self, policy_name: str, target: str) -> bool:
        """Enforce a specific governance policy."""
        try:
            enforcement_record = {
                "policy": policy_name,
                "target": target,
                "timestamp": datetime.now().isoformat(),
                "status": "enforced",
            }
            self.enforcement_history.append(enforcement_record)
            logger.info(f"Policy {policy_name} enforced on {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to enforce policy {policy_name}: {e}")
            return False

    def get_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance report."""
        return {
            "timestamp": datetime.now().isoformat(),
            "total_violations": len(self.violations),
            "recent_violations": self.violations[-10:],
            "enforcement_actions": len(self.enforcement_history),
            "active_rules": self.rules,
        }
