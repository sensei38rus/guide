import json
from pathlib import Path
import pytest
from guide.evidence.schemas import Action, Actor, GuideEvent
from guide.evidence.emitter import emit, read_events, _resolve_log_path

def _make_event(**kwargs) -> GuideEvent:
    defaults = dict(
        action=Action.PROMPTED,
        object="commit message",
        hook="commit-msg",
        violation_codes=["MSG001"],
    )
    defaults.update(kwargs)
    return GuideEvent(**defaults)

def _config(tmp_path: Path, sink: str = "file") -> dict:
    return {
        "evidence_sink": sink,
        "evidence_path": str(tmp_path / "events.jsonl"),
        "mock_mode": True,
    }

class TestResolveLogPath:
    def test_uses_configured_path(self, tmp_path):
        cfg = {"evidence_path": str(tmp_path / "custom.jsonl")}
        assert _resolve_log_path(cfg) == (tmp_path / "custom.jsonl").resolve()

    def test_default_path_in_home(self):
        path = _resolve_log_path({})
        assert "guide" in str(path)
        assert path.name == "events.jsonl"

class TestEmitFile:
    def test_creates_log_file(self, tmp_path):
        cfg = _config(tmp_path)
        event = _make_event()
        result = emit(event, cfg)
        assert result is True
        log = tmp_path / "events.jsonl"
        assert log.exists()

    def test_appends_jsonl_line(self, tmp_path):
        cfg = _config(tmp_path)
        emit(_make_event(violation_codes=["MSG001"]), cfg)
        emit(_make_event(violation_codes=["MSG002"]), cfg)
        lines = (tmp_path / "events.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2

    def test_line_is_valid_json(self, tmp_path):
        cfg = _config(tmp_path)
        emit(_make_event(), cfg)
        line = (tmp_path / "events.jsonl").read_text().strip()
        data = json.loads(line)
        assert data["action"] == Action.PROMPTED

    def test_creates_parent_directory(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        cfg = {"evidence_sink": "file", "evidence_path": str(deep / "events.jsonl"), "mock_mode": True}
        emit(_make_event(), cfg)
        assert (deep / "events.jsonl").exists()

    def test_event_fields_preserved(self, tmp_path):
        cfg = _config(tmp_path)
        event = _make_event(
            action=Action.BLOCKED,
            object="staged diff",
            hook="pre-commit",
            violation_codes=["DIFF001"],
            hint_shown="Too many lines.",
        )
        emit(event, cfg)
        line = (tmp_path / "events.jsonl").read_text().strip()
        data = json.loads(line)
        assert data["action"] == Action.BLOCKED
        assert data["object"] == "staged diff"
        assert data["violation_codes"] == ["DIFF001"]
        assert data["hint_shown"] == "Too many lines."




class TestEmitNone:
    def test_none_sink_returns_true_without_writing(self, tmp_path):
        cfg = {"evidence_sink": "none", "mock_mode": True,
               "evidence_path": str(tmp_path / "events.jsonl")}
        result = emit(_make_event(), cfg)
        assert result is True
        assert not (tmp_path / "events.jsonl").exists()


class TestMockMode:
    def test_mock_mode_redirects_webhook_to_file(self, tmp_path):
        cfg = {
            "evidence_sink": "webhook",
            "mock_mode": True,
            "evidence_path": str(tmp_path / "events.jsonl"),
        }
        result = emit(_make_event(), cfg)
        assert result is True
        assert (tmp_path / "events.jsonl").exists()

class TestReadEvents:
    def test_returns_empty_when_no_log(self, tmp_path):
        cfg = _config(tmp_path)
        events = read_events(cfg)
        assert events == []

    def test_reads_back_emitted_events(self, tmp_path):
        cfg = _config(tmp_path)
        emit(_make_event(violation_codes=["MSG001"]), cfg)
        emit(_make_event(violation_codes=["MSG002"]), cfg)
        events = read_events(cfg)
        assert len(events) == 2

    def test_events_are_guide_event_instances(self, tmp_path):
        cfg = _config(tmp_path)
        emit(_make_event(), cfg)
        events = read_events(cfg)
        assert isinstance(events[0], GuideEvent)

    def test_event_data_preserved_through_roundtrip(self, tmp_path):
        cfg = _config(tmp_path)
        original = _make_event(
            action=Action.PROMPTED,
            violation_codes=["MSG001", "TEST001"],
            hook="commit-msg",
        )
        emit(original, cfg)
        events = read_events(cfg)
        e = events[0]
        assert e.action == Action.PROMPTED
        assert e.violation_codes == ["MSG001", "TEST001"]
        assert e.hook == "commit-msg"

    def test_malformed_line_skipped(self, tmp_path, capsys):
        log = tmp_path / "events.jsonl"
        log.write_text('{"action":"guide.checked","object":"x"}\nnot-json\n{"action":"guide.prompted","object":"y"}\n')
        cfg = {"evidence_path": str(log), "mock_mode": True}
        events = read_events(cfg)
        assert len(events) == 2  # two valid lines, one skipped

    def test_blank_lines_skipped(self, tmp_path):
        log = tmp_path / "events.jsonl"
        log.write_text('\n\n{"action":"guide.checked","object":"x"}\n\n')
        cfg = {"evidence_path": str(log), "mock_mode": True}
        events = read_events(cfg)
        assert len(events) == 1

    def test_order_preserved(self, tmp_path):
        cfg = _config(tmp_path)
        for code in ("MSG001", "DIFF001", "TEST001"):
            emit(_make_event(violation_codes=[code]), cfg)
        events = read_events(cfg)
        codes = [e.violation_codes[0] for e in events]
        assert codes == ["MSG001", "DIFF001", "TEST001"]
