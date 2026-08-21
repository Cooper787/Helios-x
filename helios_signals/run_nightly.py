"""Nightly entrypoint.

    python -m helios_signals.run_nightly --dry-run

Exit codes:
    0  run completed and was healthy
    1  run completed but degraded (a source failed; no signals were issued)
    2  fatal error

Distinct codes matter: GitHub Actions marks the job red on non-zero, and a
degraded run must be visibly different from a clean one. This repository has
already run a scheduled job that failed ~195 consecutive times without anyone
noticing, because the failure path was never exercised.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from .config import AccountConfig, SignalConfig
from .engine import SignalEngine
from .ledger import RunLedger
from .notify.telegram import TelegramNotifier
from .sources.base import HttpJsonClient
from .sources.clinicaltrials import ClinicalTrialsSource
from .sources.sec import CompanyFactsSource, TickerResolver

logger = logging.getLogger("helios_signals")


def build_engine(config: SignalConfig, account: AccountConfig) -> SignalEngine:
    client = HttpJsonClient(
        user_agent=config.user_agent,
        timeout_s=config.request_timeout_s,
        max_retries=config.max_retries,
    )
    return SignalEngine(
        catalysts_source=ClinicalTrialsSource(client),
        resolver=TickerResolver(client),
        facts=CompanyFactsSource(client),
        config=config,
        account=account,
        price_lookup=None,  # no free price source wired yet; see design doc
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Helios-X nightly signal run")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render Telegram messages without sending. Implied when no bot token is set.",
    )
    parser.add_argument("--as-of", type=str, default=None, help="Override date (YYYY-MM-DD)")
    parser.add_argument("--ledger", type=Path, default=Path("ledger/runs.jsonl"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()

    config = SignalConfig.from_env()
    account = AccountConfig()
    notifier = TelegramNotifier()

    dry_run = args.dry_run or not notifier.configured
    logger.info(
        "Helios-X nightly | as_of=%s | telegram=%s | dry_run=%s",
        as_of, notifier.mode, dry_run,
    )

    try:
        engine = build_engine(config, account)
        report = engine.run(as_of=as_of, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fatal error during run")
        print(f"\nFATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    ledger = RunLedger(args.ledger)
    ledger.append(report)
    ledger.write_latest(report)

    deliveries = notifier.dispatch_run(report)
    failed = [d for d in deliveries if not d.ok]

    print("\n" + "=" * 68)
    print(f"Helios-X nightly — {report.run_id}")
    print("=" * 68)
    print(f"  healthy            : {report.healthy}")
    print(f"  telegram           : {notifier.mode}")
    print(f"  catalysts scanned  : {report.catalysts_found}")
    print(f"  in entry window    : {report.catalysts_in_window}")
    print(f"  signals            : {len(report.signals)}")
    print(f"  vetoed             : {len(report.vetoes)}")
    print("  sources:")
    for s in report.sources:
        print(
            f"    - {s.name}: {'ok' if s.ok else 'FAIL'} "
            f"({s.records} records, {s.elapsed_ms}ms)"
            + (f"\n        {s.error}" if s.error else "")
        )
    if failed:
        print("  telegram delivery failures:")
        for d in failed:
            print(f"    - {d.error}")
    print("=" * 68 + "\n")

    if report.fatal_error:
        return 2
    if not report.healthy or failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
