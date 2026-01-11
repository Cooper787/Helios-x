"""Trading configuration for ROGUE-X."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class TradingConfig:
    """Configuration settings for ROGUE-X trading system."""
    
    # Risk Management
    max_position_size: float = 0.02  # 2% of portfolio per position
    max_portfolio_risk: float = 0.10  # 10% total portfolio risk
    max_daily_loss: float = 0.05  # 5% daily loss limit
    
    # Safety Constraints
    min_liquidity: float = 100000  # Minimum daily volume
    max_spread: float = 0.01  # Maximum bid-ask spread (1%)
    require_stop_loss: bool = True
    
    # Position Limits
    max_positions: int = 5
    max_leverage: float = 1.0  # No leverage by default
    
    # Trading Parameters
    default_symbols: List[str] = None
    trading_hours: Dict[str, str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.default_symbols is None:
            self.default_symbols = []  # Empty by default
        
        if self.trading_hours is None:
            self.trading_hours = {
                'start': '09:30',
                'end': '16:00'
            }
    
    def validate(self) -> bool:
        """Validate configuration parameters.
        
        Returns:
            bool: True if configuration is valid
        
        Raises:
            ValueError: If configuration is invalid
        """
        if self.max_position_size <= 0 or self.max_position_size > 0.25:
            raise ValueError("max_position_size must be between 0 and 0.25")
        
        if self.max_portfolio_risk <= 0 or self.max_portfolio_risk > 0.50:
            raise ValueError("max_portfolio_risk must be between 0 and 0.50")
        
        if self.max_daily_loss <= 0 or self.max_daily_loss > 0.20:
            raise ValueError("max_daily_loss must be between 0 and 0.20")
        
        if self.max_positions < 1:
            raise ValueError("max_positions must be at least 1")
        
        if self.max_leverage < 1.0 or self.max_leverage > 3.0:
            raise ValueError("max_leverage must be between 1.0 and 3.0")
        
        return True
