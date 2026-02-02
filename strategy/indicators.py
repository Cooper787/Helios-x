"""Technical indicators for strategy"""
from typing import List

class SimpleMovingAverage:
    """Calculate SMA from price list"""
    def __init__(self, period: int = 20):
        self.period = period
    
    def calculate(self, prices: List[float]) -> float:
        """Calculate SMA"""
        if len(prices) < self.period:
            return sum(prices) / len(prices) if prices else 0
        return sum(prices[-self.period:]) / self.period
