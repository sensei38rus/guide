from __future__ import annotations
import os
from pathlib import Path
from typing import Any

import yaml

# Path to the bundled default config (relative to this file's package root)
_DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "configs" / "guide.default.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


def _apply_env(config: dict) -> dict:
    
    config = dict(config)

    mock_mode = os.environ.get("GUIDE_MOCK_MODE")
    if mock_mode is not None:
        config["mock_mode"] = mock_mode.lower() in ("1", "true", "yes")

    sink = os.environ.get("GUIDE_EVIDENCE_SINK")
    if sink is not None:
        config["evidence_sink"] = sink

    evidence_path = os.environ.get("GUIDE_EVIDENCE_PATH")
    if evidence_path:
        config["evidence_path"] = evidence_path

    return config


def load_config(repo_root: Path | None = None) -> dict[str, Any]:
    """Load and return the merged configuration dictionary.

    Args:
        repo_root: Path to the Git repository root. When *None*, the current
                   working directory is used.

    Returns:
        Merged configuration dictionary.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    # 1. Start with bundled defaults
    config = _load_yaml(_DEFAULT_CONFIG) if _DEFAULT_CONFIG.exists() else {}

    # 2. Merge project-level config if present
    project_config_path_env = os.environ.get("GUIDE_CONFIG_PATH")
    if project_config_path_env:
        project_config_path = Path(project_config_path_env)
    else:
        project_config_path = repo_root / "guide.yaml"

    if project_config_path.exists():
        project_config = _load_yaml(project_config_path)
        config = _deep_merge(config, project_config)

    # 3. Apply env var overrides
    config = _apply_env(config)

    # Ensure required top-level keys have defaults
    config.setdefault("mock_mode", True)
    config.setdefault("evidence_sink", "file")
    config.setdefault(
        "evidence_path",
        str(Path.home() / ".guide" / "events.jsonl"),
    )

    return config


def get_strictness(config: dict) -> str:
    """Return the configured strictness level ('warn' or 'block')."""
    return config.get("strictness", {}).get("default_level", "warn")
