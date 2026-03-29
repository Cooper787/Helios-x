"""Natural language command parser"""
import re
from typing import Dict, Any, Optional

class CommandParser:
    """Parse natural language trading commands"""
    
    def __init__(self):
        self.commands = {
            'buy': self._parse_buy,
            'sell': self._parse_sell,
            'status': self._parse_status,
            'stop': self._parse_stop,
        }
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse command text to structured dict"""
        text = text.lower().strip()
        for cmd, parser in self.commands.items():
            if cmd in text:
                return parser(text)
        return {'error': 'Unknown command'}
    
    def _parse_buy(self, text: str) -> Dict[str, Any]:
        match = re.search(r'buy\s+(\d+)\s+(\w+)', text)
        if match:
            return {'action': 'buy', 'qty': int(match.group(1)), 'symbol': match.group(2).upper()}
        return {'error': 'Invalid buy command'}
    
    def _parse_sell(self, text: str) -> Dict[str, Any]:
        match = re.search(r'sell\s+(\d+)\s+(\w+)', text)
        if match:
            return {'action': 'sell', 'qty': int(match.group(1)), 'symbol': match.group(2).upper()}
        return {'error': 'Invalid sell command'}
    
    def _parse_status(self, text: str) -> Dict[str, Any]:
        return {'action': 'status'}
    
    def _parse_stop(self, text: str) -> Dict[str, Any]:
        return {'action': 'stop'}
