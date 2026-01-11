#!/usr/bin/env python3
"""Safety check script for ROGUE-X trading system."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import TradingConfig
from core import RiskManager, DataValidator


def run_safety_checks() -> bool:
    """Run all safety checks.
    
    Returns:
        True if all checks pass
    """
    print("=" * 60)
    print("ROGUE-X Trading System Safety Check")
    print("=" * 60)
    
    all_passed = True
    
    # Test 1: Configuration validation
    print("\n[1] Testing configuration validation...")
    try:
        config = TradingConfig()
        config.validate()
        print("✓ Configuration validation passed")
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        all_passed = False
    
    # Test 2: Risk manager initialization
    print("\n[2] Testing risk manager initialization...")
    try:
        config = TradingConfig()
        risk_mgr = RiskManager(config, 100000.0)
        print("✓ Risk manager initialized successfully")
    except Exception as e:
        print(f"✗ Risk manager initialization failed: {e}")
        all_passed = False
    
    # Test 3: Position limits
    print("\n[3] Testing position size limits...")
    try:
        config = TradingConfig(max_position_size=0.02)
        risk_mgr = RiskManager(config, 100000.0)
        
        # Should pass
        can_open, reason = risk_mgr.can_open_position("AAPL", 50, 100.0, 95.0)
        assert can_open, f"Valid position rejected: {reason}"
        
        # Should fail - too large
        can_open, reason = risk_mgr.can_open_position("TSLA", 1000, 300.0, 290.0)
        assert not can_open, "Oversized position was approved"
        
        print("✓ Position size limits working correctly")
    except Exception as e:
        print(f"✗ Position size limit test failed: {e}")
        all_passed = False
    
    # Test 4: Data validation
    print("\n[4] Testing data validation...")
    try:
        # Valid price
        DataValidator.validate_price(100.50, "TEST")
        
        # Invalid prices should fail
        try:
            DataValidator.validate_price(-10, "TEST")
            raise AssertionError("Negative price was accepted")
        except ValueError:
            pass  # Expected
        
        print("✓ Data validation working correctly")
    except Exception as e:
        print(f"✗ Data validation test failed: {e}")
        all_passed = False
    
    # Test 5: Stop loss requirement
    print("\n[5] Testing stop loss requirements...")
    try:
        config = TradingConfig(require_stop_loss=True)
        risk_mgr = RiskManager(config, 100000.0)
        
        # Should fail without stop loss
        can_open, reason = risk_mgr.can_open_position("MSFT", 10, 300.0, None)
        assert not can_open, "Position without stop loss was approved"
        assert "stop loss" in reason.lower()
        
        print("✓ Stop loss requirement enforced")
    except Exception as e:
        print(f"✗ Stop loss requirement test failed: {e}")
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL SAFETY CHECKS PASSED")
        print("=" * 60)
        return True
    else:
        print("✗ SOME SAFETY CHECKS FAILED")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = run_safety_checks()
    sys.exit(0 if success else 1)
