import pytest
from guide.checks.tests_signal import check, CheckResult



def codes(result: CheckResult) -> list[str]:
    return [v.code for v in result.violations]


class TestFileDetection:
    @pytest.mark.parametrize("filename", [
        "test_auth.py",
        "auth_test.py",
        "tests/test_login.py",
        "test/unit/auth_test.py",
        "src/auth.spec.ts",
        "src/auth.spec.js",
        "src/auth.test.ts",
        "AuthTest.java",
        "AuthSpec.java",
        "spec/auth_spec.rb",
    ])
    def test_recognises_test_file(self, filename: str):
        result = check([filename, "src/main.py"], "feat(x): some change")
        assert result.ok, f"Should recognise {filename!r} as a test file"

    def test_no_test_file_triggers(self):
        result = check(["src/main.py", "src/utils.py"], "feat(x): some change")
        assert "TEST001" in codes(result)

    def test_empty_file_list_triggers(self):
        result = check([], "feat(x): some change")
        assert "TEST001" in codes(result)

    def test_only_non_test_files_triggers(self):
        result = check(["src/main.py", "README.md", "Makefile"], "feat(x): impl")
        assert "TEST001" in codes(result)



class TestMessageKeywords:
    @pytest.mark.parametrize("message", [
        "feat(x): something\n\nNo tests: docs only change",
        "feat(x): something\n\ntested manually in staging",
        "feat(x): something\n\nNo tests because: generated code",
        "feat(x): something\n\nManual test performed",
        "feat(x): something\n\nConfig only, no tests needed",
        "feat(x): something\n\nNot testable at unit level",
        "feat(x): something\n\nSkipping tests for this hotfix",
    ])
    def test_no_test_keyword_accepted(self, message: str):
        result = check(["src/main.py"], message)
        assert result.ok, f"Should accept message with no-test keyword:\n{message}"

    def test_no_keyword_and_no_test_file_triggers(self):
        result = check(["src/main.py"], "feat(x): add feature with no explanation")
        assert "TEST001" in codes(result)

    def test_keyword_case_insensitive(self):
        result = check(["src/main.py"], "feat(x): fix\n\nTESTED MANUALLY")
        assert result.ok

    def test_empty_message_and_no_test_file_triggers(self):
        result = check(["src/main.py"], "")
        assert "TEST001" in codes(result)


class TestConfigDisabled:
    def test_disabled_always_passes(self):
        config = {"tests_signal": {"require_signal": False}}
        result = check([], "", config)
        assert result.ok

    def test_disabled_ignores_missing_file(self):
        config = {"tests_signal": {"require_signal": False}}
        result = check(["src/main.py"], "feat(x): no test")
        # enabled by default — should trigger
        assert "TEST001" in codes(result)
        # disabled — should not trigger
        result2 = check(["src/main.py"], "feat(x): no test", config)
        assert result2.ok



class TestCustomKeywords:
    def test_custom_keyword_accepted(self):
        config = {"tests_signal": {"no_tests_keywords": ["integration tested"]}}
        result = check(["src/main.py"], "feat(x): change\n\nintegration tested", config)
        assert result.ok

    def test_default_keyword_not_active_when_overridden(self):
        config = {"tests_signal": {"no_tests_keywords": ["custom phrase"]}}
        # "no tests" is in the default list but not in our custom one
        result = check(["src/main.py"], "feat(x): change\n\nno tests", config)
        assert "TEST001" in codes(result)



class TestCombined:
    def test_test_file_overrides_missing_keyword(self):
        """A test file is sufficient even without a keyword."""
        result = check(["test_main.py", "src/main.py"], "feat(x): add feature")
        assert result.ok

    def test_keyword_overrides_missing_test_file(self):
        """A keyword is sufficient even without a test file."""
        result = check(["src/main.py"], "feat(x): add\n\nno tests: docs only")
        assert result.ok
