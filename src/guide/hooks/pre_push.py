
from __future__ import annotations

import sys


def run(argv: list[str] | None = None) -> int:
    """Main entry point for the pre-push hook."""
    if argv is None:
        argv = sys.argv

    try:
        from guide.config import load_config, get_strictness
        from guide.integrations.git import get_push_info, parse_pre_push_stdin
    except ImportError as exc:
        print(f"[guide] Warning: could not import guide package ({exc})", file=sys.stderr)
        print("[guide] Hook skipped. Run 'make install' to set up Guide.", file=sys.stderr)
        return 0

    # ----------------------------------------------------------------- args
    remote_name = argv[1] if len(argv) > 1 else "origin"
    remote_url  = argv[2] if len(argv) > 2 else ""

    stdin_text = sys.stdin.read()
    refs = parse_pre_push_stdin(stdin_text)

    if not refs:
        # Nothing being pushed (e.g. only tag deletion)
        return 0

    # ----------------------------------------------------------------- data
    config = load_config()
    push_info = get_push_info(remote_name, remote_url, refs)

    cfg = config.get("diff", {})
    max_push_lines: int = cfg.get("max_push_lines", cfg.get("max_lines", 200) * 3)

    violations: list[str] = []

    # PUSH001 — total lines in push too large
    if push_info.total_lines > max_push_lines:
        violations.append(
            f"[PUSH001] Push is large: {push_info.total_lines} lines across "
            f"{push_info.commit_count} commit(s), threshold is {max_push_lines}.\n"
            f"  → This may be hard to review as a single unit.\n"
            f"    Consider opening a draft PR early or splitting into smaller branches.\n"
            f"    If the size is intentional, add a note to the PR description."
        )

    if not violations:
        # Emit a clean "checked" event
        try:
            from guide.hooks._emit_helper import emit_hook_event
            emit_hook_event(
                hook="pre-push",
                object_label=f"push to {remote_name}",
                violation_codes=[],
                hint_text="",
                config=config,
            )
        except Exception:
            pass
        return 0

    # ----------------------------------------------------------------- evidence
    try:
        from guide.hooks._emit_helper import emit_hook_event
        emit_hook_event(
            hook="pre-push",
            object_label=f"push to {remote_name}",
            violation_codes=["PUSH001"],
            hint_text="\n".join(violations),
            config=config,
        )
    except Exception:
        pass

    # ----------------------------------------------------------------- output
    print("", file=sys.stderr)
    print("┌─ Guide ──────────────────────────────────────────────────────┐", file=sys.stderr)
    for block in violations:
        for line in block.splitlines():
            print(f"│  {line}", file=sys.stderr)
    print("└──────────────────────────────────────────────────────────────┘", file=sys.stderr)
    print("", file=sys.stderr)

    strictness = get_strictness(config)
    if strictness == "block":
        print("[guide] Push blocked. Address the issues above before pushing.", file=sys.stderr)
        return 1

    print("[guide] Push allowed (warn mode). Consider addressing the issues above.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(run())
