"""Signal generation from indicators"""
from .indicators import SimpleMovingAverage

class SignalGenerator:
    """Generate buy/sell signals from price data"""
    def __init__(self, sma_period: int = 20):
        self.sma = SimpleMovingAverage(sma_period)
    
    def generate(self, prices: list, current_price: float) -> str:
        """Generate signal (buy/sell/hold)"""
        sma_value = self.sma.calculate(prices)
        if current_price > sma_value * 1.02:
            return 'buy'
        elif current_price < sma_value * 0.98:
            return 'sell'
        return 'hold'
