"""Episodic memory for trade history"""
from .persistence import MemoryStore

class EpisodicMemory:
    """Memory of specific events/trades"""
    def __init__(self):
        self.store = MemoryStore("memory/episodes.jsonl")
    
    def record_trade(self, symbol: str, qty: int, price: float, side: str) -> None:
        """Record a trade event"""
        self.store.append({
            'event_type': 'trade',
            'symbol': symbol,
            'qty': qty,
            'price': price,
            'side': side
        })
