
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_check_msg(args: argparse.Namespace) -> int:
    from guide.checks.commit_message import check
    from guide.checks.rationale import check as check_rationale
    from guide.config import load_config

    if args.message == "-":
        message = sys.stdin.read()
    elif args.file:
        message = Path(args.file).read_text(encoding="utf-8")
    else:
        message = args.message

    config = load_config()
    ok = True

    result = check(message, config)
    print(result)
    if not result.ok:
        ok = False

    rat_result = check_rationale(message, config)
    if not rat_result.ok:
        print(rat_result)
        ok = False

    return 0 if ok else 1


def _cmd_check_diff(args: argparse.Namespace) -> int:
    from guide.checks import diff_size, tests_signal
    from guide.config import load_config
    from guide.integrations.git import get_staged_diff

    config = load_config()

    # Allow CLI overrides for quick ad-hoc checks
    if args.lines is not None:
        config.setdefault("diff", {})["max_lines"] = args.lines
    if args.files is not None:
        config.setdefault("diff", {})["max_files"] = args.files

    diff = get_staged_diff()
    ok = True

    size_result = diff_size.check(diff, config)
    print(size_result)
    if not size_result.ok:
        ok = False

    msg = args.message or ""
    sig_result = tests_signal.check(diff.files, msg, config)
    print(sig_result)
    if not sig_result.ok:
        ok = False

    return 0 if ok else 1


def _cmd_log(args: argparse.Namespace) -> int:
    from guide.config import load_config
    from guide.evidence.emitter import read_events
    from guide.evidence.schemas import Action
    from collections import Counter
    import json as _json

    config = load_config()
    events = read_events(config)

    if not events:
        print("No events found in the log.")
        print(f"  Log path: {_resolve_log_path_str(config)}")
        return 0

    if args.json:
        print(_json.dumps([e.to_dict() for e in events], ensure_ascii=False, indent=2))
        return 0

    # ---- summary view -------------------------------------------------------
    total = len(events)
    action_counts = Counter(e.action for e in events)
    prompted = [e for e in events if e.action == Action.PROMPTED]
    blocked  = [e for e in events if e.action == Action.BLOCKED]
    checked  = [e for e in events if e.action == Action.CHECKED]

    # Top violation codes across all prompted/blocked events
    code_counts: Counter = Counter()
    for e in events:
        code_counts.update(e.violation_codes)

    print(f"\nGuide event log — {total} event(s)\n")
    print(f"  {'Action':<20} {'Count':>6}")
    print(f"  {'-'*20} {'------':>6}")
    for action, count in sorted(action_counts.items()):
        short = action.replace("guide.", "")
        print(f"  {short:<20} {count:>6}")

    if code_counts:
        print(f"\n  Top violation codes:")
        for code, count in code_counts.most_common(10):
            print(f"    {code:<12} {count:>4}×")

    if args.verbose and prompted:
        print(f"\n  Recent hints ({min(5, len(prompted))} of {len(prompted)}):")
        for e in prompted[-5:]:
            ts = e.timestamp[:19].replace("T", " ")
            codes_str = ", ".join(e.violation_codes) or "—"
            print(f"    [{ts}] {e.hook:<12} {codes_str}")

    print(f"\n  Log: {_resolve_log_path_str(config)}\n")
    return 0


def _cmd_profile(args: argparse.Namespace) -> int:
    from guide.config import load_config
    from guide.profile import load_profile, save_profile, profile_summary, UserProfile
    import json as _json

    config = load_config()

    if args.reset:
        save_profile(UserProfile(), config)
        print("Profile reset.")
        return 0

    profile = load_profile(config)
    rows = profile_summary(profile)

    if not rows:
        print("No profile data yet. Make some commits to build a profile.")
        return 0

    if args.json:
        print(_json.dumps(profile.to_dict(), ensure_ascii=False, indent=2))
        return 0

    threshold = config.get("strictness", {}).get("adaptive_threshold", 5)
    print(f"\nGuide adaptive profile  (quiet threshold: {threshold} consecutive passes)\n")
    print(f"  {'Code':<12} {'Streak':>6} {'Passes':>7} {'Triggers':>9} {'Status'}")
    print(f"  {'-'*12} {'------':>6} {'-------':>7} {'---------':>9} {'------'}")
    for row in rows:
        status = "🔇 quiet" if row["quiet"] else "active"
        streak_bar = "●" * min(row["streak"], threshold) + "○" * max(0, threshold - row["streak"])
        print(
            f"  {row['code']:<12} {row['streak']:>6} {row['total_passes']:>7} "
            f"{row['total_triggers']:>9}   {status}  {streak_bar}"
        )
    print()


def _resolve_log_path_str(config: dict) -> str:
    from guide.evidence.emitter import _resolve_log_path
    return str(_resolve_log_path(config))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guide",
        description="Guide — git-hook mentorship tool (manual check runner)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- check-msg ----------------------------------------------------------
    msg_parser = sub.add_parser(
        "check-msg",
        help="Validate a commit message against configured rules.",
    )
    msg_group = msg_parser.add_mutually_exclusive_group(required=False)
    msg_group.add_argument(
        "message",
        nargs="?",
        default="-",
        help="Commit message text. Use '-' to read from stdin (default).",
    )
    msg_group.add_argument(
        "--file", "-f",
        metavar="PATH",
        help="Read commit message from a file (e.g. .git/COMMIT_EDITMSG).",
    )

    # ---- check-diff ---------------------------------------------------------
    diff_parser = sub.add_parser(
        "check-diff",
        help="Check the currently staged diff for size and test signal.",
    )
    diff_parser.add_argument(
        "--lines", type=int, default=None,
        help="Override max_lines threshold for this run.",
    )
    diff_parser.add_argument(
        "--files", type=int, default=None,
        help="Override max_files threshold for this run.",
    )
    diff_parser.add_argument(
        "--message", "-m", default=None,
        help="Commit message to include in test-signal check (body keywords).",
    )

    # ---- log ----------------------------------------------------------------
    log_parser = sub.add_parser(
        "log",
        help="Show a summary of Guide events from the local evidence log.",
    )
    log_parser.add_argument(
        "--json", action="store_true",
        help="Output raw JSON array of all events.",
    )
    log_parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show recent individual hint events.",
    )

    # ---- profile ------------------------------------------------------------
    profile_parser = sub.add_parser(
        "profile",
        help="Show or reset the adaptive hint profile.",
    )
    profile_parser.add_argument(
        "--json", action="store_true",
        help="Output raw JSON profile.",
    )
    profile_parser.add_argument(
        "--reset", action="store_true",
        help="Reset all streak counters to zero.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "check-msg":
        return _cmd_check_msg(args)
    if args.command == "check-diff":
        return _cmd_check_diff(args)
    if args.command == "log":
        return _cmd_log(args)
    if args.command == "profile":
        return _cmd_profile(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
