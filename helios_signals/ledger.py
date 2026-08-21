"""Append-only run ledger, committed to git.

Git is the tamper-evidence mechanism: each run is a timestamped commit, so the
record of what Helios recommended and when cannot be quietly revised after the
fact. That property is the point. The project's stated ambition is to be
verifiably trustworthy rather than merely profitable-looking, and a track
record that can be edited afterwards demonstrates nothing.

JSONL rather than a database, deliberately: a database is mutable, lives
somewhere else, and cannot be diffed by a human.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

from .models import RunReport

logger = logging.getLogger(__name__)

DEFAULT_LEDGER = Path("ledger/runs.jsonl")


class RunLedger:
    def __init__(self, path: Path = DEFAULT_LEDGER) -> None:
        self.path = Path(path)

    def append(self, report: RunReport) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(report.to_dict(), sort_keys=True, default=str)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        logger.info("Ledger appended: %s (%s)", self.path, report.run_id)
        return self.path

    def read(self) -> Iterator[dict]:
        if not self.path.exists():
            return iter(())

        def _gen() -> Iterator[dict]:
            with self.path.open("r", encoding="utf-8") as fh:
                for num, raw in enumerate(fh, 1):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        yield json.loads(raw)
                    except json.JSONDecodeError:
                        # Never let one corrupt line hide the rest of the record.
                        logger.error("Ledger line %d is not valid JSON; skipping", num)

        return _gen()

    def write_latest(self, report: RunReport, path: Path = Path("ledger/latest.json")) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        return path
