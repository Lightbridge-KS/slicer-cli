"""Layered config loading: flag > env > project-toml > user-toml > built-in."""

from __future__ import annotations

from pathlib import Path

from slicer_cli.config import load_config


def test_builtin_defaults_permissive_exec() -> None:
    config = load_config(env={}, user_config_path=Path("/nonexistent"))
    assert config.exec.enabled is True  # permissive default — operators can disable
    assert config.server.url == "http://127.0.0.1:2016"


def test_env_overrides_builtin() -> None:
    config = load_config(
        env={"SLICER_URL": "http://example:1234", "SLICER_EXEC_ENABLED": "false"},
        user_config_path=Path("/nonexistent"),
    )
    assert config.server.url == "http://example:1234"
    assert config.exec.enabled is False


def test_user_toml_overrides_builtin(tmp_path: Path) -> None:
    user_toml = tmp_path / "config.toml"
    user_toml.write_text(
        '[server]\nurl = "http://from-user:1"\n\n[exec]\nenabled = false\n',
        encoding="utf-8",
    )

    config = load_config(env={}, user_config_path=user_toml)
    assert config.server.url == "http://from-user:1"
    assert config.exec.enabled is False


def test_env_overrides_user_toml(tmp_path: Path) -> None:
    user_toml = tmp_path / "config.toml"
    user_toml.write_text(
        '[server]\nurl = "http://from-user:1"\n',
        encoding="utf-8",
    )

    config = load_config(
        env={"SLICER_URL": "http://from-env:2"},
        user_config_path=user_toml,
    )
    assert config.server.url == "http://from-env:2"


def test_overrides_win(tmp_path: Path) -> None:
    user_toml = tmp_path / "config.toml"
    user_toml.write_text('[server]\nurl = "http://from-user:1"\n', encoding="utf-8")

    config = load_config(
        env={"SLICER_URL": "http://from-env:2"},
        user_config_path=user_toml,
        overrides={"server": {"url": "http://from-flag:3"}},
    )
    assert config.server.url == "http://from-flag:3"


def test_project_toml_between_env_and_user(tmp_path: Path) -> None:
    user_toml = tmp_path / "user.toml"
    user_toml.write_text('[server]\nurl = "http://user:1"\n', encoding="utf-8")

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / ".slicer-cli.toml").write_text(
        '[server]\nurl = "http://project:2"\n', encoding="utf-8"
    )

    config = load_config(env={}, user_config_path=user_toml, project_dir=project_dir)
    assert config.server.url == "http://project:2"

    config2 = load_config(
        env={"SLICER_URL": "http://env:3"},
        user_config_path=user_toml,
        project_dir=project_dir,
    )
    assert config2.server.url == "http://env:3"
