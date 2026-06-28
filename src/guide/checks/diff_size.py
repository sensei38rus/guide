from __future__ import annotations
from dataclasses import dataclass, field
from guide.integrations.git import StagedDiff

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
            return "✓ Diff size looks good."
        lines = ["Diff size issues found:"]
        for v in self.violations:
            lines.append(str(v))
        return "\n".join(lines)


def check(diff: StagedDiff, config: dict | None = None) -> CheckResult:
    """Check whether *diff* exceeds configured size thresholds.

    Args:
        diff:   A :class:`~guide.integrations.git.StagedDiff` instance.
        config: Guide config dict.  Uses built-in defaults when *None*.

    Returns:
        :class:`CheckResult` with zero or more violations.
    """
    if config is None:
        config = {}

    cfg = config.get("diff", {})
    max_lines: int = cfg.get("max_lines", 200)
    max_files: int = cfg.get("max_files", 15)

    result = CheckResult()

    
    # DIFF001 — too many lines changed
    
    if diff.total_lines > max_lines:
        result.violations.append(
            Violation(
                code="DIFF001",
                message=(
                    f"Staged change is large: {diff.total_lines} lines "
                    f"(+{diff.added_lines} / -{diff.removed_lines}), "
                    f"threshold is {max_lines}."
                ),
                hint=(
                    "Consider splitting this into smaller, focused commits.\n"
                    "  Each commit should represent one logical change.\n"
                    "  If the size is intentional (e.g. generated code, bulk rename),\n"
                    "  add a note in the commit body explaining why."
                ),
            )
        )

    
    # DIFF002 — too many files changed
    
    if diff.file_count > max_files:
        result.violations.append(
            Violation(
                code="DIFF002",
                message=(
                    f"Too many files in one commit: {diff.file_count} files, "
                    f"threshold is {max_files}."
                ),
                hint=(
                    "A commit touching many unrelated files is hard to review.\n"
                    "  Group related changes together and commit them separately."
                ),
            )
        )

    return result
