import pytest
from guide.checks.rationale import check, CheckResult, _extract_body, _has_task_ref

def codes(result: CheckResult) -> list[str]:
    return [v.code for v in result.violations]

def enabled() -> dict:
    """Config that enables the rationale check."""
    return {"rationale": {"require": True, "min_body_length": 15}}

class TestDisabledByDefault:
    def test_passes_when_disabled(self):
        result = check("feat(x): add feature")
        assert result.ok

    def test_passes_even_with_no_body_when_disabled(self):
        result = check("fix: small patch")
        assert result.ok

class TestTaskReferences:
    @pytest.mark.parametrize("message", [
        "feat(auth): add login\n\nrefs #42",
        "feat(auth): add login\n\nref #7",
        "feat(auth): add login\n\ncloses #100",
        "feat(auth): add login\n\nclose #5",
        "feat(auth): add login\n\nfixes #3",
        "feat(auth): add login\n\nresolves #99",
        "feat(auth): add login PROJ-123",
        "feat(auth): add login\n\nSee https://github.com/org/repo/issues/42",
    ])
    def test_task_ref_accepted(self, message: str):
        result = check(message, enabled())
        assert result.ok, f"Should accept task ref in:\n{message}"

    def test_jira_style_ref(self):
        result = check("feat(auth): add login\n\nPROJ-42: required for sprint goal", enabled())
        assert result.ok

class TestBodyRationale:
    def test_sufficient_body_accepted(self):
        message = (
            "feat(auth): add rate limiting\n"
            "\n"
            "Repeated failed logins were causing DB load spikes."
        )
        result = check(message, enabled())
        assert result.ok

    def test_short_body_triggers(self):
        message = "feat(auth): add rate limiting\n\nshort"
        result = check(message, enabled())
        assert "RAT001" in codes(result)

    def test_body_exactly_at_min_length(self):
        config = {"rationale": {"require": True, "min_body_length": 10}}
        message = "feat(x): change\n\n1234567890"
        result = check(message, config)
        assert result.ok

    def test_no_body_triggers(self):
        result = check("feat(auth): add rate limiting", enabled())
        assert "RAT001" in codes(result)

    def test_comment_only_body_triggers(self):
        message = "feat(x): change\n\n# This is a git comment\n# Another comment"
        result = check(message, enabled())
        assert "RAT001" in codes(result)

class TestNoRationale:
    def test_subject_only_triggers(self):
        result = check("feat(auth): add login endpoint", enabled())
        assert "RAT001" in codes(result)

    def test_subject_with_blank_body_triggers(self):
        result = check("feat(auth): add login endpoint\n\n", enabled())
        assert "RAT001" in codes(result)

class TestExtractBody:
    def test_no_body_returns_empty(self):
        assert _extract_body("feat(x): change") == ""

    def test_body_after_blank_line(self):
        msg = "feat(x): change\n\nThis is the body."
        assert _extract_body(msg) == "This is the body."

    def test_multiline_body(self):
        msg = "feat(x): change\n\nLine one.\nLine two."
        body = _extract_body(msg)
        assert "Line one." in body
        assert "Line two." in body

class TestHasTaskRef:
    def test_refs_hash(self):
        assert _has_task_ref("refs #42") is True

    def test_closes_hash(self):
        assert _has_task_ref("closes #7") is True

    def test_jira_pattern(self):
        assert _has_task_ref("PROJ-123") is True

    def test_no_ref(self):
        assert _has_task_ref("just a plain message") is False

    def test_partial_hash_no_number(self):
        assert _has_task_ref("refs #") is False
