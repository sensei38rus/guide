from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class Violation:
    """A single rule violation with a user-facing hint."""

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
    """Aggregated result of all commit-message checks."""

    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.violations) == 0

    def __str__(self) -> str:
        if self.ok:
            return "✓ Commit message looks good."
        lines = ["Commit message issues found:"]
        for v in self.violations:
            lines.append(str(v))
        return "\n".join(lines)





_CONVENTIONAL_TYPES = (
    "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
)
_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>" + _CONVENTIONAL_TYPES + r")"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?"
    r": (?P<description>.+)$",
    re.IGNORECASE,
)


def check(message: str, config: dict | None = None) -> CheckResult:
   
    if config is None:
        config = {}

    cfg = config.get("commit_message", {})
    require_conventional: bool = cfg.get("require_conventional", True)
    min_desc_len: int = cfg.get("min_description_length", 10)
   
    _default_blocked = [
        r"^fix$", r"^wip$", r"^changes$", r"^update$",
        r"^minor$", r"^temp$", r"^done$", r"^test$", r"^commit$",
    ]
    blocked_patterns: list[str] = (
        cfg["blocked_patterns"] if "blocked_patterns" in cfg else _default_blocked
    )

    
    subject = message.strip().split("\n")[0].strip()

    result = CheckResult()

    
    # Check 1 — not a generic placeholder
    
    for pattern in blocked_patterns:
        if re.match(pattern, subject, re.IGNORECASE):
            result.violations.append(
                Violation(
                    code="MSG001",
                    message=f"Subject line '{subject}' is too generic.",
                    hint=(
                        "Describe what changed, e.g. "
                        "\"fix(auth): handle empty password\" "
                        "instead of just \"fix\"."
                    ),
                )
            )
           
            return result

  
    # Check 2 — Conventional Commits format
  
    if require_conventional:
        match = _CONVENTIONAL_RE.match(subject)
        if not match:
            result.violations.append(
                Violation(
                    code="MSG002",
                    message="Subject does not follow Conventional Commits format.",
                    hint=(
                        "Use the pattern:  type(scope): short description\n"
                        "  Examples:\n"
                        "    feat(auth): add OAuth2 login\n"
                        "    fix: correct null pointer in parser\n"
                        "    docs(readme): update installation steps\n"
                        f"  Allowed types: {_CONVENTIONAL_TYPES.replace('|', ', ')}"
                    ),
                )
            )
           
            return result

        
        # Check 3 — description length (only when format is valid)
       
        description = match.group("description").strip()
        if len(description) < min_desc_len:
            result.violations.append(
                Violation(
                    code="MSG003",
                    message=(
                        f"Description is too short ({len(description)} chars, "
                        f"minimum {min_desc_len})."
                    ),
                    hint=(
                        "Add more context to the description so it explains "
                        "what changed and why, not just that something changed."
                    ),
                )
            )

    return result
