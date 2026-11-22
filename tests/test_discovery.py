"""Configuration loading, discovery scope and document classification."""

import pytest

from project_docs.config import glob_match, load_config
from project_docs.discovery import discover
from project_docs.models import ConfigError, DocType
from support import Repo, iso


def _types(repo: Repo) -> dict[str, DocType]:
    return {doc.rel: doc.doc_type for doc in discover(load_config(repo.root))}


@pytest.mark.parametrize(
    ("toml", "fragment"),
    [
        ("ignore = ['PD006']\n", "unknown key(s) ignore"),
        ("status_max_lines = '60'\n", "'status_max_lines' must be a positive integer"),
        ("status_max_lines = 0\n", "'status_max_lines' must be a positive integer"),
        ("status_max_lines = true\n", "'status_max_lines' must be a positive integer"),
        ("exclude = 'x/**'\n", "'exclude' must be a list of glob strings"),
        ("paths = 'docs'\n", "'paths' must be a table"),
        ("[paths]\nfindings = 'x/**'\n", "unknown document type 'paths.findings'"),
        ("[paths]\nfinding = 3\n", "'paths.finding' must be a glob string or list of globs"),
        ("status_max_lines = \n", "cannot read .project-docs.toml"),
    ],
)
def test_config_errors_name_key_and_expected_type(repo: Repo, toml: str, fragment: str) -> None:
    repo.write(".project-docs.toml", toml)
    with pytest.raises(ConfigError) as excinfo:
        load_config(repo.root)
    assert fragment in str(excinfo.value)


def test_config_precedence(repo: Repo) -> None:
    assert load_config(repo.root).explicit is False
    repo.write("pyproject.toml", "[project]\nname = 'project-docs-user'\n")
    assert load_config(repo.root).explicit is False
    repo.write("pyproject.toml", "[tool.project-docs]\nstatus_max_lines = 1\n")
    assert load_config(repo.root).status_max_lines == 1
    repo.write(".project-docs.toml", "status_max_lines = 7\n")
    config = load_config(repo.root)
    assert (config.explicit, config.status_max_lines) == (True, 7)


def test_pyproject_errors(repo: Repo) -> None:
    repo.write("pyproject.toml", "[tool]\nproject-docs = 3\n")
    with pytest.raises(ConfigError, match="expected a table"):
        load_config(repo.root)
    repo.write("pyproject.toml", "[tool.project-docs]\nstrict = true\n")
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(repo.root)


def test_discovery_scope(repo: Repo) -> None:
    for rel in [
        "README.md",
        "readme-ja.md",
        "AGENTS.md",
        "CLAUDE.local.md",
        ".claude/CLAUDE.md",
        ".claude/skills/x/SKILL.md",
        "src/pkg/AGENTS.md",
        "src/pkg/CLAUDE.md",
        "src/pkg/notes.md",
        "CHANGELOG.md",
        "docs/index.md",
        "docs/status.md",
        "docs/README.md",
        "docs/AGENTS.md",
        "docs/contracts/api.md",
        "docs/guides/run.md",
        "docs/records/exp-1.md",
        "docs/findings/loss.md",
        "docs/findings/index.md",
        "docs/archive/index.md",
        "docs/archive/old.md",
        "docs/adr/0001.md",
        "docs/sub/status.md",
        "docs/.vitepress/theme.md",
        "docs/node_modules/pkg/README.md",
        "docs/notes.txt",
    ]:
        repo.write(rel, "# Doc\n")
    assert _types(repo) == {
        ".claude/CLAUDE.md": DocType.ENTRY,
        "AGENTS.md": DocType.ENTRY,
        "CLAUDE.local.md": DocType.ENTRY,
        "README.md": DocType.ENTRY,
        "readme-ja.md": DocType.ENTRY,
        "docs/index.md": DocType.INDEX,
        "docs/README.md": DocType.INDEX,
        "docs/AGENTS.md": DocType.OTHER,
        "docs/status.md": DocType.STATUS,
        "docs/contracts/api.md": DocType.CONTRACT,
        "docs/guides/run.md": DocType.GUIDE,
        "docs/records/exp-1.md": DocType.RECORD,
        "docs/findings/loss.md": DocType.FINDING,
        "docs/findings/index.md": DocType.OTHER,
        "docs/archive/index.md": DocType.ARCHIVE_INDEX,
        "docs/archive/old.md": DocType.ARCHIVE,
        "docs/adr/0001.md": DocType.OTHER,
        "docs/sub/status.md": DocType.OTHER,
    }


def test_classification_uses_paths_then_convention(repo: Repo) -> None:
    repo.write(
        ".project-docs.toml",
        '[paths]\nstatus = "/STATUS.md"\nfinding = ["notes/findings/**"]\n'
        'guide = "docs/records/"\n',
    )
    repo.write("STATUS.md", "# Status\n")
    repo.write("notes/findings/loss.md", "# Loss\n")
    repo.write("notes/other.md", "# Not configured\n")
    repo.write("docs/records/howto.md", "# How to\n")
    repo.write("docs/records/exp.md", "---\ntype: guide\n---\n# Exp\n")
    repo.write("docs/guides/plan.md", "---\ntype: status\n---\n# Plan\n")
    assert _types(repo) == {
        "STATUS.md": DocType.STATUS,
        "notes/findings/loss.md": DocType.FINDING,
        "docs/records/howto.md": DocType.RECORD,
        "docs/records/exp.md": DocType.RECORD,
        "docs/guides/plan.md": DocType.GUIDE,
    }
    assert {(d.rule, d.path) for d in repo.check()} == {
        ("PD004", "STATUS.md"),
        ("PD007", "notes/findings/loss.md"),
    }


def test_exclude_prunes_files_and_directories(repo: Repo) -> None:
    repo.write(".project-docs.toml", 'exclude = ["docs/drafts/", "**/scratch-*.md"]\n')
    repo.write("docs/drafts/a/x.md", "[broken](nope.md)\n")
    repo.write("docs/guides/scratch-1.md", "[broken](nope.md)\n")
    repo.write("docs/guides/run.md", "# Run\n")
    assert list(_types(repo)) == ["docs/guides/run.md"]


@pytest.mark.parametrize("marker", ["dir", "file"])
def test_nested_repositories_are_skipped(repo: Repo, marker: str) -> None:
    repo.write(".project-docs.toml", '[paths]\nfinding = "vendor/lib/docs/**"\n')
    for nested in ("docs/third-party", "vendor/lib"):
        if marker == "dir":
            (repo.root / nested / ".git").mkdir(parents=True)
        else:
            repo.write(f"{nested}/.git", "gitdir: ../../.git/modules/x\n")
    repo.write("docs/third-party/README.md", "[broken](nope.md)\n")
    repo.write("vendor/lib/docs/finding.md", "[broken](nope.md)\n")
    repo.write("docs/guide.md", f"Checked {iso()}.\n")
    assert list(_types(repo)) == ["docs/guide.md"]
    assert repo.check() == []


def test_docs_that_is_a_repository_or_symlink_is_skipped(
    repo: Repo, tmp_path_factory: pytest.TempPathFactory
) -> None:
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    (elsewhere / "status.md").write_text("no date\n", encoding="utf-8")
    (repo.root / "docs").symlink_to(elsewhere, target_is_directory=True)
    repo.write("README.md", "# Readme\n")
    assert list(_types(repo)) == ["README.md"]
    (repo.root / "docs").unlink()
    repo.write("docs/.git/HEAD", "ref: refs/heads/main\n")
    repo.write("docs/status.md", "no date\n")
    assert list(_types(repo)) == ["README.md"]


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("docs/a.md", "docs/*.md", True),
        ("docs/sub/a.md", "docs/*.md", False),
        ("docs/sub/a.md", "docs/**/*.md", True),
        ("docs/a.md", "docs/**/*.md", True),
        ("history", "history/**", True),
        ("history/x/y.md", "history/**", True),
        ("historyx/y.md", "history/**", False),
        ("a/b/scratch-1.md", "**/scratch-?.md", True),
        ("STATUS.md", "./STATUS.md", True),
        ("STATUS.md", "/STATUS.md", True),
        ("docs/drafts", "docs/drafts/", True),
        ("docs/drafts", "/docs/drafts/", True),
    ],
)
def test_glob_match(path: str, pattern: str, expected: bool) -> None:
    assert glob_match(path, pattern) is expected
