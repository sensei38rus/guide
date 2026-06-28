"""pre-commit hook.

Git calls this hook with no arguments before the commit is created.
The hook inspects the *staged* diff and runs two checks:
  - diff size  (DIFF001, DIFF002)
  - test signal (TEST001)

Exit codes:
    0 — checks passed or we are in warn-only mode
    1 — at least one violation in 'block' strictness mode
"""

from __future__ import annotations

import sys


def run(argv: list[str] | None = None) -> int:
    """Main entry point for the pre-commit hook."""
    if argv is None:
        argv = sys.argv

    try:
        from guide.checks import diff_size, tests_signal
        from guide.config import load_config, get_strictness
        from guide.integrations.git import get_staged_diff
    except ImportError as exc:
        print(f"[guide] Warning: could not import guide package ({exc})", file=sys.stderr)
        print("[guide] Hook skipped. Run 'make install' to set up Guide.", file=sys.stderr)
        return 0

    config = load_config()
    diff = get_staged_diff()

    violations_found = False
    output_lines: list[str] = []
    all_codes: list[str] = []

    # ---------------------------------------------------------------- diff size
    size_result = diff_size.check(diff, config)
    if not size_result.ok:
        violations_found = True
        for v in size_result.violations:
            output_lines.append(str(v))
            all_codes.append(v.code)

    # ---------------------------------------------------------------- test signal
    sig_result = tests_signal.check(diff.files, "", config)
    if not sig_result.ok:
        violations_found = True
        for v in sig_result.violations:
            output_lines.append(str(v))
            all_codes.append(v.code)

    # ---------------------------------------------------------------- evidence
    try:
        from guide.hooks._emit_helper import emit_hook_event
        emit_hook_event(
            hook="pre-commit",
            object_label="staged diff",
            violation_codes=all_codes,
            hint_text="\n".join(output_lines),
            config=config,
        )
    except Exception:
        pass

    if not violations_found:
        return 0

    # ---------------------------------------------------------------- output
    print("", file=sys.stderr)
    print("┌─ Guide ──────────────────────────────────────────────────────┐", file=sys.stderr)
    for line in "\n".join(output_lines).splitlines():
        print(f"│  {line}", file=sys.stderr)
    print("└──────────────────────────────────────────────────────────────┘", file=sys.stderr)
    print("", file=sys.stderr)

    strictness = get_strictness(config)
    if strictness == "block":
        print("[guide] Commit blocked. Fix the issues above and try again.", file=sys.stderr)
        return 1

    print("[guide] Commit allowed (warn mode). Consider addressing the issues above.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(run())
