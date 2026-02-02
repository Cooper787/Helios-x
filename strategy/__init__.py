"""Strategy: ML-based signal generation"""
__version__ = "0.3.0"
from .indicators import SimpleMovingAverage
from .signals import SignalGenerator

__all__ = ['SimpleMovingAverage', 'SignalGenerator']
