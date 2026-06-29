from __future__ import annotations
import re
from dataclasses import dataclass, field

@dataclass
class Violation:
    code: str
    message: str
    hint: str = ""

    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.message}"]
        if self.hint:
            parts.append(f"  → {self.hint}")
        return "\n".join(parts)


@dataclass
class CheckResult:
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.violations) == 0

    def __str__(self) -> str:
        if self.ok:
            return "✓ Test signal found."
        lines = ["Test signal issues found:"]
        for v in self.violations:
            lines.append(str(v))
        return "\n".join(lines)


# Files that count as test evidence
_TEST_FILE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(^|/)test_[^/]+\.py$"),       # test_auth.py
    re.compile(r"(^|/)[^/]+_test\.py$"),        # auth_test.py
    re.compile(r"(^|/)tests?/"),                # tests/ or test/ directory
    re.compile(r"\.spec\.[jt]sx?$"),            # auth.spec.ts / auth.spec.js
    re.compile(r"\.test\.[jt]sx?$"),            # auth.test.ts
    re.compile(r"_spec\.rb$"),                  # Ruby rspec
    re.compile(r"Test\.java$"),                 # AuthTest.java
    re.compile(r"Spec\.java$"),                 # AuthSpec.java
]

# Default keywords in the commit message body that count as explicit no-test explanation
_DEFAULT_NO_TEST_KEYWORDS: list[str] = [
    "no tests",
    "not testable",
    "manual test",
    "tested manually",
    "docs only",
    "config only",
    "no test needed",
    "skipping tests",
    "no test because",
    "no tests because",
    "no tests needed",
]

def _has_test_file(files: list[str]) -> bool:
    """Return True if any staged file looks like a test file."""
    for f in files:
        for pattern in _TEST_FILE_PATTERNS:
            if pattern.search(f):
                return True
    return False


def _has_no_test_keyword(message: str, keywords: list[str]) -> bool:
    """Return True if the commit message contains an explicit no-test note."""
    lower = message.lower()
    return any(kw in lower for kw in keywords)


def check(
    files: list[str],
    commit_message: str,
    config: dict | None = None,
) -> CheckResult:
  
    if config is None:
        config = {}

    cfg = config.get("tests_signal", {})
    require_signal: bool = cfg.get("require_signal", True)

    if not require_signal:
        return CheckResult()

    no_test_keywords: list[str] = cfg.get(
        "no_tests_keywords", _DEFAULT_NO_TEST_KEYWORDS
    )

    result = CheckResult()

    # ---- Evidence present? -----------------------------------------------
    if _has_test_file(files):
        return result  # test file staged → signal found

    if _has_no_test_keyword(commit_message, no_test_keywords):
        return result  # explicit "no tests because …" → signal found

    # ---- No evidence found -----------------------------------------------
    result.violations.append(
        Violation(
            code="TEST001",
            message="No test signal found in staged files or commit message.",
            hint=(
                "Either:\n"
                "  a) Add or update a test file in the same commit, or\n"
                "  b) Add a line to the commit body explaining why tests\n"
                "     are not applicable, e.g.:\n"
                "       'No tests: config-only change'\n"
                "       'Tested manually in staging environment'\n"
                "       'No tests because: generated code, covered by contract tests'"
            ),
        )
    )

    return result
