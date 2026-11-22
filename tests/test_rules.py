"""Positive and negative cases for each rule."""

import os
import posixpath
import subprocess
from pathlib import Path

import pytest

from project_docs.checker import link_path
from support import Repo, iso

STATUS = f"# Status\n\nAs of {iso()} (source: log).\n"
BANNER = "> Historical record, not current guidance. Read only when asked.\n"


# PD000 -------------------------------------------------------------------------------------------


def test_pd000_non_utf8_and_dangling_symlink(repo: Repo) -> None:
    (repo.root / "docs").mkdir()
    (repo.root / "docs" / "latin1.md").write_bytes(b"# Caf\xe9\n")
    (repo.root / "docs" / "dangling.md").symlink_to(repo.root / "missing.md")
    assert repo.found() == {("PD000", "docs/latin1.md"), ("PD000", "docs/dangling.md")}


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="needs a non-root POSIX user")
def test_pd000_permission_denied(repo: Repo) -> None:
    path = repo.write("docs/secret.md", "# Secret\n")
    path.chmod(0)
    try:
        assert repo.found() == {("PD000", "docs/secret.md")}
    finally:
        path.chmod(0o644)


def test_pd000_not_reported_for_bom(repo: Repo) -> None:
    (repo.root / "docs").mkdir()
    (repo.root / "docs" / "bom.md").write_bytes("﻿# Notes\n".encode())
    assert repo.check() == []


# PD001 -------------------------------------------------------------------------------------------

ENTRY_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "CLAUDE.local.md",
    ".claude/CLAUDE.md",
    "README.md",
    "README_zh.md",
    "docs/index.md",
    "docs/status.md",
]


@pytest.mark.parametrize("entry", ENTRY_FILES)
def test_pd001_entry_documents_must_not_link_archive(repo: Repo, entry: str) -> None:
    repo.write("docs/archive/old.md", BANNER)
    target = posixpath.relpath("docs/archive/old.md", posixpath.dirname(entry) or ".")
    repo.write(entry, f"As of {iso()}.\n\nSee [old]({target}).\n")
    assert ("PD001", entry) in repo.found()


def test_pd001_all_link_forms(repo: Repo) -> None:
    repo.write("docs/archive/old.md", BANNER)
    repo.write(
        "CLAUDE.md",
        "[a](docs/archive/old.md)\n"
        '<a href="docs/archive/old.md">b</a>\n'
        "@docs/archive/old.md\n"
        "[c]: docs/archive/old.md\n",
    )
    lines = sorted(d.line for d in repo.check() if d.rule == "PD001")
    assert lines == [1, 2, 3, 4]


def test_pd001_archive_by_config(repo: Repo) -> None:
    repo.write(".project-docs.toml", '[paths]\narchive = "history/**"\n')
    repo.write("history/v1.md", BANNER)
    repo.write("history/notes.pdf", "")
    repo.write("AGENTS.md", "[a](history/v1.md) [b](history/notes.pdf) [dir](history/)\n")
    assert [(d.rule, d.line) for d in repo.check()] == [("PD001", 1), ("PD001", 1)]


def test_pd001_allows_archive_index(repo: Repo) -> None:
    repo.write("docs/archive/index.md", "# Archive\n\n- [Old](old.md)\n")
    repo.write("docs/archive/old.md", BANNER)
    repo.write("docs/archive/2024/README.md", "# 2024\n")
    repo.write(
        "docs/index.md",
        "- [History](archive/index.md) - closed work, read only when asked.\n"
        "- [Archive folder](archive/) and [2024](archive/2024/README.md)\n",
    )
    repo.write("AGENTS.md", "@docs/archive/index.md\n")
    assert repo.check() == []


def test_pd001_ignores_non_entry_documents_and_code(repo: Repo) -> None:
    repo.write("docs/archive/old.md", BANNER)
    repo.write("docs/archive/index.md", "# Archive\n\n- [Old](old.md)\n")
    repo.write("docs/contracts/api.md", "Superseded by v2; see [v1](../archive/old.md).\n")
    repo.write(
        "AGENTS.md",
        "Never link `[x](docs/archive/old.md)` from here.\n\n"
        "```md\n[x](docs/archive/old.md)\n```\n\n"
        "<!-- [x](docs/archive/old.md) -->\n\n"
        "    [x](docs/archive/old.md)\n",
    )
    assert repo.check() == []


# PD002 -------------------------------------------------------------------------------------------


def test_pd002_archive_without_banner(repo: Repo) -> None:
    repo.write("docs/archive/old.md", "# Old design\n\n> Historical.\n")
    repo.write("docs/archive/fenced.md", "```\n> not a banner\n```\n")
    assert repo.found() == {("PD002", "docs/archive/old.md"), ("PD002", "docs/archive/fenced.md")}


@pytest.mark.parametrize(
    "text",
    [
        BANNER,
        f"\n\n   {BANNER}",
        f"---\narchived: 2025-01-01\n---\n\n{BANNER}",
        f"<!-- markdownlint-disable -->\n{BANNER}",
        "> 历史记录，非当前指导，仅在用户要求时阅读。\n",
    ],
)
def test_pd002_banner_accepted(repo: Repo, text: str) -> None:
    repo.write("docs/archive/old.md", text)
    assert repo.check() == []


def test_pd002_archive_index_needs_no_banner(repo: Repo) -> None:
    repo.write("docs/archive/index.md", "# Archive\n")
    repo.write("docs/archive/2024/README.md", "# 2024\n")
    assert repo.check() == []


# PD003 -------------------------------------------------------------------------------------------


def test_pd003_status_line_budget(repo: Repo) -> None:
    body = "\n".join(f"- item {i}" for i in range(59))
    repo.write("docs/status.md", f"As of {iso()}\n\n{body}\n\n\n")
    assert repo.check() == []
    repo.write("docs/status.md", f"As of {iso()}\n\n{body}\n- item 59\n")
    diags = repo.check()
    assert [(d.rule, d.line) for d in diags] == [("PD003", 62)]


def test_pd003_configured_budget_and_frontmatter_excluded(repo: Repo) -> None:
    repo.write(".project-docs.toml", "status_max_lines = 2\n")
    repo.write("docs/status.md", f"---\ntitle: Status\nowner: me\n---\nAs of {iso()}\n- one\n")
    assert repo.check() == []
    repo.write("docs/status.md", f"As of {iso()}\n- one\n- two\n")
    assert repo.found() == {("PD003", "docs/status.md")}


# PD004 -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"As of {iso()} (source: log).",
        f"截至{iso(-1)}（来源：训练日志）",
        f"Checked {iso(-3)}T14:02Z from the process list.",
        f"as-of {iso(1)}",
        f"---\nas_of: {iso(-2)}\n---\n# Status",
        f"As of {iso(-7)}.\n\nDeadline: {iso(30)}.",
    ],
)
def test_pd004_valid_as_of_date(repo: Repo, text: str) -> None:
    repo.write("docs/status.md", text + "\n")
    assert repo.check() == []


@pytest.mark.parametrize(
    "text",
    [
        "# Status\n\nTraining is running.",
        f"Planned: {iso(2)}",
        "As of 2025-02-30.",
        "Build 12025-01-01 and 2025-01-011.",
    ],
)
def test_pd004_missing_or_invalid_date(repo: Repo, text: str) -> None:
    repo.write("docs/status.md", text + "\n")
    assert repo.found() == {("PD004", "docs/status.md")}


# PD007 -------------------------------------------------------------------------------------------


def _index(repo: Repo, findings_section: str) -> None:
    repo.write("docs/findings/hashing.md", "# Hashing\n")
    repo.write("docs/index.md", f"# Docs\n\n## Findings\n\n{findings_section}\n")


@pytest.mark.parametrize(
    "item",
    [
        "- [Hashing](findings/hashing.md) - probes stay low below 0.70 load.",
        "* [Hashing](findings/hashing.md): x",
        "1. **[Hashing](findings/hashing.md)** — 负载低于 0.70 时探测稳定",
        "- [哈希](findings/hashing.md)：探测稳定",
        "| Topic | Conclusion |\n| --- | --- |\n| [Hashing](findings/hashing.md) | low probes |",
        "See [Hashing](findings/hashing.md) for why probes stay low.",
        "- [Hashing](findings/hashing.md) -\n  probes stay low below 0.70 occupancy.",
        "- [Hashing](findings/hashing.md)\n\tprobes stay low",
        "- Topics\n  - [Hashing](findings/hashing.md) (indoor) holds up",
        "- Topics\n\n    - [Hashing](findings/hashing.md) - nested after a blank line",
        "- [Hashing][h] - probes stay low.\n\n[h]: findings/hashing.md",
        '- <a href="findings/hashing.md">Hashing</a> probes stay low',
    ],
)
def test_pd007_listed_with_conclusion(repo: Repo, item: str) -> None:
    _index(repo, item)
    assert repo.check() == []


@pytest.mark.parametrize(
    ("item", "message"),
    [
        ("- [Hashing](findings/hashing.md)", "without a conclusion"),
        ("1. [Hashing](findings/hashing.md) —", "without a conclusion"),
        ("| [Hashing](findings/hashing.md) | |", "without a conclusion"),
        ("- [Hashing](findings/hashing.md) -\n- [Other](other.md) - next item", "without a"),
        ("- [Hashing](findings/hashing.md) -\n\n  probes stay low", "without a conclusion"),
        ("```\n- [Hashing](findings/hashing.md) - probes stay low\n```", "not listed"),
        ("<!-- - [Hashing](findings/hashing.md) - probes stay low -->", "not listed"),
        ("- [Records](records/) - all experiment records", "not listed"),
    ],
)
def test_pd007_not_listed_with_conclusion(repo: Repo, item: str, message: str) -> None:
    _index(repo, item)
    (diag,) = [d for d in repo.check() if d.rule == "PD007"]
    assert diag.path == "docs/findings/hashing.md"
    assert message in diag.message


def test_pd007_without_index(repo: Repo) -> None:
    repo.write("docs/findings/hashing.md", "# Hashing\n")
    (diag,) = repo.check()
    assert diag.rule == "PD007" and "no docs index" in diag.message


def test_pd007_scope(repo: Repo) -> None:
    repo.write(".project-docs.toml", '[paths]\nfinding = "docs/notes/*.md"\n')
    repo.write(
        "docs/README.md", "# Docs\n\n- [Loss](notes/loss.md) - focal loss helps rare classes\n"
    )
    repo.write("docs/notes/loss.md", "---\ntype: guide\n---\n# Loss\n")
    repo.write("docs/findings/README.md", "# Findings\n\nSee the docs index.\n")
    repo.write("docs/records/exp-1.md", "# Exp 1\n")
    assert repo.check() == []


# PD009 -------------------------------------------------------------------------------------------


def test_pd009_broken_links(repo: Repo) -> None:
    repo.write(
        "docs/guide.md",
        '[a](missing.md)\n![b](img/missing.png)\n<a href="gone.md">c</a>\n[d]: nowhere.md\n',
    )
    assert [(d.rule, d.line) for d in repo.check()] == [
        ("PD009", 1),
        ("PD009", 2),
        ("PD009", 3),
        ("PD009", 4),
    ]


def test_pd009_accepted_targets(repo: Repo) -> None:
    repo.write("docs/other.md", "# Other\n")
    repo.write("docs/my file.md", "# Spaced\n")
    repo.write("docs/notes(1).md", "# Parens\n")
    repo.write("docs/snake_case.md", "# Escaped\n")
    repo.write("README.md", "# Readme\n")
    repo.write(
        "docs/guide.md",
        "[anchor only](#nope) [missing anchor](other.md#nope) [query](other.md?raw=1)\n"
        "[encoded](my%20file.md) [angle](<my file.md>) [parens](notes(1).md)\n"
        "[escaped](snake\\_case.md)\n"
        '[title](other.md "Other page") [dir](./) [up](../README.md)\n'
        "[outside](../../../outside.md) [absolute](/nowhere.md) [home](~/x.md) [nul](a%00.md)\n"
        "[web](https://example.com/x.md) [mail](mailto:a@example.com) [ftp](ftp://h/x)\n"
        "@missing/import.md is only an archive-boundary concern.\n",
    )
    assert repo.check() == []


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("%2Fetc%2Fhosts", None),
        ("%2E%2E/%2E%2E/x.md", None),
        ("..%2F..%2Fx.md", None),
        ("%7E/x.md", None),
        ("%2E%2E/README.md", "README.md"),
        ("sub%2Fpage.md#top", "docs/sub/page.md"),
    ],
)
def test_link_path_decodes_before_checking(target: str, expected: str | None) -> None:
    assert link_path("docs/a.md", target) == expected


def test_encoded_absolute_target_does_not_escape_root(repo: Repo) -> None:
    repo.write("docs/guide.md", "[x](%2Fnonexistent-target-for-test.md)\n")
    assert repo.check() == []


def test_pd009_skips_archive_files(repo: Repo) -> None:
    repo.write("docs/archive/old.md", f"{BANNER}\n[gone](deleted.md)\n")
    repo.write("docs/archive/index.md", "- [gone](deleted.md)\n")
    assert repo.found() == {("PD009", "docs/archive/index.md")}


def _git_ok() -> bool:
    return subprocess.run(["git", "--version"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _git_ok(), reason="git is required")
def test_pd009_skips_gitignored_targets(repo: Repo) -> None:
    repo.git_init()
    repo.write(".gitignore", "outputs/\n*.ckpt\n")
    repo.write(
        "docs/run.md",
        "[plot](../outputs/run-3/plot.png) [ckpt](../model.ckpt) [dir](../outputs)\n",
    )
    assert repo.check() == []


@pytest.mark.skipif(not _git_ok(), reason="git is required")
def test_pd009_skips_targets_git_cannot_decide(repo: Repo) -> None:
    repo.git_init()
    gitlink = "160000,0123456789012345678901234567890123456789,ext/lib"
    subprocess.run(
        ["git", "update-index", "--add", "--cacheinfo", gitlink], cwd=repo.root, check=True
    )
    repo.write("docs/run.md", "[lib](../ext/lib/README.md) [gone](missing.md)\n")
    assert [d.message for d in repo.check()] == ["Local link target 'missing.md' does not exist."]


@pytest.mark.skipif(not _git_ok(), reason="git is required")
def test_pd009_ignores_global_excludes_file(
    repo: Repo, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path_factory.mktemp("home")
    (home / "ignore").write_text("missing.md\n", encoding="utf-8")
    (home / "config").write_text(f"[core]\n\texcludesFile = {home / 'ignore'}\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "config"))
    repo.git_init()
    repo.write("docs/run.md", "[gone](missing.md)\n")
    assert repo.found() == {("PD009", "docs/run.md")}


def test_pd009_reports_ignored_pattern_outside_git(repo: Repo) -> None:
    repo.write(".gitignore", "outputs/\n")
    repo.write("docs/run.md", "[plot](../outputs/plot.png)\n")
    assert repo.found() == {("PD009", "docs/run.md")}


def test_checks_are_scoped_to_repo_root(repo: Repo, tmp_path: Path) -> None:
    repo.write("docs/guide.md", f"[sibling](../../{tmp_path.name}-sibling/x.md)\n")
    assert repo.check() == []
