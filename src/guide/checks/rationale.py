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
            return "✓ Rationale found."
        lines = ["Rationale issues found:"]
        for v in self.violations:
            lines.append(str(v))
        return "\n".join(lines)



_TASK_REF_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brefs?\s*#\d+", re.IGNORECASE),        # refs #42, ref #7
    re.compile(r"\bcloses?\s*#\d+", re.IGNORECASE),      # closes #42
    re.compile(r"\bfixes?\s*#\d+", re.IGNORECASE),       # fixes #42
    re.compile(r"\bresolves?\s*#\d+", re.IGNORECASE),    # resolves #42
    re.compile(r"\b[A-Z]{2,10}-\d+\b"),                  # JIRA-style: PROJ-123
    re.compile(r"https?://\S+/issues?/\d+"),              # issue URL
]



def _extract_body(message: str) -> str:
    """Return everything after the first blank line (the commit body)."""
    lines = message.strip().splitlines()
    # Find the blank separator between subject and body
    for i, line in enumerate(lines):
        if i > 0 and line.strip() == "":
            body_lines = lines[i + 1:]
            return "\n".join(body_lines).strip()
    return ""


def _has_task_ref(message: str) -> bool:
    """Return True if the message contains any task/issue reference."""
    for pattern in _TASK_REF_PATTERNS:
        if pattern.search(message):
            return True
    return False


def _body_is_sufficient(body: str, min_length: int) -> bool:
    """Return True if *body* has enough meaningful content."""
    # Strip comment lines (e.g. from git commit template)
    meaningful = "\n".join(
        line for line in body.splitlines() if not line.strip().startswith("#")
    ).strip()
    return len(meaningful) >= min_length



def check(commit_message: str, config: dict | None = None) -> CheckResult:
   
    if config is None:
        config = {}

    cfg = config.get("rationale", {})
    require: bool = cfg.get("require", False)

    if not require:
        return CheckResult()  # opt-in only

    min_body_length: int = cfg.get("min_body_length", 15)

    result = CheckResult()

    # ---- Task reference covers the rationale requirement -----------------
    if _has_task_ref(commit_message):
        return result

    # ---- Sufficient commit body covers it too ----------------------------
    body = _extract_body(commit_message)
    if _body_is_sufficient(body, min_body_length):
        return result

    # ---- Neither found ---------------------------------------------------
    result.violations.append(
        Violation(
            code="RAT001",
            message="No rationale found in the commit message.",
            hint=(
                "Add a brief explanation of *why* this change was made.\n"
                "  Options:\n"
                "    a) Reference a task:  'refs #42'  or  'closes PROJ-7'\n"
                "    b) Add a body paragraph after a blank line:\n"
                "\n"
                "       feat(auth): add rate limiting to login endpoint\n"
                "\n"
                "       Repeated failed logins were causing DB load spikes.\n"
                "       Limit to 5 attempts per minute per IP with exponential backoff."
            ),
        )
    )

    return result
