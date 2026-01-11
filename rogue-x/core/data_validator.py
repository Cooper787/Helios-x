"""Data validation module for ROGUE-X."""

from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates market data and trading parameters."""
    
    @staticmethod
    def validate_price(price: float, symbol: str = "unknown") -> bool:
        """Validate price data.
        
        Args:
            price: Price value to validate
            symbol: Trading symbol for logging
        
        Returns:
            True if valid
        
        Raises:
            ValueError: If price is invalid
        """
        if not isinstance(price, (int, float)):
            raise ValueError(f"{symbol}: Price must be numeric, got {type(price)}")
        
        if price <= 0:
            raise ValueError(f"{symbol}: Price must be positive, got {price}")
        
        if price > 1e9:  # Sanity check for unreasonably large prices
            raise ValueError(f"{symbol}: Price {price} seems unreasonably large")
        
        return True
    
    @staticmethod
    def validate_quantity(quantity: float, symbol: str = "unknown") -> bool:
        """Validate quantity/size data.
        
        Args:
            quantity: Quantity value to validate
            symbol: Trading symbol for logging
        
        Returns:
            True if valid
        
        Raises:
            ValueError: If quantity is invalid
        """
        if not isinstance(quantity, (int, float)):
            raise ValueError(f"{symbol}: Quantity must be numeric, got {type(quantity)}")
        
        if quantity == 0:
            raise ValueError(f"{symbol}: Quantity cannot be zero")
        
        if abs(quantity) > 1e9:  # Sanity check
            raise ValueError(f"{symbol}: Quantity {quantity} seems unreasonably large")
        
        return True
    
    @staticmethod
    def validate_market_data(data: Dict[str, Any]) -> bool:
        """Validate market data dictionary.
        
        Args:
            data: Market data dictionary
        
        Returns:
            True if valid
        
        Raises:
            ValueError: If data is invalid
        """
        required_fields = ['symbol', 'price', 'volume']
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        symbol = data['symbol']
        
        # Validate symbol
        if not isinstance(symbol, str) or len(symbol) == 0:
            raise ValueError("Symbol must be a non-empty string")
        
        # Validate price
        DataValidator.validate_price(data['price'], symbol)
        
        # Validate volume
        volume = data['volume']
        if not isinstance(volume, (int, float)) or volume < 0:
            raise ValueError(f"{symbol}: Volume must be non-negative numeric")
        
        # Validate optional timestamp
        if 'timestamp' in data:
            timestamp = data['timestamp']
            if not isinstance(timestamp, (datetime, int, float)):
                raise ValueError(f"{symbol}: Timestamp must be datetime or numeric")
        
        return True
    
    @staticmethod
    def validate_order(order: Dict[str, Any]) -> bool:
        """Validate order parameters.
        
        Args:
            order: Order dictionary
        
        Returns:
            True if valid
        
        Raises:
            ValueError: If order is invalid
        """
        required_fields = ['symbol', 'quantity', 'price', 'side']
        
        for field in required_fields:
            if field not in order:
                raise ValueError(f"Missing required order field: {field}")
        
        symbol = order['symbol']
        
        # Validate symbol
        if not isinstance(symbol, str) or len(symbol) == 0:
            raise ValueError("Order symbol must be a non-empty string")
        
        # Validate side
        side = order['side']
        if side not in ['buy', 'sell', 'long', 'short']:
            raise ValueError(f"{symbol}: Invalid order side: {side}")
        
        # Validate price
        DataValidator.validate_price(order['price'], symbol)
        
        # Validate quantity
        DataValidator.validate_quantity(order['quantity'], symbol)
        
        # Validate optional stop loss
        if 'stop_loss' in order and order['stop_loss'] is not None:
            DataValidator.validate_price(order['stop_loss'], symbol)
        
        # Validate optional take profit
        if 'take_profit' in order and order['take_profit'] is not None:
            DataValidator.validate_price(order['take_profit'], symbol)
        
        return True
