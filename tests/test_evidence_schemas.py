import json
from datetime import datetime, timezone
import pytest
from guide.evidence.schemas import (
    Action,
    Actor,
    EvidenceLinks,
    GuideEvent,
    build_actor,
    _utc_now,
)

class TestAction:
    def test_all_actions_defined(self):
        for a in (Action.CHECKED, Action.PROMPTED, Action.CORRECTED,
                  Action.BLOCKED, Action.CONFIRMED):
            assert a.startswith("guide.")

    def test_all_set_complete(self):
        assert len(Action.ALL) == 5

class TestActor:
    def test_defaults_are_empty_strings(self):
        a = Actor()
        assert a.name == ""
        assert a.email == ""
        assert a.repo == ""
        assert a.branch == ""

    def test_to_dict(self):
        a = Actor(name="Ada", email="ada@example.com", repo="git@gh", branch="main")
        d = a.to_dict()
        assert d["name"] == "Ada"
        assert d["email"] == "ada@example.com"
        assert d["repo"] == "git@gh"
        assert d["branch"] == "main"

class TestEvidenceLinks:
    def test_empty_fields_excluded_from_dict(self):
        el = EvidenceLinks(commit_hash="abc123")
        d = el.to_dict()
        assert d == {"commit_hash": "abc123"}

    def test_all_fields_included_when_set(self):
        el = EvidenceLinks(
            commit_hash="abc", local_log_path="/tmp/e.jsonl",
            task_ref="refs #42", external_id="ext-1",
        )
        d = el.to_dict()
        assert len(d) == 4

class TestGuideEvent:
    def _make_event(self, **kwargs) -> GuideEvent:
        defaults = dict(action=Action.PROMPTED, object="commit message")
        defaults.update(kwargs)
        return GuideEvent(**defaults)

    def test_default_timestamp_is_utc_iso(self):
        e = self._make_event()
        # Should parse as ISO-8601 with timezone
        dt = datetime.fromisoformat(e.timestamp)
        assert dt.tzinfo is not None

    def test_to_dict_contains_required_keys(self):
        e = self._make_event()
        d = e.to_dict()
        for key in ("action", "object", "actor", "timestamp", "hook",
                    "violation_codes", "hint_shown", "evidence"):
            assert key in d, f"Missing key: {key}"

    def test_to_json_is_valid_json(self):
        e = self._make_event()
        parsed = json.loads(e.to_json())
        assert parsed["action"] == Action.PROMPTED

    def test_to_jsonl_is_single_line(self):
        e = self._make_event()
        line = e.to_jsonl()
        assert "\n" not in line

    def test_to_jsonl_is_valid_json(self):
        e = self._make_event()
        parsed = json.loads(e.to_jsonl())
        assert parsed["object"] == "commit message"

    def test_violation_codes_serialised(self):
        e = self._make_event(
            action=Action.PROMPTED,
            violation_codes=["MSG001", "TEST001"],
        )
        d = e.to_dict()
        assert d["violation_codes"] == ["MSG001", "TEST001"]

    def test_extra_field_included_when_set(self):
        e = self._make_event(extra={"custom": "value"})
        d = e.to_dict()
        assert d["extra"] == {"custom": "value"}

    def test_extra_field_omitted_when_empty(self):
        e = self._make_event()
        d = e.to_dict()
        assert "extra" not in d

class TestGuideEventFromDict:
    def _roundtrip(self, event: GuideEvent) -> GuideEvent:
        return GuideEvent.from_dict(json.loads(event.to_json()))

    def test_action_preserved(self):
        e = GuideEvent(action=Action.BLOCKED, object="staged diff")
        assert self._roundtrip(e).action == Action.BLOCKED

    def test_object_preserved(self):
        e = GuideEvent(action=Action.CHECKED, object="push to origin")
        assert self._roundtrip(e).object == "push to origin"

    def test_actor_preserved(self):
        e = GuideEvent(
            action=Action.PROMPTED, object="x",
            actor=Actor(name="Bob", email="bob@x.com", repo="r", branch="feat"),
        )
        rt = self._roundtrip(e)
        assert rt.actor.name == "Bob"
        assert rt.actor.email == "bob@x.com"

    def test_violation_codes_preserved(self):
        e = GuideEvent(
            action=Action.PROMPTED, object="x",
            violation_codes=["MSG002", "DIFF001"],
        )
        assert self._roundtrip(e).violation_codes == ["MSG002", "DIFF001"]

    def test_evidence_links_preserved(self):
        e = GuideEvent(
            action=Action.PROMPTED, object="x",
            evidence=EvidenceLinks(commit_hash="deadbeef", task_ref="refs #7"),
        )
        rt = self._roundtrip(e)
        assert rt.evidence.commit_hash == "deadbeef"
        assert rt.evidence.task_ref == "refs #7"

    def test_from_dict_with_missing_keys_uses_defaults(self):
        minimal = {"action": Action.CHECKED, "object": "msg"}
        e = GuideEvent.from_dict(minimal)
        assert e.hook == ""
        assert e.violation_codes == []

    def test_jsonl_roundtrip(self):
        e = GuideEvent(
            action=Action.PROMPTED, object="commit message",
            hook="commit-msg",
            violation_codes=["MSG001"],
            hint_shown="Subject is too generic.",
        )
        line = e.to_jsonl()
        e2 = GuideEvent.from_dict(json.loads(line))
        assert e2.hint_shown == "Subject is too generic."
        assert e2.hook == "commit-msg"

class TestBuildActor:
    def test_returns_actor_instance(self, tmp_path):
        # We don't assert specific values since git config varies per machine,
        # but we verify the function returns an Actor with string fields.
        actor = build_actor(repo_root=str(tmp_path))
        assert isinstance(actor, Actor)
        assert isinstance(actor.name, str)
        assert isinstance(actor.email, str)
        assert isinstance(actor.repo, str)
        assert isinstance(actor.branch, str)

class TestUtcNow:
    def test_returns_valid_iso_string(self):
        ts = _utc_now()
        dt = datetime.fromisoformat(ts)
        assert dt.tzinfo is not None

    def test_is_recent(self):
        ts = _utc_now()
        dt = datetime.fromisoformat(ts)
        now = datetime.now(tz=timezone.utc)
        diff = abs((now - dt).total_seconds())
        assert diff < 5  # within 5 seconds
