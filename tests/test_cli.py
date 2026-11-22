"""CLI subcommands, exit codes, the Claude Code hook and the shipped examples."""

import io
import json
import sys
from pathlib import Path

import pytest

from project_docs import checker
from project_docs.cli import main
from project_docs.discovery import Doc
from project_docs.models import Diagnostic
from support import Repo, iso

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_check_exit_codes_and_json(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    repo.write("docs/guide.md", "[a](missing.md)\n")
    assert main(["check", str(repo.root), "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False and payload["checked_files"] == 1
    assert payload["diagnostics"] == [
        {
            "rule": "PD009",
            "path": "docs/guide.md",
            "line": 1,
            "message": "Local link target 'missing.md' does not exist.",
        }
    ]
    repo.write("docs/guide.md", "# Guide\n")
    assert main(["check", str(repo.root)]) == 0
    assert "no problems" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [[], ["check", "--strict"], ["check", "-q"], ["lint"], ["check", "missing-dir"]],
)
def test_usage_errors_exit_3(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    try:
        code = main(argv)
    except SystemExit as exc:
        code = int(exc.code or 0)
    assert code == 3
    assert "error" in capsys.readouterr().err


def test_config_error_exit_3(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    repo.write(".project-docs.toml", "docs_dir = 'documentation'\n")
    assert main(["check", str(repo.root)]) == 3
    assert "docs_dir" in capsys.readouterr().err


def test_map_lists_types(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    repo.write("AGENTS.md", "# Agents\n")
    repo.write("docs/findings/loss.md", "# Loss\n")
    assert main(["map", str(repo.root)]) == 0
    assert capsys.readouterr().out.split("\n")[:2] == [
        "entry          AGENTS.md",
        "finding        docs/findings/loss.md",
    ]


def test_init_then_check_passes(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["init", str(repo.root)]) == 0
    assert (repo.root / ".project-docs.toml").is_file()
    assert iso() in (repo.root / "docs" / "status.md").read_text(encoding="utf-8")
    assert main(["check", str(repo.root)]) == 0
    capsys.readouterr()

    (repo.root / "docs" / "status.md").write_text("custom\n", encoding="utf-8")
    assert main(["init", str(repo.root)]) == 0
    assert "already exist" in capsys.readouterr().out
    assert (repo.root / "docs" / "status.md").read_text(encoding="utf-8") == "custom\n"
    assert main(["init", str(repo.root), "--force"]) == 0
    assert iso() in (repo.root / "docs" / "status.md").read_text(encoding="utf-8")


def test_init_respects_existing_readme_index_and_pyproject_config(repo: Repo) -> None:
    repo.write("pyproject.toml", "[tool.project-docs]\nstatus_max_lines = 40\n")
    repo.write("docs/README.md", "# Docs\n\n- [Status](status.md) - current work and blockers\n")
    assert main(["init", str(repo.root), "--force"]) == 0
    assert not (repo.root / ".project-docs.toml").exists()
    assert not (repo.root / "docs" / "index.md").exists()
    assert main(["check", str(repo.root)]) == 0


# Hook --------------------------------------------------------------------------------------------


def _hook(monkeypatch: pytest.MonkeyPatch, event: object) -> int:
    raw = event if isinstance(event, str) else json.dumps(event)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    return main(["hook"])


def _edit(path: Path) -> dict[str, object]:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}


@pytest.fixture
def opted_in(repo: Repo) -> Repo:
    repo.git_init()
    repo.write(".project-docs.toml", "")
    repo.write("docs/status.md", "No date here.\n")
    repo.write("docs/guide.md", "# Guide\n")
    return repo


def test_hook_reports_only_the_edited_file(
    opted_in: Repo, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _hook(monkeypatch, _edit(opted_in.root / "docs" / "guide.md")) == 0
    assert _hook(monkeypatch, _edit(opted_in.root / "docs" / "status.md")) == 2
    err = capsys.readouterr().err
    assert "docs/status.md:1: PD004" in err and "guide.md" not in err


def test_hook_is_silent_without_config(
    opted_in: Repo, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (opted_in.root / ".project-docs.toml").unlink()
    assert _hook(monkeypatch, _edit(opted_in.root / "docs" / "status.md")) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "event",
    [
        {"tool_name": "Write", "tool_input": {"file_path": "/x/src/main.py"}},
        {"tool_name": "Bash", "tool_input": {"command": "ls"}},
        {"tool_name": "Edit"},
        [],
    ],
)
def test_hook_ignores_non_markdown_events(
    opted_in: Repo, monkeypatch: pytest.MonkeyPatch, event: object
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(opted_in.root))
    assert _hook(monkeypatch, event) == 0


def test_hook_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _hook(monkeypatch, "not json") == 3


def test_hook_ignores_files_outside_project_dir(
    opted_in: Repo, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    plans = tmp_path_factory.mktemp("plans")
    (plans / "docs").mkdir()
    (plans / "docs" / "status.md").write_text("No date.\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(opted_in.root))
    assert _hook(monkeypatch, _edit(plans / "docs" / "status.md")) == 0
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    assert _hook(monkeypatch, _edit(plans / "docs" / "status.md")) == 0


def test_hook_uses_claude_project_dir(
    opted_in: Repo, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(opted_in.root))
    assert _hook(monkeypatch, _edit(opted_in.root / "docs" / "status.md")) == 2
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(elsewhere))
    assert _hook(monkeypatch, _edit(opted_in.root / "docs" / "status.md")) == 0


def test_hook_ignores_relative_paths_and_blank_input(
    opted_in: Repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = {"cwd": str(opted_in.root), "tool_input": {"file_path": "docs/status.md"}}
    assert _hook(monkeypatch, event) == 0
    assert _hook(monkeypatch, "  \n") == 0


def test_hook_runs_per_file_rules_on_the_edited_file_only(
    opted_in: Repo, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    opted_in.write("docs/broken.md", "".join(f"[x{i}](missing-{i}.md)\n" for i in range(50)))
    opted_in.write("docs/findings/loss.md", "# Loss\n")
    opted_in.write("docs/index.md", "# Docs\n\n- [Status](status.md) - live state\n")
    checked: list[str] = []
    original = checker._check_local_links

    def spy(doc: Doc, root: Path, ignore: checker._IgnoreRules) -> list[Diagnostic]:
        checked.append(doc.rel)
        return original(doc, root, ignore)

    monkeypatch.setattr(checker, "_check_local_links", spy)
    assert _hook(monkeypatch, _edit(opted_in.root / "docs" / "index.md")) == 0
    assert checked == ["docs/index.md"]
    assert _hook(monkeypatch, _edit(opted_in.root / "docs" / "findings" / "loss.md")) == 2
    assert "PD007" in capsys.readouterr().err


def test_hook_stops_at_nested_git_boundary(opted_in: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    opted_in.git_init("baselines/nerf")
    nested = opted_in.write("baselines/nerf/docs/status.md", "No date.\n")
    assert _hook(monkeypatch, _edit(nested)) == 0
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(opted_in.root))
    assert _hook(monkeypatch, _edit(nested)) == 0


# Shipped content ---------------------------------------------------------------------------------


@pytest.mark.parametrize("target", [REPO_ROOT, REPO_ROOT / "examples" / "3d-recon-docs"])
def test_shipped_docs_pass(target: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(target)]) == 0, capsys.readouterr().out
