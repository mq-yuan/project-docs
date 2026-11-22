"""Discover governed Markdown files and assign their document roles."""

import os
import posixpath
from dataclasses import dataclass
from pathlib import Path

from project_docs.config import glob_match, normalize_glob
from project_docs.markdown import Parsed, parse
from project_docs.models import Config, DocType

_ROOT_ENTRY_NAMES = frozenset({"AGENTS.md", "CLAUDE.md", "CLAUDE.local.md"})
_DOT_CLAUDE_ENTRY = ".claude/CLAUDE.md"
_DOCS_FOLDERS = {
    "contracts": DocType.CONTRACT,
    "guides": DocType.GUIDE,
    "records": DocType.RECORD,
    "findings": DocType.FINDING,
    "archive": DocType.ARCHIVE,
}
_DIRECTORY_INDEX_NAMES = ("index.md", "readme.md")


@dataclass
class Doc:
    """A discovered Markdown document.

    Attributes:
        rel: Root-relative POSIX path.
        doc_type: Assigned role.
        lines: Lines without terminators; empty if unreadable.
        parsed: Scan result.
        read_error: Reason the file could not be read, if any.
    """

    rel: str
    doc_type: DocType
    lines: list[str]
    parsed: Parsed
    read_error: str | None = None


def _is_entry(rel: str) -> bool:
    if rel == _DOT_CLAUDE_ENTRY:
        return True
    is_readme = rel.upper().startswith("README") and rel.lower().endswith(".md")
    return "/" not in rel and (rel in _ROOT_ENTRY_NAMES or is_readme)


def _convention_type(rel: str) -> DocType:
    if _is_entry(rel):
        return DocType.ENTRY
    lower = rel.lower()
    if lower in ("docs/index.md", "docs/readme.md"):
        return DocType.INDEX
    if lower == "docs/status.md":
        return DocType.STATUS
    parts = rel.split("/")
    if len(parts) > 2 and parts[0] == "docs" and parts[1] in _DOCS_FOLDERS:
        return _DOCS_FOLDERS[parts[1]]
    return DocType.OTHER


def classify(rel: str, config: Config) -> DocType:
    """Assign a role by config ``paths``, then by path convention.

    A directory index (``index.md`` / ``README.md``) inside the archive is the archive
    index; inside the findings folder it is a navigation page, not a finding.

    Args:
        rel: Root-relative POSIX path.
        config: Repository configuration.

    Returns:
        The document role.
    """
    found = next(
        (t for t, globs in config.paths.items() if any(glob_match(rel, g) for g in globs)),
        None,
    )
    if found is None:
        found = _convention_type(rel)
    if posixpath.basename(rel).lower() in _DIRECTORY_INDEX_NAMES:
        if found is DocType.ARCHIVE:
            return DocType.ARCHIVE_INDEX
        if found is DocType.FINDING:
            return DocType.OTHER
    return found


def _excluded(rel: str, config: Config) -> bool:
    return any(glob_match(rel, pattern) for pattern in config.exclude)


def load_doc(config: Config, rel: str) -> Doc:
    """Read, scan and classify one Markdown file.

    Args:
        config: Repository configuration.
        rel: Root-relative POSIX path.

    Returns:
        The document; ``read_error`` is set when the file cannot be read as UTF-8.
    """
    doc_type = classify(rel, config)
    try:
        text = (config.root / rel).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        # Non-UTF-8 content becomes a PD000 diagnostic instead of aborting the run.
        error = f"not valid UTF-8 (byte {exc.start})"
    except OSError as exc:
        # Permission errors and dangling symlinks become PD000 diagnostics as well.
        error = exc.strerror or type(exc).__name__
    else:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        return Doc(rel, doc_type, lines, parse(lines))
    return Doc(rel, doc_type, [], Parsed(0, [], []), error)


def _walkable(root: Path, rel_dir: str) -> bool:
    """Return True if every directory on ``rel_dir`` is real and not a nested repository."""
    path = root
    for part in filter(None, rel_dir.split("/")):
        path = path / part
        if path.is_symlink() or not path.is_dir() or os.path.lexists(path / ".git"):
            return False
    return True


def _walk(config: Config, top: str) -> list[str]:
    """List files under ``top``, pruning hidden, nested-repository and excluded directories."""
    found = []
    for dirpath, dirnames, filenames in os.walk(config.root / top):
        rel_dir = Path(dirpath).relative_to(config.root).as_posix()
        prefix = "" if rel_dir == "." else f"{rel_dir}/"
        dirnames[:] = [
            name
            for name in dirnames
            if not name.startswith(".")
            and name != "node_modules"
            and not os.path.lexists(Path(dirpath) / name / ".git")
            and not _excluded(prefix + name, config)
        ]
        found.extend(prefix + name for name in filenames)
    return found


def discover(config: Config) -> list[Doc]:
    """Find root entry documents, ``.claude/CLAUDE.md``, ``docs/`` and ``paths`` matches.

    ``docs/`` and ``paths`` locations are skipped when they pass through a symlink or a
    nested repository (a directory with its own ``.git``); ``exclude`` globs apply
    everywhere.

    Args:
        config: Repository configuration.

    Returns:
        Documents sorted by path.
    """
    root = config.root
    globs = [normalize_glob(g) for patterns in config.paths.values() for g in patterns]
    rels = {name for name in os.listdir(root) if _is_entry(name)}
    if os.path.lexists(root / _DOT_CLAUDE_ENTRY):
        rels.add(_DOT_CLAUDE_ENTRY)
    tops = {"docs"}
    for pattern in globs:
        parts = pattern.split("/")
        wild = next((i for i, part in enumerate(parts) if "*" in part or "?" in part), None)
        if wild is not None:
            tops.add("/".join(parts[:wild]))
        elif os.path.lexists(root / pattern) and _walkable(root, posixpath.dirname(pattern)):
            rels.add(pattern)
    for top in sorted(tops):
        if _walkable(root, top):
            walked = _walk(config, top)
            rels.update(
                r for r in walked if r.startswith("docs/") or any(glob_match(r, g) for g in globs)
            )
    rels = {rel for rel in rels if rel.lower().endswith(".md") and not _excluded(rel, config)}
    return [load_doc(config, rel) for rel in sorted(rels)]
