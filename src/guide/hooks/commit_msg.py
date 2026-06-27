"""commit-msg hook.

Git calls this hook as:
    .git/hooks/commit-msg <path-to-commit-msg-file>

Exit codes:
    0 — message is acceptable (or we're in warn-only mode)
    1 — message blocked (only when strictness level is 'block')
"""

from __future__ import annotations

import sys
from pathlib import Path


def run(argv: list[str] | None = None) -> int:
    """Main entry point for the commit-msg hook.

    Args:
        argv: Command-line arguments. Defaults to :data:`sys.argv`.

    Returns:
        Exit code (0 = allow commit, 1 = block commit).
    """
    if argv is None:
        argv = sys.argv

    # ------------------------------------------------------------------ setup
    # Lazy imports so the hook starts fast and fails gracefully if the
    # package is not yet installed.
    try:
        from guide.checks.commit_message import check as check_msg
        from guide.config import load_config, get_strictness
    except ImportError as exc:
        # Can't import guide — let the commit through with a warning
        print(f"[guide] Warning: could not import guide package ({exc})", file=sys.stderr)
        print("[guide] Hook skipped. Run 'make install' to set up Guide.", file=sys.stderr)
        return 0

    # ----------------------------------------------------------- read message
    if len(argv) < 2:
        print("[guide] commit-msg: missing commit message file argument.", file=sys.stderr)
        return 0  # Don't block if we're called incorrectly

    msg_path = Path(argv[1])
    if not msg_path.exists():
        print(f"[guide] commit-msg: file not found: {msg_path}", file=sys.stderr)
        return 0

    raw_message = msg_path.read_text(encoding="utf-8")

    # Strip comment lines (lines starting with #) — Git adds these in templates
    message = "\n".join(
        line for line in raw_message.splitlines() if not line.startswith("#")
    ).strip()

    if not message:
        # Empty message — Git itself will reject this, don't double-warn
        return 0

    # ------------------------------------------------------- run checks
    config = load_config()

    try:
        from guide.checks.rationale import check as check_rationale
        from guide.checks.tests_signal import check as check_tests
        from guide.integrations.git import get_staged_diff
    except ImportError:
        check_rationale = None
        check_tests = None
        get_staged_diff = None

    output_lines: list[str] = []
    all_codes: list[str] = []

    # 1. Commit message format
    msg_result = check_msg(message, config)
    if not msg_result.ok:
        output_lines.extend(str(msg_result).splitlines())
        all_codes.extend(v.code for v in msg_result.violations)

    # 2. Rationale (opt-in via config)
    if check_rationale is not None:
        rat_result = check_rationale(message, config)
        if not rat_result.ok:
            output_lines.extend(str(rat_result).splitlines())
            all_codes.extend(v.code for v in rat_result.violations)

    # 3. Test signal (re-check here in case pre-commit was skipped or
    #    the user added a "no tests because …" note in the message body)
    if check_tests is not None and get_staged_diff is not None:
        diff = get_staged_diff()
        sig_result = check_tests(diff.files, message, config)
        if not sig_result.ok:
            output_lines.extend(str(sig_result).splitlines())
            all_codes.extend(v.code for v in sig_result.violations)

    # ---------------------------------------------------------- evidence
    try:
        from guide.hooks._emit_helper import emit_hook_event
        from guide.checks.rationale import _has_task_ref
        task_ref = ""
        try:
            task_ref = message if _has_task_ref(message) else ""
        except Exception:
            pass
        emit_hook_event(
            hook="commit-msg",
            object_label="commit message",
            violation_codes=all_codes,
            hint_text="\n".join(output_lines),
            config=config,
            task_ref=task_ref,
        )
    except Exception:
        pass

    if not output_lines:
        return 0

    # ---------------------------------------------------------- output
    print("", file=sys.stderr)
    print("┌─ Guide ──────────────────────────────────────────────────────┐", file=sys.stderr)
    for line in output_lines:
        print(f"│  {line}", file=sys.stderr)
    print("└──────────────────────────────────────────────────────────────┘", file=sys.stderr)
    print("", file=sys.stderr)

    strictness = get_strictness(config)
    if strictness == "block":
        print("[guide] Commit blocked. Fix the issues and try again.", file=sys.stderr)
        return 1

    # warn mode — print hint but allow the commit
    print("[guide] Commit allowed (warn mode). Consider improving the message.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(run())
