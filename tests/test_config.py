"""Unit tests for guide/config.py."""

import os
from pathlib import Path

import pytest
import yaml

from guide.config import load_config, get_strictness, _deep_merge



class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 99, "c": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_nested_merge(self):
        base = {"commit_message": {"min_description_length": 10, "require_conventional": True}}
        override = {"commit_message": {"min_description_length": 20}}
        result = _deep_merge(base, override)
        assert result["commit_message"]["min_description_length"] == 20
        assert result["commit_message"]["require_conventional"] is True

    def test_does_not_mutate_base(self):
        base = {"a": {"x": 1}}
        override = {"a": {"x": 99}}
        _deep_merge(base, override)
        assert base["a"]["x"] == 1




class TestLoadConfigDefaults:
    def test_returns_dict(self, tmp_path):
        config = load_config(repo_root=tmp_path)
        assert isinstance(config, dict)

    def test_mock_mode_default(self, tmp_path):
        config = load_config(repo_root=tmp_path)
        assert config["mock_mode"] is True

    def test_evidence_sink_default(self, tmp_path):
        config = load_config(repo_root=tmp_path)
        assert config["evidence_sink"] == "file"

    def test_evidence_path_default(self, tmp_path):
        config = load_config(repo_root=tmp_path)
        assert "events.jsonl" in config["evidence_path"]

    def test_commit_message_section_present(self, tmp_path):
        config = load_config(repo_root=tmp_path)
        assert "commit_message" in config

    def test_diff_section_present(self, tmp_path):
        config = load_config(repo_root=tmp_path)
        assert "diff" in config




class TestLoadConfigProjectOverride:
    def test_project_config_overrides_defaults(self, tmp_path):
        override = {"diff": {"max_lines": 50}}
        (tmp_path / "guide.yaml").write_text(yaml.dump(override))
        config = load_config(repo_root=tmp_path)
        assert config["diff"]["max_lines"] == 50

    def test_project_config_preserves_unset_defaults(self, tmp_path):
        override = {"diff": {"max_lines": 50}}
        (tmp_path / "guide.yaml").write_text(yaml.dump(override))
        config = load_config(repo_root=tmp_path)
        assert "commit_message" in config  # default still present

    def test_no_project_config_is_fine(self, tmp_path):
        config = load_config(repo_root=tmp_path)
        assert config is not None




class TestLoadConfigEnvOverrides:
    def test_guide_mock_mode_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GUIDE_MOCK_MODE", "false")
        config = load_config(repo_root=tmp_path)
        assert config["mock_mode"] is False

    def test_guide_mock_mode_true_variants(self, tmp_path, monkeypatch):
        for val in ("true", "1", "yes", "True", "YES"):
            monkeypatch.setenv("GUIDE_MOCK_MODE", val)
            config = load_config(repo_root=tmp_path)
            assert config["mock_mode"] is True, f"Failed for GUIDE_MOCK_MODE={val!r}"

    def test_guide_evidence_sink(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GUIDE_EVIDENCE_SINK", "webhook")
        config = load_config(repo_root=tmp_path)
        assert config["evidence_sink"] == "webhook"

    def test_guide_evidence_path(self, tmp_path, monkeypatch):
        custom_path = str(tmp_path / "custom_events.jsonl")
        monkeypatch.setenv("GUIDE_EVIDENCE_PATH", custom_path)
        config = load_config(repo_root=tmp_path)
        assert config["evidence_path"] == custom_path

    def test_guide_config_path_env(self, tmp_path, monkeypatch):
        custom_cfg = tmp_path / "my_guide.yaml"
        custom_cfg.write_text(yaml.dump({"diff": {"max_lines": 9}}))
        monkeypatch.setenv("GUIDE_CONFIG_PATH", str(custom_cfg))
        config = load_config(repo_root=tmp_path)
        assert config["diff"]["max_lines"] == 9



class TestGetStrictness:
    def test_default_strictness(self, tmp_path):
        config = load_config(repo_root=tmp_path)
        assert get_strictness(config) in ("warn", "block")

    def test_explicit_block(self):
        config = {"strictness": {"default_level": "block"}}
        assert get_strictness(config) == "block"

    def test_explicit_warn(self):
        config = {"strictness": {"default_level": "warn"}}
        assert get_strictness(config) == "warn"

    def test_missing_strictness_key(self):
        assert get_strictness({}) == "warn"
