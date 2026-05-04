"""Layered configuration loader.

Precedence (highest first):
  1. CLI flags (handled in cli/app.py — passed via overrides)
  2. Environment variables (SLICER_URL, SLICER_TIMEOUT, SLICER_EXEC_*)
  3. Project-local .slicer-cli.toml (cwd or first ancestor)
  4. User config ~/.config/slicer-cli/config.toml
  5. Built-in defaults below

`exec.enabled` defaults to True so `slicer-cli exec` works out of the box;
operators who want to lock arbitrary Python execution down should set
`exec.enabled = false` in user or project config (or via
`SLICER_EXEC_ENABLED=false`). The `--i-understand-the-risk` flag overrides
the gate per-invocation.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from slicer_cli.client.errors import SlicerConfigError

PROJECT_CONFIG_NAME: str = ".slicer-cli.toml"
USER_CONFIG_PATH: Path = Path.home() / ".config" / "slicer-cli" / "config.toml"


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = "http://127.0.0.1:2016"
    timeout_seconds: float = 30.0
    discover_alt_ports: bool = False  # Phase 4


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default: str = "pretty"  # "pretty" | "json"
    include_meta: bool = False


class ExecConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True  # permissive default; gate with `enabled = false` to lock down
    audit_log: str = "~/.local/state/slicer-cli/exec.log"


class RenderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_size: int = 512
    default_view: str = "red"


class AppConfig(BaseModel):
    """Frozen, validated settings used everywhere downstream."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    server: ServerConfig = Field(default_factory=ServerConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    exec: ExecConfig = Field(default_factory=ExecConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)


def load_config(
    *,
    overrides: dict[str, Any] | None = None,
    project_dir: Path | None = None,
    user_config_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> AppConfig:
    """Load merged config. Later sources take precedence; see module docstring."""
    env_map = env if env is not None else dict(os.environ)
    user_path = user_config_path if user_config_path is not None else USER_CONFIG_PATH

    layered: dict[str, Any] = {}
    _deep_merge(layered, _read_toml(user_path))
    _deep_merge(layered, _read_toml(_find_project_config(project_dir)))
    _deep_merge(layered, _from_env(env_map))
    if overrides:
        _deep_merge(layered, overrides)

    try:
        return AppConfig.model_validate(layered)
    except Exception as exc:  # pydantic validation
        raise SlicerConfigError(f"Invalid configuration: {exc}") from exc


def config_paths() -> dict[str, str]:
    """Inspect-only helper: report which files were considered."""
    project = _find_project_config(None)
    return {
        "user": str(USER_CONFIG_PATH),
        "user_exists": str(USER_CONFIG_PATH.exists()),
        "project": str(project) if project else "",
        "project_exists": str(bool(project and project.exists())),
    }


# ---------------------------------------------------------------- internal helpers


def _find_project_config(start: Path | None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        candidate = directory / PROJECT_CONFIG_NAME
        if candidate.is_file():
            return candidate
    return None


def _read_toml(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise SlicerConfigError(f"Could not parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SlicerConfigError(f"Expected a TOML table at {path}, got {type(data).__name__}")
    return data


def _from_env(env: dict[str, str]) -> dict[str, Any]:
    """Map a small, explicit set of env vars to config keys."""
    out: dict[str, Any] = {}
    if (url := env.get("SLICER_URL")) is not None:
        out.setdefault("server", {})["url"] = url
    if (timeout := env.get("SLICER_TIMEOUT")) is not None:
        out.setdefault("server", {})["timeout_seconds"] = _coerce_float(timeout, "SLICER_TIMEOUT")
    if (exec_enabled := env.get("SLICER_EXEC_ENABLED")) is not None:
        out.setdefault("exec", {})["enabled"] = _coerce_bool(exec_enabled, "SLICER_EXEC_ENABLED")
    return out


def _coerce_bool(raw: str, key: str) -> bool:
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise SlicerConfigError(f"Could not parse boolean for {key}: {raw!r}")


def _coerce_float(raw: str, key: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise SlicerConfigError(f"Could not parse number for {key}: {raw!r}") from exc


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
