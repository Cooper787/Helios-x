"""Trade logging module for ROGUE-X."""

import logging
from typing import Dict, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class TradeLogger:
    """Logs all trading activity for audit and analysis."""
    
    def __init__(self, log_file: str = "trades.log"):
        """Initialize trade logger.
        
        Args:
            log_file: Path to trade log file
        """
        self.log_file = log_file
        self.trade_logger = logging.getLogger("trade_logger")
        
        # Setup file handler
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(message)s')
        )
        self.trade_logger.addHandler(handler)
        self.trade_logger.setLevel(logging.INFO)
        
        logger.info(f"TradeLogger initialized: {log_file}")
    
    def log_order(self, order: Dict[str, Any]) -> None:
        """Log an order submission.
        
        Args:
            order: Order details
        """
        self.trade_logger.info(f"ORDER: {json.dumps(order)}")
    
    def log_execution(self, execution: Dict[str, Any]) -> None:
        """Log an order execution.
        
        Args:
            execution: Execution details
        """
        self.trade_logger.info(f"EXECUTION: {json.dumps(execution)}")
    
    def log_risk_check(self, check: Dict[str, Any]) -> None:
        """Log a risk check result.
        
        Args:
            check: Risk check details
        """
        self.trade_logger.info(f"RISK_CHECK: {json.dumps(check)}")
    
    def log_error(self, error: Dict[str, Any]) -> None:
        """Log a trading error.
        
        Args:
            error: Error details
        """
        self.trade_logger.error(f"ERROR: {json.dumps(error)}")
