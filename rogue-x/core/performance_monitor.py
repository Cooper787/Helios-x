"""Performance monitoring module for ROGUE-X."""

from typing import Dict, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitors and tracks trading performance metrics."""
    
    def __init__(self):
        """Initialize performance monitor."""
        self.trades: List[Dict] = []
        self.daily_pnl: Dict[str, float] = {}
        logger.info("PerformanceMonitor initialized")
    
    def record_trade(self, trade: Dict) -> None:
        """Record a completed trade.
        
        Args:
            trade: Trade details including PnL
        """
        self.trades.append({
            **trade,
            'timestamp': datetime.now()
        })
        
        # Update daily PnL
        date_key = datetime.now().strftime('%Y-%m-%d')
        if date_key not in self.daily_pnl:
            self.daily_pnl[date_key] = 0.0
        
        if 'pnl' in trade:
            self.daily_pnl[date_key] += trade['pnl']
        
        logger.info(f"Trade recorded: {trade.get('symbol', 'unknown')}")
    
    def get_win_rate(self, days: int = 30) -> float:
        """Calculate win rate over specified period.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Win rate as percentage
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_trades = [
            t for t in self.trades
            if t.get('timestamp', datetime.min) > cutoff
        ]
        
        if not recent_trades:
            return 0.0
        
        wins = sum(1 for t in recent_trades if t.get('pnl', 0) > 0)
        return (wins / len(recent_trades)) * 100
    
    def get_total_pnl(self) -> float:
        """Get total profit/loss.
        
        Returns:
            Total PnL
        """
        return sum(t.get('pnl', 0) for t in self.trades)
    
    def get_daily_summary(self) -> Dict:
        """Get today's performance summary.
        
        Returns:
            Dictionary with daily metrics
        """
        date_key = datetime.now().strftime('%Y-%m-% d')
        return {
            'date': date_key,
            'pnl': self.daily_pnl.get(date_key, 0.0),
            'trades': len([t for t in self.trades
                          if t.get('timestamp', datetime.min).strftime('%Y-%m-%d') == date_key])
        }
