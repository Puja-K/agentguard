"""Tests for repository-local AgentGuard configuration."""

from pathlib import Path

import pytest

from agentguard.config import AgentGuardConfig, ConfigError, load_config


def test_missing_config_uses_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path)

    assert config == AgentGuardConfig()


def test_empty_config_uses_defaults(tmp_path: Path) -> None:
    (tmp_path / "agentguard.toml").write_text("", encoding="utf-8")

    assert load_config(tmp_path) == AgentGuardConfig()


def test_valid_config_loads_typed_values(tmp_path: Path) -> None:
    (tmp_path / "agentguard.toml").write_text(
        'include = ["src/**/*.py"]\nexclude = ["vendor/**"]\n',
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.include == ("src/**/*.py",)
    assert config.exclude == ("vendor/**",)


@pytest.mark.parametrize(
    ("contents", "expected_message"),
    [
        ('include = ["unterminated]\n', "Unable to read configuration"),
        ('include = "**/*.py"\n', "Invalid configuration"),
        ("unexpected = true\n", "Invalid configuration"),
    ],
)
def test_invalid_config_is_rejected(
    tmp_path: Path,
    contents: str,
    expected_message: str,
) -> None:
    config_path = tmp_path / "agentguard.toml"
    config_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ConfigError, match=expected_message) as error:
        load_config(tmp_path)

    assert str(config_path) in str(error.value)


def test_unreadable_config_has_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "agentguard.toml"
    config_path.touch()
    original_read_text = Path.read_text

    def fail_for_config(path: Path, *args: object, **kwargs: object) -> str:
        if path == config_path:
            raise PermissionError("permission denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_for_config)

    with pytest.raises(ConfigError, match="permission denied"):
        load_config(tmp_path)


def test_config_is_loaded_from_supplied_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repository"
    other_root = tmp_path / "other"
    repository_root.mkdir()
    other_root.mkdir()
    (repository_root / "agentguard.toml").write_text(
        'include = ["repository/**"]\n', encoding="utf-8"
    )
    (other_root / "agentguard.toml").write_text('include = ["other/**"]\n', encoding="utf-8")
    monkeypatch.chdir(other_root)

    assert load_config(repository_root).include == ("repository/**",)


def test_loading_config_does_not_execute_python_or_create_state(tmp_path: Path) -> None:
    sentinel = tmp_path / "executed"
    (tmp_path / "agentguard.toml").write_text('include = ["**/*.py"]\n', encoding="utf-8")
    (tmp_path / "target.py").write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n",
        encoding="utf-8",
    )

    load_config(tmp_path)

    assert not sentinel.exists()
    assert not (tmp_path / ".agentguard").exists()
