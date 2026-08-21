"""Telegram dispatch, with a dry-run mode that needs no bot.

The pipeline must be fully verifiable before a bot exists. With no
TELEGRAM_BOT_TOKEN configured the dispatcher renders every message and writes
it to stdout and to the run artifact, reporting exactly what *would* have been
sent. That makes "does the nightly job work" answerable without creating
credentials first.

When a token is present, delivery failures are surfaced, never swallowed. A
notifier that fails quietly is worse than no notifier: this repository already
ran a scheduled job that failed ~195 times in a row without a single alert,
because the alerting path itself had never been tested.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

from ..models import RunReport, Signal

logger = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 4096


def _esc(text: str) -> str:
    """Escape HTML special characters for Telegram's HTML parse mode."""
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def render_signal(signal: Signal) -> str:
    c = signal.catalyst
    days = c.days_until(__import__("datetime").date.today())

    lines = [
        f"<b>{_esc(signal.decision.value.upper())} {_esc(signal.ticker)}</b>",
        "",
        f"<b>Catalyst:</b> {_esc(c.event_type.value.replace('_', ' '))} in {days}d "
        f"({_esc(c.event_date.isoformat())})",
        f"<b>Trial:</b> {_esc(c.external_id)}",
    ]
    if c.conditions:
        lines.append(f"<b>Indication:</b> {_esc(', '.join(c.conditions[:2]))}")
    if c.intervention_names:
        lines.append(f"<b>Asset:</b> {_esc(', '.join(c.intervention_names[:2]))}")

    lines.append("")
    if signal.entry_price is not None:
        lines.append(f"<b>Entry:</b> ${signal.entry_price:,.2f}")
    if signal.quantity is not None and signal.position_value is not None:
        lines.append(
            f"<b>Size:</b> {signal.quantity:g} sh (~${signal.position_value:,.2f})"
        )
    if signal.stop_loss is not None:
        lines.append(f"<b>Stop:</b> ${signal.stop_loss:,.2f}")
    if signal.exit_by is not None:
        lines.append(f"<b>HARD EXIT BY:</b> {_esc(signal.exit_by.isoformat())}")

    lines += ["", f"<i>{_esc(signal.reason)}</i>"]

    if signal.caveats:
        lines.append("")
        lines.append("<b>Caveats</b>")
        for cav in signal.caveats:
            lines.append(f"• {_esc(cav)}")

    lines += [
        "",
        "<i>Advisory only. You place the order. Not investment advice.</i>",
    ]
    return "\n".join(lines)[:MAX_LEN]


def render_run_summary(report: RunReport) -> str:
    status = "OK" if report.healthy else "DEGRADED"
    lines = [
        f"<b>Helios-X nightly — {_esc(status)}</b>",
        f"<code>{_esc(report.run_id)}</code>",
        "",
        f"Catalysts scanned: {report.catalysts_found}",
        f"In entry window: {report.catalysts_in_window}",
        f"Signals: {len(report.signals)}",
        f"Vetoed: {len(report.vetoes)}",
        "",
        "<b>Sources</b>",
    ]
    for s in report.sources:
        mark = "ok" if s.ok else "FAIL"
        lines.append(f"• {_esc(s.name)}: {mark}, {s.records} rec, {s.elapsed_ms}ms")
        if s.error:
            lines.append(f"  <i>{_esc(s.error[:200])}</i>")

    if report.fatal_error:
        lines += ["", f"<b>FATAL:</b> {_esc(report.fatal_error[:400])}"]

    if not report.healthy:
        lines += [
            "",
            "<b>No signals were issued.</b> A source failed, so the run is not "
            "trustworthy and the pipeline failed closed.",
        ]

    if report.dry_run:
        lines += ["", "<i>DRY RUN — nothing was sent to a live chat.</i>"]

    return "\n".join(lines)[:MAX_LEN]


@dataclass
class Delivery:
    ok: bool
    text: str
    error: Optional[str] = None
    dry_run: bool = False


class TelegramNotifier:
    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout_s: int = 20,
    ) -> None:
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN") or ""
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID") or ""
        self.timeout_s = timeout_s

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    @property
    def mode(self) -> str:
        return "live" if self.configured else "dry-run"

    def send(self, text: str) -> Delivery:
        if not self.configured:
            missing = []
            if not self.token:
                missing.append("TELEGRAM_BOT_TOKEN")
            if not self.chat_id:
                missing.append("TELEGRAM_CHAT_ID")
            logger.info("DRY RUN (missing %s) — would send:\n%s", ", ".join(missing), text)
            return Delivery(ok=True, text=text, dry_run=True)

        payload = urllib.parse.urlencode(
            {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
        ).encode()

        try:
            req = urllib.request.Request(
                API.format(token=self.token),
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if not body.get("ok"):
                return Delivery(False, text, f"Telegram API returned ok=false: {body}")
            return Delivery(True, text)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            return Delivery(False, text, f"HTTP {exc.code}: {detail}")
        except Exception as exc:  # noqa: BLE001 - notifier must never crash the run
            return Delivery(False, text, f"{type(exc).__name__}: {exc}")

    def dispatch_run(self, report: RunReport) -> List[Delivery]:
        """Always send the summary; send signals only if the run is healthy."""
        deliveries = [self.send(render_run_summary(report))]
        if report.healthy:
            for sig in report.signals:
                deliveries.append(self.send(render_signal(sig)))
        return deliveries
