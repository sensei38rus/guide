"""Git integration helpers.

All functions are thin, side-effect-free wrappers around ``git`` CLI calls.
They return plain Python objects so checks stay easy to unit-test without a
real repository.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class StagedDiff:
    """Summary of the staged (index) changes for pre-commit."""

    files: list[str] = field(default_factory=list)
    added_lines: int = 0
    removed_lines: int = 0

    @property
    def total_lines(self) -> int:
        return self.added_lines + self.removed_lines

    @property
    def file_count(self) -> int:
        return len(self.files)


@dataclass
class PushInfo:
    """Information available in the pre-push hook."""

    remote_name: str = ""
    remote_url: str = ""
    # Each item is (local_sha, remote_sha, ref_name)
    refs: list[tuple[str, str, str]] = field(default_factory=list)
    # Total lines changed across all commits not yet on remote
    added_lines: int = 0
    removed_lines: int = 0
    commit_count: int = 0

    @property
    def total_lines(self) -> int:
        return self.added_lines + self.removed_lines


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _run(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return stdout as a string.

    Raises ``RuntimeError`` when the process exits with a non-zero code.
    """
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command {args!r} failed (exit {result.returncode}):\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_staged_diff(repo_root: Path | None = None) -> StagedDiff:
    """Return a summary of the currently staged changes.

    Uses ``git diff --staged --numstat`` which outputs one line per file:
        <added>\\t<removed>\\t<filename>

    Binary files are reported as ``-\\t-\\t<filename>`` and counted as 0 lines.
    """
    try:
        output = _run(["git", "diff", "--staged", "--numstat"], cwd=repo_root)
    except RuntimeError:
        return StagedDiff()

    files: list[str] = []
    added_total = 0
    removed_total = 0

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added_str, removed_str, filename = parts
        files.append(filename)
        # Binary files report "-" for both counts
        try:
            added_total += int(added_str)
        except ValueError:
            pass
        try:
            removed_total += int(removed_str)
        except ValueError:
            pass

    return StagedDiff(
        files=files,
        added_lines=added_total,
        removed_lines=removed_total,
    )


def get_push_info(
    remote_name: str,
    remote_url: str,
    refs: list[tuple[str, str, str]],
    repo_root: Path | None = None,
) -> PushInfo:
    """Build a :class:`PushInfo` by counting commits not yet on the remote.

    ``refs`` is a list of ``(local_sha, remote_sha, refname)`` tuples as
    provided by Git on stdin to the pre-push hook.
    """
    info = PushInfo(remote_name=remote_name, remote_url=remote_url, refs=refs)

    for local_sha, remote_sha, _refname in refs:
        # Zero SHA means the ref is being deleted — skip
        if local_sha == "0" * 40:
            continue

        # Range: commits reachable from local but not from remote
        if remote_sha == "0" * 40:
            rev_range = local_sha
        else:
            rev_range = f"{remote_sha}..{local_sha}"

        try:
            stat_output = _run(
                ["git", "log", rev_range, "--numstat", "--format="],
                cwd=repo_root,
            )
            commit_count_output = _run(
                ["git", "rev-list", "--count", rev_range],
                cwd=repo_root,
            )
        except RuntimeError:
            continue

        info.commit_count += int(commit_count_output.strip() or "0")

        for line in stat_output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            added_str, removed_str, _ = parts
            try:
                info.added_lines += int(added_str)
            except ValueError:
                pass
            try:
                info.removed_lines += int(removed_str)
            except ValueError:
                pass

    return info


def parse_pre_push_stdin(stdin_text: str) -> list[tuple[str, str, str]]:
    """Parse the stdin lines Git sends to the pre-push hook.

    Each line has the format:
        <local_ref> <local_sha> <remote_ref> <remote_sha>

    Returns a list of ``(local_sha, remote_sha, local_ref)`` tuples.
    """
    refs: list[tuple[str, str, str]] = []
    for line in stdin_text.splitlines():
        parts = line.strip().split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, _remote_ref, remote_sha = parts
        refs.append((local_sha, remote_sha, local_ref))
    return refs
