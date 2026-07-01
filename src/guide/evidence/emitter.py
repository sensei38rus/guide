from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from guide.evidence.schemas import GuideEvent

def emit(event: "GuideEvent", config: dict | None = None) -> bool:
    """Emit *event* to the configured sink.

    Args:
        event:  The :class:`~guide.evidence.schemas.GuideEvent` to record.
        config: Guide config dict.  Uses built-in defaults when *None*.

    Returns:
        ``True`` if the event was successfully written, ``False`` otherwise.
        Errors are printed to stderr but never raised — hooks must not fail
        because of evidence writing failures.
    """
    if config is None:
        config = {}

    sink: str = config.get("evidence_sink", "file")
    mock_mode: bool = config.get("mock_mode", True)

    # In mock mode, always write locally regardless of sink setting
    if mock_mode and sink == "webhook":
        sink = "file"

    if sink == "none":
        return True

    if sink == "webhook" and not mock_mode:
        return _emit_webhook(event, config)

    # Default: file sink
    return _emit_file(event, config)



def _resolve_log_path(config: dict) -> Path:
    """Return the absolute path to the JSONL event log."""
    configured = config.get("evidence_path", "")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".guide" / "events.jsonl"


def _emit_file(event: "GuideEvent", config: dict) -> bool:
    """Append a JSONL line to the event log."""
    log_path = _resolve_log_path(config)

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(event.to_jsonl() + "\n")
        return True
    except OSError as exc:
        print(f"[guide] Warning: could not write evidence log: {exc}", file=sys.stderr)
        return False



def _emit_webhook(event: "GuideEvent", config: dict) -> bool:
    """POST event JSON to the configured webhook URL."""
    url = (
        os.environ.get("GUIDE_WEBHOOK_URL")
        or config.get("webhook_url", "")
    )
    if not url:
        print(
            "[guide] Warning: evidence_sink=webhook but no GUIDE_WEBHOOK_URL set.",
            file=sys.stderr,
        )
        return False

    payload = event.to_json().encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status < 300
    except (urllib.error.URLError, OSError) as exc:
        print(f"[guide] Warning: webhook delivery failed: {exc}", file=sys.stderr)
        return False


def read_events(config: dict | None = None) -> list["GuideEvent"]:
    """Read all events from the local JSONL log.

    Returns an empty list when the log does not exist or cannot be parsed.
    Lines that fail to parse are silently skipped.
    """
    from guide.evidence.schemas import GuideEvent

    if config is None:
        config = {}

    log_path = _resolve_log_path(config)
    if not log_path.exists():
        return []

    events: list[GuideEvent] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                events.append(GuideEvent.from_dict(data))
            except (json.JSONDecodeError, TypeError, KeyError):
                print(
                    f"[guide] Warning: skipping malformed line {line_no} in log.",
                    file=sys.stderr,
                )
    return events
