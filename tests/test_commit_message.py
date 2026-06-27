import pytest
from guide.checks.commit_message import check, Violation, CheckResult

def codes(result: CheckResult) -> list[str]:
    """Return the list of violation codes from a result."""
    return [v.code for v in result.violations]

# Generic placeholder messages (MSG001)

class TestGenericMessages:
    def test_bare_fix(self):
        result = check("fix")
        assert "MSG001" in codes(result)

    def test_bare_wip(self):
        result = check("wip")
        assert "MSG001" in codes(result)

    def test_bare_changes(self):
        result = check("changes")
        assert "MSG001" in codes(result)

    def test_bare_update(self):
        result = check("update")
        assert "MSG001" in codes(result)

    def test_case_insensitive_wip(self):
        result = check("WIP")
        assert "MSG001" in codes(result)

    def test_single_violation_on_placeholder(self):
        """Placeholder triggers MSG001 and stops — no further violations."""
        result = check("fix")
        assert codes(result) == ["MSG001"]


# Conventional Commits format (MSG002)


class TestConventionalFormat:
    def test_no_type_prefix(self):
        result = check("updated authentication logic in login module")
        assert "MSG002" in codes(result)

    def test_missing_colon(self):
        result = check("feat add new feature")
        assert "MSG002" in codes(result)

    def test_invalid_type(self):
        result = check("change(auth): do something important here")
        assert "MSG002" in codes(result)

    def test_valid_feat(self):
        result = check("feat(auth): add OAuth2 login support")
        assert "MSG002" not in codes(result)

    def test_valid_fix_no_scope(self):
        result = check("fix: correct null pointer in password parser")
        assert "MSG002" not in codes(result)

    def test_valid_docs(self):
        result = check("docs(readme): update installation instructions")
        assert "MSG002" not in codes(result)

    def test_valid_refactor(self):
        result = check("refactor(core): extract validation into separate module")
        assert "MSG002" not in codes(result)

    def test_valid_breaking_change(self):
        result = check("feat(api)!: drop support for v1 endpoints")
        assert "MSG002" not in codes(result)

    def test_valid_chore(self):
        result = check("chore: bump dependencies to latest versions")
        assert "MSG002" not in codes(result)

    def test_valid_ci(self):
        result = check("ci: add GitHub Actions workflow for tests")
        assert "MSG002" not in codes(result)

# Description length (MSG003)

class TestDescriptionLength:
    def test_too_short_description(self):
        result = check("fix(auth): fix it")
        assert "MSG003" in codes(result)

    def test_exact_minimum(self):
        """Exactly 10 characters should pass (default min = 10)."""
        result = check("fix(auth): 1234567890")
        assert "MSG003" not in codes(result)

    def test_long_enough_description(self):
        result = check("feat(ui): add responsive layout to the dashboard")
        assert "MSG003" not in codes(result)

    def test_custom_min_length(self):
        """Custom config with min_description_length=20."""
        config = {"commit_message": {"min_description_length": 20}}
        result = check("fix(auth): short fix", config)
        assert "MSG003" in codes(result)

    def test_custom_min_length_pass(self):
        config = {"commit_message": {"min_description_length": 5}}
        result = check("fix(x): ok fix", config)
        assert "MSG003" not in codes(result)



class TestValidMessages:
    @pytest.mark.parametrize("message", [
        "feat(auth): add password strength validation on registration",
        "fix: correct null pointer exception in JSON parser",
        "docs(readme): update installation and quickstart sections",
        "refactor(api): extract authentication middleware into separate module",
        "test(auth): add unit tests for JWT token validation",
        "chore: update Python version in CI configuration file",
        "ci: add automated release pipeline for PyPI publishing",
        "perf(db): replace N+1 queries with a single JOIN operation",
        "style: apply black formatting to the entire codebase",
    ])
    def test_valid_message_passes(self, message: str):
        result = check(message)
        assert result.ok, f"Expected OK for: {message!r}\nGot: {result}"


# Multi-line messages (subject + body)


class TestMultiLineMessages:
    def test_subject_checked_body_ignored_for_format(self):
        message = (
            "feat(auth): add password strength meter\n"
            "\n"
            "Uses zxcvbn to evaluate strength. Shows feedback as the user types.\n"
            "Closes #42"
        )
        result = check(message)
        assert result.ok

    def test_bad_subject_with_good_body(self):
        message = "wip\n\nThis is some context"
        result = check(message)
        assert "MSG001" in codes(result)

# Config: disable Conventional Commits requirement


class TestConfigOverrides:
    def test_conventional_disabled(self):
        config = {"commit_message": {"require_conventional": False}}
        result = check("add some feature with a good long description", config)
        assert "MSG002" not in codes(result)
        assert "MSG003" not in codes(result)

    def test_custom_blocked_pattern(self):
        config = {"commit_message": {"blocked_patterns": [r"^please work$"]}}
        result = check("please work", config)
        assert "MSG001" in codes(result)

    def test_default_blocked_not_active_when_overridden(self):
        """When custom blocked_patterns are set, the default list is fully replaced."""
        config = {"commit_message": {"blocked_patterns": [r"^please work$"]}}
        # "wip" is in the default list but not in our custom one — should NOT get MSG001
        result = check("wip", config)
        assert "MSG001" not in codes(result)
        # "wip" fails MSG002 instead (not Conventional Commits), which is fine
        assert "MSG002" in codes(result)



# Violation dataclass and CheckResult


class TestDataClasses:
    def test_violation_str_with_hint(self):
        v = Violation(code="MSG001", message="Too generic.", hint="Try harder.")
        text = str(v)
        assert "MSG001" in text
        assert "Too generic." in text
        assert "Try harder." in text

    def test_violation_str_without_hint(self):
        v = Violation(code="MSG002", message="Bad format.")
        text = str(v)
        assert "MSG002" in text
        assert "→" not in text

    def test_result_ok_when_no_violations(self):
        result = CheckResult()
        assert result.ok

    def test_result_not_ok_with_violations(self):
        result = CheckResult(violations=[Violation("MSG001", "test")])
        assert not result.ok

    def test_result_str_ok(self):
        result = CheckResult()
        assert "good" in str(result).lower()

    def test_result_str_violations(self):
        result = CheckResult(violations=[Violation("MSG001", "Too generic.")])
        text = str(result)
        assert "MSG001" in text
        assert "issues" in text.lower()
