"""JSONL persistence layer for memory"""
import json
from pathlib import Path
from typing import Any, Dict
from datetime import datetime
import hashlib

class MemoryStore:
    """Append-only JSONL memory store"""
    def __init__(self, path: str = "memory/store.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    
    def append(self, record: Dict[str, Any]) -> None:
        """Append record with timestamp and hash"""
        record['timestamp'] = datetime.utcnow().isoformat()
        record['hash'] = hashlib.sha256(str(record).encode()).hexdigest()[:16]
        with open(self.path, 'a') as f:
            f.write(json.dumps(record) + '\n')
    
    def tail(self, n: int = 100) -> list:
        """Get last n records"""
        if not self.path.exists():
            return []
        lines = self.path.read_text().strip().split('\n')
        return [json.loads(l) for l in lines[-n:] if l]
