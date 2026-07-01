#!/usr/bin/env python3


from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Bootstrap: add src/ to path so we can import guide without installing
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_SRC = _SCRIPT_DIR.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _load_events(since: str | None = None):
    from guide.config import load_config
    from guide.evidence.emitter import read_events

    config = load_config()
    events = read_events(config)

    if since:
        try:
            cutoff = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
            events = [
                e for e in events
                if datetime.fromisoformat(e.timestamp) >= cutoff
            ]
        except ValueError:
            print(f"Warning: could not parse --since date '{since}', ignoring.", file=sys.stderr)

    return events, config


def _build_summary(events) -> dict:
    from guide.evidence.schemas import Action

    total = len(events)
    action_counts = Counter(e.action for e in events)
    code_counts: Counter = Counter()
    hook_counts: Counter = Counter()

    for e in events:
        code_counts.update(e.violation_codes)
        if e.hook:
            hook_counts[e.hook] += 1

    prompted_count = action_counts.get(Action.PROMPTED, 0)
    blocked_count  = action_counts.get(Action.BLOCKED, 0)
    checked_count  = action_counts.get(Action.CHECKED, 0)
    corrected_count = action_counts.get(Action.CORRECTED, 0)

    correction_rate = (
        round(corrected_count / prompted_count, 2)
        if prompted_count > 0 else None
    )

    recent_hints = [
        {
            "timestamp": e.timestamp,
            "hook": e.hook,
            "codes": e.violation_codes,
            "hint_preview": e.hint_shown[:120] if e.hint_shown else "",
        }
        for e in events
        if e.action in (Action.PROMPTED, Action.BLOCKED)
    ][-10:]

    return {
        "total_events": total,
        "actions": {
            "checked":   checked_count,
            "prompted":  prompted_count,
            "blocked":   blocked_count,
            "corrected": corrected_count,
        },
        "correction_rate": correction_rate,
        "top_violations": code_counts.most_common(10),
        "by_hook": dict(hook_counts),
        "recent_hints": recent_hints,
    }


def _print_text(summary: dict, log_path: str) -> None:
    sep = "─" * 50

    print(f"\n{'Guide — mentor summary':^50}")
    print(sep)

    print(f"\n  Total events : {summary['total_events']}")
    print()

    # Action breakdown
    a = summary["actions"]
    print(f"  {'Action':<16} {'Count':>6}")
    print(f"  {'-'*16} {'------':>6}")
    for name, count in a.items():
        print(f"  {name:<16} {count:>6}")

    rate = summary["correction_rate"]
    if rate is not None:
        pct = int(rate * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\n  Correction rate : {bar} {pct}%")
        print(f"  (user fixed issue after hint: {a['corrected']} of {a['prompted']})")

    # Violations
    if summary["top_violations"]:
        print(f"\n  Top violation codes:")
        for code, count in summary["top_violations"]:
            bar = "▪" * min(count, 20)
            print(f"    {code:<10} {count:>3}×  {bar}")

    # By hook
    if summary["by_hook"]:
        print(f"\n  Events by hook:")
        for hook, count in sorted(summary["by_hook"].items()):
            print(f"    {hook:<16} {count:>4}")

    # Recent hints
    if summary["recent_hints"]:
        print(f"\n  Recent hints (last {len(summary['recent_hints'])}):")
        for h in summary["recent_hints"]:
            ts = h["timestamp"][:19].replace("T", " ")
            codes = ", ".join(h["codes"]) if h["codes"] else "—"
            hook  = (h["hook"] or "?")[:12]
            print(f"    [{ts}] {hook:<13} {codes}")
            if h["hint_preview"]:
                preview = h["hint_preview"].splitlines()[0][:60]
                print(f"      {preview}")

    print(f"\n  Log: {log_path}")
    print(sep + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export Guide evidence log as a mentor summary.",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output raw JSON instead of plain text.",
    )
    parser.add_argument(
        "--since", metavar="YYYY-MM-DD", default=None,
        help="Only include events on or after this date (UTC).",
    )
    args = parser.parse_args(argv)

    events, config = _load_events(since=args.since)

    if not events:
        print("No events found in the log.")
        return 0

    summary = _build_summary(events)

    from guide.evidence.emitter import _resolve_log_path
    log_path = str(_resolve_log_path(config))

    if args.json:
        print(json.dumps({**summary, "log_path": log_path}, ensure_ascii=False, indent=2))
    else:
        _print_text(summary, log_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
