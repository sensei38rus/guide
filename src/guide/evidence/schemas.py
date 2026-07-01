from __future__ import annotations
import json
import os
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any



class Action:
    """Namespace for Guide action strings."""

    CHECKED   = "guide.checked"    # hook ran and found nothing to flag
    PROMPTED  = "guide.prompted"   # hint was shown to the user
    CORRECTED = "guide.corrected"  # user fixed the issue after a hint
    BLOCKED   = "guide.blocked"    # action was stopped by a rule
    CONFIRMED = "guide.confirmed"  # user explicitly acknowledged an exception

    ALL = {CHECKED, PROMPTED, CORRECTED, BLOCKED, CONFIRMED}

@dataclass
class Actor:
    """The person or process that triggered the hook."""

    name: str = ""          # git config user.name
    email: str = ""         # git config user.email
    repo: str = ""          # repository remote URL or local path
    branch: str = ""        # current branch name

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class EvidenceLinks:
    """References to artefacts produced by or related to the event."""

    commit_hash: str = ""       # SHA of the commit (if available post-commit)
    local_log_path: str = ""    # absolute path to the JSONL log file
    task_ref: str = ""          # task/issue reference extracted from message
    external_id: str = ""       # ID in an external LRS / Evidence Locker

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}



@dataclass
class GuideEvent:
    """One observable event emitted by a Guide hook."""

    # Required fields
    action: str                         # one of Action.*
    object: str                         # what was checked (human-readable label)

    # Actor — populated from git config at creation time
    actor: Actor = field(default_factory=Actor)

    # Timing
    timestamp: str = field(default_factory=lambda: _utc_now())

    # Hook context
    hook: str = ""                      # "commit-msg" | "pre-commit" | "pre-push"
    course: str = ""                    # course/project identifier (from config)

    # Violation codes that triggered the event (empty for CHECKED)
    violation_codes: list[str] = field(default_factory=list)

    # Hint text shown to the user (for PROMPTED / BLOCKED)
    hint_shown: str = ""

    # Links to related artefacts
    evidence: EvidenceLinks = field(default_factory=EvidenceLinks)

    # Arbitrary extra fields for future use
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return {
            "action": self.action,
            "object": self.object,
            "actor": self.actor.to_dict(),
            "timestamp": self.timestamp,
            "hook": self.hook,
            "course": self.course,
            "violation_codes": self.violation_codes,
            "hint_shown": self.hint_shown,
            "evidence": self.evidence.to_dict(),
            **({"extra": self.extra} if self.extra else {}),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_jsonl(self) -> str:
        """Serialise to a single-line JSONL string (no trailing newline)."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuideEvent":
        """Deserialise from a plain dictionary (e.g. parsed from JSONL)."""
        actor_data = data.get("actor", {})
        evidence_data = data.get("evidence", {})
        return cls(
            action=data.get("action", ""),
            object=data.get("object", ""),
            actor=Actor(**{k: actor_data.get(k, "") for k in Actor.__dataclass_fields__}),
            timestamp=data.get("timestamp", _utc_now()),
            hook=data.get("hook", ""),
            course=data.get("course", ""),
            violation_codes=data.get("violation_codes", []),
            hint_shown=data.get("hint_shown", ""),
            evidence=EvidenceLinks(
                **{k: evidence_data.get(k, "") for k in EvidenceLinks.__dataclass_fields__}
            ),
            extra=data.get("extra", {}),
        )



def _utc_now() -> str:
    """Return current UTC time as an ISO-8601 string with timezone."""
    return datetime.now(tz=timezone.utc).isoformat()


def build_actor(repo_root: str | None = None) -> Actor:
    """Populate an :class:`Actor` from the local git configuration."""

    def _git(args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True, text=True,
                cwd=repo_root or os.getcwd(),
            )
            return result.stdout.strip()
        except Exception:
            return ""

    name   = _git(["config", "user.name"])
    email  = _git(["config", "user.email"])
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    repo   = (
        _git(["remote", "get-url", "origin"])
        or _git(["rev-parse", "--show-toplevel"])
        or os.getcwd()
    )

    return Actor(name=name, email=email, repo=repo, branch=branch)
