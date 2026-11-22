"""Starter files written by ``project-docs init``."""

from datetime import date
from pathlib import Path

from project_docs.config import CONFIG_FILE, load_config

CONFIG_TEMPLATE = """\
# project-docs configuration. Keep this file at the repository root.
# Its presence opts the repository into `project-docs hook`.

# status_max_lines = 60
# exclude = ["experiments/scratch/**"]

# [paths]
# finding = ["notes/findings/**"]
"""

INDEX_TEMPLATE = """\
# Documentation

- [Status](status.md) - active work, next steps and blockers.

## Contracts

## Guides

## Findings

<!-- One line per finding: - [topic](findings/topic.md) - one-sentence conclusion -->

## Records
"""

STATUS_TEMPLATE = """\
# Status

As of {today} (source: project-docs init).

## Active work

- None yet.
"""


def init_docs(root: Path, *, force: bool = False) -> list[Path]:
    """Write the opt-in config, ``docs/index.md`` and ``docs/status.md``.

    Existing files are kept unless ``force`` is set. The config file is not written
    when ``[tool.project-docs]`` already configures the repository, and
    ``docs/index.md`` is not written when ``docs/README.md`` serves as the index.

    Args:
        root: Repository root.
        force: Overwrite existing starter files.

    Returns:
        Paths that were written.

    Raises:
        ConfigError: If an existing configuration is invalid.
    """
    config = load_config(root)
    written: list[Path] = []

    def write(path: Path, content: str) -> None:
        if path.exists() and not force:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)

    config_path = root / CONFIG_FILE
    if not config.explicit or config_path.is_file():
        write(config_path, CONFIG_TEMPLATE)
    docs = root / "docs"
    if not (docs / "README.md").exists():
        write(docs / "index.md", INDEX_TEMPLATE)
    write(docs / "status.md", STATUS_TEMPLATE.format(today=date.today().isoformat()))
    return written
