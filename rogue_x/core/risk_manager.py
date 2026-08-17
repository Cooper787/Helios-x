"""Risk management module for ROGUE-X with comprehensive safety checks."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..config import TradingConfig

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    @property
    def value(self) -> float:
        """Current position value."""
        return abs(self.quantity * self.current_price)

    @property
    def pnl(self) -> float:
        """Current profit/loss."""
        return (self.current_price - self.entry_price) * self.quantity


class RiskManager:
    """Manages trading risk with multiple safety layers."""

    def __init__(self, config: TradingConfig, initial_capital: float):
        """Initialize risk manager.

        Args:
            config: Trading configuration
            initial_capital: Starting capital amount

        Raises:
            ValueError: If initial_capital is not positive
        """
        # SAFETY FIX #1: Validate initial capital
        if initial_capital <= 0:
            raise ValueError("Initial capital must be positive")

        self.config = config
        self.config.validate()  # SAFETY FIX #2: Validate config on init

        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.daily_start_capital = initial_capital
        self.peak_capital = initial_capital
        self.bars_seen = 0
        self.trading_halted = False
        self.halt_reason: Optional[str] = None

        logger.info(f"RiskManager initialized with capital: ${initial_capital:.2f}")

    @property
    def equity(self) -> float:
        """Current capital plus unrealized PnL on open positions."""
        return self.current_capital + sum(pos.pnl for pos in self.positions.values())

    def record_bar(self) -> None:
        """Record that one bar of market data has been observed (warmup tracking)."""
        self.bars_seen += 1

    def halt_trading(self, reason: str) -> None:
        """Latch the trading halt. Requires explicit human reset_halt() to resume."""
        if not self.trading_halted:
            self.trading_halted = True
            self.halt_reason = reason
            logger.critical(f"TRADING HALTED: {reason}")

    def reset_halt(self) -> None:
        """Manually clear a trading halt (human decision only)."""
        logger.warning(f"Trading halt manually reset (was: {self.halt_reason})")
        self.trading_halted = False
        self.halt_reason = None

    def check_circuit_breaker(self) -> bool:
        """Check equity drawdown from peak against max_drawdown; halt if breached.

        Returns:
            True if the circuit breaker is tripped (trading halted).
        """
        # SAFETY: Peak tracks the highest equity seen; drawdown includes unrealized PnL.
        self.peak_capital = max(self.peak_capital, self.equity)
        if self.peak_capital <= 0:
            self.halt_trading("Peak capital is non-positive")
            return True
        drawdown = (self.peak_capital - self.equity) / self.peak_capital
        if drawdown >= self.config.max_drawdown:
            self.halt_trading(
                f"Circuit breaker: drawdown {drawdown*100:.1f}% >= limit {self.config.max_drawdown*100:.1f}%"
            )
        return self.trading_halted

    def can_open_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        stop_loss: Optional[float] = None
    ) -> tuple[bool, str]:
        """Check if a position can be opened safely.

        Args:
            symbol: Trading symbol
            quantity: Position size
            price: Entry price
            stop_loss: Stop loss price

        Returns:
            Tuple of (can_open, reason)
        """
        # SAFETY: Circuit breaker / manual halt gate
        if self.check_circuit_breaker():
            return False, f"Trading halted: {self.halt_reason}"

        # SAFETY: Warmup gate - no positions until enough data has been observed
        if self.bars_seen < self.config.warmup_bars:
            return False, (
                f"Warmup incomplete: {self.bars_seen}/{self.config.warmup_bars} bars observed"
            )

        # SAFETY FIX #3: Validate inputs
        if quantity == 0:
            return False, "Quantity cannot be zero"

        # SAFETY: Long-only unless shorting is explicitly enabled in config
        if quantity < 0 and not self.config.allow_short:
            return False, "Short selling is disabled (config.allow_short=False)"

        if price <= 0:
            return False, "Price must be positive"

        # SAFETY FIX #4: Check position limits
        if len(self.positions) >= self.config.max_positions:
            return False, f"Maximum {self.config.max_positions} positions reached"

        # SAFETY FIX #5: Check if position already exists
        if symbol in self.positions:
            return False, f"Position already exists for {symbol}"

        # SAFETY FIX #6: Calculate position size
        position_value = abs(quantity * price)
        max_position_value = self.current_capital * self.config.max_position_size

        if position_value > max_position_value:
            return False, f"Position size ${position_value:.2f} exceeds limit ${max_position_value:.2f}"

        # SAFETY FIX #7: Check portfolio risk
        total_exposure = sum(pos.value for pos in self.positions.values())
        new_total_exposure = total_exposure + position_value
        max_exposure = self.current_capital * self.config.max_portfolio_risk

        if new_total_exposure > max_exposure:
            return False, f"Total exposure ${new_total_exposure:.2f} would exceed limit ${max_exposure:.2f}"

        # SAFETY FIX #8: Validate stop loss requirement
        if self.config.require_stop_loss and stop_loss is None:
            return False, "Stop loss is required but not provided"

        # SAFETY FIX #9: Validate stop loss value
        if stop_loss is not None:
            if quantity > 0 and stop_loss >= price:
                return False, "Stop loss must be below entry price for long positions"
            if quantity < 0 and stop_loss <= price:
                return False, "Stop loss must be above entry price for short positions"

        # SAFETY FIX #10: Check daily loss limit (realized + unrealized)
        unrealized = sum(pos.pnl for pos in self.positions.values())
        effective_daily_pnl = self.daily_pnl + unrealized
        if effective_daily_pnl < 0:
            daily_loss_pct = abs(effective_daily_pnl / self.daily_start_capital)
            if daily_loss_pct >= self.config.max_daily_loss:
                return False, f"Daily loss limit {self.config.max_daily_loss*100}% reached (incl. unrealized)"

        # SAFETY FIX #11: Check available capital
        if position_value > self.current_capital:
            return False, f"Insufficient capital: ${self.current_capital:.2f} available, ${position_value:.2f} required"

        return True, "Position approved"

    def open_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """Open a new position with safety checks.

        Args:
            symbol: Trading symbol
            quantity: Position size
            price: Entry price
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price

        Returns:
            True if position opened successfully
        """
        # SAFETY FIX #12: Pre-flight checks
        can_open, reason = self.can_open_position(symbol, quantity, price, stop_loss)

        if not can_open:
            logger.warning(f"Cannot open position for {symbol}: {reason}")
            return False

        # Create position
        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=price,
            current_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        self.positions[symbol] = position
        logger.info(f"Opened position: {symbol} qty={quantity} @ ${price:.2f}")

        return True

    def close_position(self, symbol: str, price: float) -> Optional[float]:
        """Close an existing position.

        Args:
            symbol: Trading symbol
            price: Exit price

        Returns:
            Realized PnL or None if position doesn't exist
        """
        if symbol not in self.positions:
            logger.warning(f"Cannot close non-existent position: {symbol}")
            return None

        position = self.positions[symbol]
        pnl = (price - position.entry_price) * position.quantity

        # Update capital and daily PnL
        self.current_capital += pnl
        self.daily_pnl += pnl

        # Remove position
        del self.positions[symbol]

        logger.info(f"Closed position: {symbol} @ ${price:.2f}, PnL: ${pnl:.2f}")

        # SAFETY: Re-evaluate circuit breaker after every realized PnL change.
        self.check_circuit_breaker()

        return pnl

    def update_position_price(self, symbol: str, price: float) -> None:
        """Update current price for a position.

        Args:
            symbol: Trading symbol
            price: Current market price
        """
        if symbol in self.positions:
            self.positions[symbol].current_price = price
            # SAFETY: Mark-to-market moves can breach the drawdown limit.
            self.check_circuit_breaker()

    def check_stop_losses(self) -> List[str]:
        """Check if any positions have hit their stop losses.

        Returns:
            List of symbols that hit stop losses
        """
        # SAFETY FIX #13: Automatic stop loss enforcement
        hit_stops = []

        for symbol, position in list(self.positions.items()):
            if position.stop_loss is None:
                continue

            # Check long position
            if position.quantity > 0 and position.current_price <= position.stop_loss:
                logger.warning(f"Stop loss hit for {symbol}: ${position.current_price:.2f} <= ${position.stop_loss:.2f}")
                hit_stops.append(symbol)
                # SAFETY: Fill at current market price (conservative), not the stop price.
                self.close_position(symbol, position.current_price)

            # Check short position
            elif position.quantity < 0 and position.current_price >= position.stop_loss:
                logger.warning(f"Stop loss hit for {symbol}: ${position.current_price:.2f} >= ${position.stop_loss:.2f}")
                hit_stops.append(symbol)
                # SAFETY: Fill at current market price (conservative), not the stop price.
                self.close_position(symbol, position.current_price)

        return hit_stops

    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary.

        Returns:
            Dictionary with portfolio metrics
        """
        total_value = sum(pos.value for pos in self.positions.values())
        total_pnl = sum(pos.pnl for pos in self.positions.values())

        return {
            'capital': self.current_capital,
            'equity': self.equity,
            'peak_capital': self.peak_capital,
            'trading_halted': self.trading_halted,
            'halt_reason': self.halt_reason,
            'bars_seen': self.bars_seen,
            'positions': len(self.positions),
            'total_exposure': total_value,
            'unrealized_pnl': total_pnl,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': self.daily_pnl / self.daily_start_capital * 100
        }

    def reset_daily_metrics(self) -> None:
        """Reset daily tracking metrics (call at start of trading day)."""
        self.daily_pnl = 0.0
        self.daily_start_capital = self.current_capital
        logger.info("Daily metrics reset")
