"""Unit tests for integrations/git.py — Sprint 2.

These tests cover pure logic (parsing, data classes) without requiring a real
git repository.  Functions that shell out to git are tested via integration
tests in run_demo.sh.
"""

import pytest
from guide.integrations.git import (
    StagedDiff,
    PushInfo,
    parse_pre_push_stdin,
)


# ─────────────────────────────────────────────────────────────────────────────
# StagedDiff
# ─────────────────────────────────────────────────────────────────────────────

class TestStagedDiff:
    def test_total_lines(self):
        d = StagedDiff(files=["a.py"], added_lines=10, removed_lines=5)
        assert d.total_lines == 15

    def test_file_count(self):
        d = StagedDiff(files=["a.py", "b.py", "c.py"])
        assert d.file_count == 3

    def test_empty_diff(self):
        d = StagedDiff()
        assert d.total_lines == 0
        assert d.file_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# PushInfo
# ─────────────────────────────────────────────────────────────────────────────

class TestPushInfo:
    def test_total_lines(self):
        p = PushInfo(added_lines=100, removed_lines=50)
        assert p.total_lines == 150

    def test_empty_push_info(self):
        p = PushInfo()
        assert p.total_lines == 0
        assert p.commit_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# parse_pre_push_stdin
# ─────────────────────────────────────────────────────────────────────────────

class TestParsePrePushStdin:
    def test_single_ref(self):
        stdin = "refs/heads/main abc123 refs/heads/main def456\n"
        refs = parse_pre_push_stdin(stdin)
        assert len(refs) == 1
        local_sha, remote_sha, local_ref = refs[0]
        assert local_sha == "abc123"
        assert remote_sha == "def456"
        assert local_ref == "refs/heads/main"

    def test_multiple_refs(self):
        stdin = (
            "refs/heads/main aaa111 refs/heads/main bbb222\n"
            "refs/heads/feat ccc333 refs/heads/feat ddd444\n"
        )
        refs = parse_pre_push_stdin(stdin)
        assert len(refs) == 2

    def test_empty_stdin(self):
        refs = parse_pre_push_stdin("")
        assert refs == []

    def test_malformed_line_skipped(self):
        stdin = "only-three parts here\n"
        refs = parse_pre_push_stdin(stdin)
        assert refs == []

    def test_blank_lines_skipped(self):
        stdin = "\nrefs/heads/main abc refs/heads/main def\n\n"
        refs = parse_pre_push_stdin(stdin)
        assert len(refs) == 1

    def test_delete_ref_zero_sha(self):
        """A push that deletes a branch sends all-zero SHA for local."""
        zero = "0" * 40
        stdin = f"refs/heads/old {zero} refs/heads/old abc123\n"
        refs = parse_pre_push_stdin(stdin)
        assert refs[0][0] == zero  # preserved, filtering is in get_push_info
