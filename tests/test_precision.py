"""Precision corpus: ordinary, healthy documentation must produce zero diagnostics."""

from urllib.parse import quote

import pytest

from support import Repo, iso

BANNER = "> Historical record, not current guidance. Read only when asked.\n"


def mkdocs_site() -> dict[str, str]:
    return {
        "mkdocs.yml": "site_name: Demo\nnav:\n  - index.md\n",
        "docs/index.md": (
            "# Demo\n\n"
            "Start with [Getting started](getting-started.md) or the "
            "[API reference](api/reference.md#functions).\n\n"
            '!!! note "Heads up"\n'
            "    Admonition bodies are indented, see [setup](getting-started.md#install).\n\n"
            '=== "pip"\n\n'
            "    ```bash\n    pip install demo  # [x](missing.md)\n    ```\n\n"
            '=== "uv"\n\n'
            "    ```bash\n    uv add demo\n    ```\n\n"
            '![Architecture](img/arch.svg){ width="600" }\n\n'
            '--8<-- "snippets/footer.md"\n\n'
            "[Edit this page](https://github.com/org/demo/edit/main/docs/index.md)\n"
        ),
        "docs/getting-started.md": (
            "# Getting started { #start }\n\n"
            '## Install\n\nRead the [reference](api/reference.md#demo.load "API").\n\n'
            "| Option | Description |\n| ------ | ----------- |\n"
            "| `--fast` | See [tuning](api/reference.md#tuning) |\n"
        ),
        "docs/api/reference.md": (
            "# Reference\n\n::: demo.load\n\n## Tuning\n\n"
            "Back to [home](../index.md) or [start](../getting-started.md#start).\n"
        ),
        "docs/img/arch.svg": "<svg/>\n",
    }


def adr_with_considered_options() -> dict[str, str]:
    return {
        "docs/contracts/schema.md": "# Metadata schema\n\nTables `runs` and `artifacts`.\n",
        "docs/contracts/adr-0001-postgres.md": (
            "---\nstatus: accepted\ndate: 2025-03-14\n---\n"
            "# Use PostgreSQL for metadata\n\n"
            "## Context and Problem Statement\n\nRuns are written by many workers at once.\n\n"
            "## Considered Options\n\n* PostgreSQL\n* SQLite\n* MongoDB\n\n"
            "## Decision Outcome\n\n"
            'Chosen option: "PostgreSQL", because it handles concurrent writers. '
            "See the [schema](schema.md).\n\n"
            "## Pros and Cons of the Options\n\n### SQLite\n\n"
            "* Good, because it needs no server.\n"
            "* Bad, because concurrent writers were ruled out by the lock contention test.\n"
        ),
    }


def agents_md_with_changelog_rules() -> dict[str, str]:
    return {
        "AGENTS.md": (
            "# AGENTS.md\n\n"
            "Read @docs/index.md first; current work is in [status](docs/status.md).\n\n"
            "## Changelog\n\n"
            "- Keep `CHANGELOG.md` in [Keep a Changelog](https://keepachangelog.com/) format.\n"
            "- Add entries under `## [Unreleased]`; a release becomes `## [1.4.0] - 2026-01-15`.\n"
            "- Update (2026-03-01) entries belong in CHANGELOG.md, never in docs.\n\n"
            "## Deprecations\n\n"
            '- Mark deprecated APIs with `@deprecated("use load_v2")` and a DeprecationWarning.\n'
            "- [deprecated] tags in docstrings must name the replacement.\n"
            "- Superseded endpoints are removed in 3.0; see [the guide](docs/guides/api.md).\n\n"
            "## History\n\n"
            "Old designs live in `docs/archive/`. Do not read them unless asked.\n"
        ),
        "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n### Deprecated\n\n- `load()`\n",
        "docs/index.md": "# Docs\n\n- [API guide](guides/api.md) - how to call the service.\n",
        "docs/status.md": f"# Status\n\nAs of {iso()} (source: CI run).\n\n- Next: ship 3.0.\n",
        "docs/guides/api.md": "# API\n\n`load_v2()` replaces `load()`.\n",
        "docs/archive/v1-api.md": BANNER + "\n# v1 API\n",
    }


def chinese_docs() -> dict[str, str]:
    finding = "体素哈希.md"
    return {
        "docs/index.md": (
            "# 文档索引\n\n当前进展见[状态页](status.md)。\n\n## 发现\n\n"
            f"- [体素哈希负载因子](findings/{finding})：占用率不超过 0.70 时探测次数稳定。\n"
            "- [截断调度](findings/truncation.md) —— 前 30% 帧从 12 cm 退火到 4 cm，F 值提升。\n\n"
            "## 记录\n\n- [实验 009](records/exp-009.md)\n"
        ),
        "docs/status.md": (
            f"# 状态\n\n截至{iso(-1)}（来源：训练日志 `logs/run-3.log`）。\n\n## 进行中\n\n"
            f"- 户外哈希压缩：内核已通过碰撞单测；下一步测大场景显存，截止 {iso(14)}。\n"
        ),
        f"docs/findings/{finding}": "# 体素哈希\n\n证据：[实验 009](../records/exp-009.md)。\n",
        "docs/findings/truncation.md": "# 截断调度\n\n证据见记录。\n",
        "docs/records/exp-009.md": (
            f"# 实验 009\n\n结论见[发现](../findings/{quote(finding)})。\n"
        ),
        "docs/archive/旧方案.md": "> 历史记录，非当前指导，仅在用户要求时阅读。\n\n# 八叉树方案\n",
    }


def grouped_findings_index() -> dict[str, str]:
    names = ["load-factor", "probe-chains", "eviction", "focal", "dice", "depth-noise", "warmup"]
    files = {f"docs/findings/{name}.md": f"# {name}\n" for name in names}
    files["docs/findings/README.md"] = "# Findings\n\nListed in the [docs index](../index.md).\n"
    files["docs/status.md"] = f"---\nupdated: {iso()}\n---\n# Status\n\n- Idle.\n"
    files["docs/index.md"] = (
        "# Docs\n\n- [Status](status.md) - live state.\n\n## Findings\n\n### Hashing\n\n"
        "- [Load factor](findings/load-factor.md) — probes stay near 1.3 up to 0.70 occupancy.\n"
        "- **Probing**\n"
        "  - [Probe chains](findings/probe-chains.md): bounded below warp width at 0.70 load.\n"
        "  - Eviction\n"
        "    - [Cuckoo](findings/eviction.md) | evicts on 18% of inserts\n\n"
        "### Losses\n\n"
        "1. [Focal loss](findings/focal.md) (rare classes) improves recall by 4 points.\n"
        '2. <a href="findings/dice.md">Dice loss</a> stabilizes thin structures.\n\n'
        "* Data\n"
        "    * [Depth noise](findings/depth-noise.md) - sensor noise dominates beyond 4 m.\n\n"
        "- Optimization\n\n"
        "    - [Warmup](findings/warmup.md) - 500 warmup steps remove early divergence.\n\n"
        "| Topic | Conclusion |\n| --- | --- |\n"
        "| [Load factor](findings/load-factor.md) | Also listed in a table. |\n"
    )
    return files


def third_party_checkouts() -> dict[str, str]:
    return {
        "README.md": "# Project\n\nBaseline: [3DGS](baselines/gaussian-splatting/README.md).\n",
        "baselines/gaussian-splatting/.git/HEAD": "ref: refs/heads/main\n",
        "baselines/gaussian-splatting/README.md": "[broken](missing.md)\n",
        "baselines/gaussian-splatting/AGENTS.md": "[old](docs/archive/x.md) [gone](nope.md)\n",
        "baselines/gaussian-splatting/docs/status.md": "No date.\n" * 100,
        "baselines/gaussian-splatting/docs/findings/x.md": "# Unlisted\n",
        "docs/vendor-api/.git": "gitdir: ../../.git/modules/vendor-api\n",
        "docs/vendor-api/index.md": "[broken](missing.md)\n- [x](findings/x.md)\n",
        "docs/vendor-api/findings/x.md": "# Unlisted\n",
        "extern/submodule/.git": "gitdir: ../../.git/modules/submodule\n",
        "extern/submodule/CLAUDE.md": "[broken](x.md)\n",
        "extern/submodule/docs/archive/old.md": "# No banner\n",
    }


def tables_and_comments() -> dict[str, str]:
    return {
        "docs/records/r1.md": "# Run 1\n",
        "docs/records/r2.md": "# Run 2\n",
        "docs/guides/results.md": (
            "# Results\n\n| Run | Config | Notes |\n| --- | --- | --- |\n"
            "| [r1](../records/r1.md) | `lr=1e-3` | ok \\| fine |\n"
            '| [r2](../records/r2.md "Run 2") | <a href="../records/r2.md">html</a> | — |\n\n'
            "<!--\nTODO: [future page](../records/r3.md)\n---\n"
            "- [Draft finding](../findings/draft.md) - not written yet\n-->\n\n"
            "Text <!-- inline [hidden](nope.md) --> continues with [r1](../records/r1.md).\n\n"
            "<details>\n<summary>Raw log</summary>\n\n    [not a link](missing.md)\n\n</details>\n"
        ),
    }


def readme_and_imports() -> dict[str, str]:
    return {
        ".gitignore": "outputs/\n",
        "LICENSE": "MIT\n",
        "README.md": (
            "# Demo [![CI](https://github.com/o/r/actions/workflows/ci.yml/badge.svg)]"
            "(https://github.com/o/r/actions)\n\n"
            "[中文](README_zh.md) | [Docs][docs] | [License](LICENSE)\n\n"
            "After `make report`, open [the report](outputs/report.html).\n"
            "Measured on one GPU[^1]. Contact: team@example.com.\n\n"
            "[^1]: An A100.\n\n[docs]: docs/index.md\n"
        ),
        "README_zh.md": "# 演示\n\n[English](README.md)\n",
        "CLAUDE.md": "@AGENTS.md\n@docs/guides/style.md\n\nPing @maintainers before releases.\n",
        "AGENTS.md": "# Agents\n",
        "docs/index.md": "# Docs\n\n- [Style](guides/style.md) - formatting rules.\n",
        "docs/guides/style.md": "# Style\n",
    }


SCENARIOS = {
    "mkdocs": mkdocs_site,
    "adr": adr_with_considered_options,
    "agents-changelog": agents_md_with_changelog_rules,
    "chinese": chinese_docs,
    "grouped-findings": grouped_findings_index,
    "third-party": third_party_checkouts,
    "tables-comments": tables_and_comments,
    "readme-imports": readme_and_imports,
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_healthy_docs_have_no_diagnostics(repo: Repo, name: str) -> None:
    repo.git_init()
    for rel, text in SCENARIOS[name]().items():
        repo.write(rel, text)
    assert [diag.format_text() for diag in repo.check()] == []


def test_all_scenarios_together(repo: Repo) -> None:
    repo.git_init()
    for name in ("mkdocs", "adr", "tables-comments", "third-party"):
        for rel, text in SCENARIOS[name]().items():
            repo.write(rel, text)
    assert [diag.format_text() for diag in repo.check()] == []
