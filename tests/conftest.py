"""Shared fixtures that isolate tests from the user's git and Claude Code environment."""

from pathlib import Path

import pytest

from support import Repo


@pytest.fixture(autouse=True)
def _isolated_env(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    git_config = tmp_path_factory.mktemp("gitconfig") / "config"
    git_config.write_text("[init]\n\tdefaultBranch = main\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(git_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(tmp_path)
