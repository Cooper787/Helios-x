# Run ledger

Append-only record of every nightly run: what Helios saw, what it recommended,
and what it refused.

- `runs.jsonl` — one JSON object per run, appended, never rewritten
- `latest.json` — the most recent run, pretty-printed

Git is the tamper-evidence mechanism. Each run lands as a timestamped commit,
so the record of what was recommended and when cannot be quietly revised after
the outcome is known. A track record that can be edited afterwards demonstrates
nothing; this one can be independently verified against the commit history.
