import pytest
from guide.checks.diff_size import check, CheckResult
from guide.integrations.git import StagedDiff



def codes(result: CheckResult) -> list[str]:
    return [v.code for v in result.violations]


def make_diff(added: int = 0, removed: int = 0, files: list[str] | None = None) -> StagedDiff:
    return StagedDiff(
        files=files or ["src/main.py"],
        added_lines=added,
        removed_lines=removed,
    )




class TestLineThreshold:
    def test_under_threshold_ok(self):
        result = check(make_diff(added=50, removed=30))
        assert result.ok

    def test_exactly_at_threshold_ok(self):
        # 200 lines = threshold — should pass (strictly greater than)
        result = check(make_diff(added=100, removed=100))
        assert result.ok

    def test_over_threshold_triggers(self):
        result = check(make_diff(added=150, removed=100))  # 250 total
        assert "DIFF001" in codes(result)

    def test_custom_threshold(self):
        config = {"diff": {"max_lines": 50}}
        result = check(make_diff(added=30, removed=30), config)  # 60 total
        assert "DIFF001" in codes(result)

    def test_custom_threshold_pass(self):
        config = {"diff": {"max_lines": 500}}
        result = check(make_diff(added=200, removed=100), config)
        assert "DIFF001" not in codes(result)

    def test_violation_message_contains_counts(self):
        diff = make_diff(added=150, removed=100)
        result = check(diff)
        assert "DIFF001" in codes(result)
        msg = result.violations[0].message
        assert "250" in msg  # total lines
        assert "150" in msg  # added
        assert "100" in msg  # removed




class TestFileThreshold:
    def test_few_files_ok(self):
        result = check(make_diff(files=[f"file{i}.py" for i in range(5)]))
        assert result.ok

    def test_exactly_at_threshold_ok(self):
        config = {"diff": {"max_files": 10}}
        result = check(make_diff(files=[f"f{i}.py" for i in range(10)]), config)
        assert "DIFF002" not in codes(result)

    def test_over_file_threshold_triggers(self):
        config = {"diff": {"max_files": 5}}
        result = check(make_diff(files=[f"f{i}.py" for i in range(6)]), config)
        assert "DIFF002" in codes(result)

    def test_violation_message_contains_count(self):
        config = {"diff": {"max_files": 3}}
        diff = make_diff(files=["a.py", "b.py", "c.py", "d.py"])
        result = check(diff, config)
        assert "4" in result.violations[0].message




class TestBothThresholds:
    def test_both_violations(self):
        config = {"diff": {"max_lines": 10, "max_files": 2}}
        diff = make_diff(
            added=20, removed=5,
            files=["a.py", "b.py", "c.py"],
        )
        result = check(diff, config)
        assert "DIFF001" in codes(result)
        assert "DIFF002" in codes(result)
        assert len(result.violations) == 2



class TestCheckResult:
    def test_ok_when_empty(self):
        result = check(make_diff(added=1, removed=1))
        assert result.ok

    def test_str_ok(self):
        result = check(make_diff(added=1))
        assert "good" in str(result).lower()

    def test_str_violations(self):
        config = {"diff": {"max_lines": 5}}
        result = check(make_diff(added=10), config)
        assert "DIFF001" in str(result)
