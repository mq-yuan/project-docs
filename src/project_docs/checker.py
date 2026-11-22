"""Structural rules. Each rule is language-independent and avoids guessing at meaning."""

import os
import posixpath
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote

from project_docs.config import load_config
from project_docs.discovery import Doc, classify, discover
from project_docs.models import Config, Diagnostic, DocType, RuleCode

_ENTRY_TYPES = frozenset({DocType.ENTRY, DocType.INDEX, DocType.STATUS})
_ARCHIVE_LINK_KINDS = frozenset({"inline", "ref_def", "html", "import"})
_CHECKED_LINK_KINDS = frozenset({"inline", "ref_def", "html"})
_INDEX_LINK_KINDS = frozenset({"inline", "ref_use", "html"})
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])")
_DATE_RE = re.compile(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s+")
_WORD_RE = re.compile(r"\w")


def link_path(source_rel: str, target: str) -> str | None:
    """Resolve a link destination to a normalized root-relative POSIX path.

    Backslash escapes are removed, query strings and fragments are dropped, and the path
    is URL-decoded before it is checked, so an encoded leading ``/`` cannot leave the root.

    Args:
        source_rel: Root-relative path of the document that contains the link.
        target: Raw link destination.

    Returns:
        The root-relative path, or None for external, absolute, fragment-only or
        out-of-root targets.
    """
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = unquote(_ESCAPE_RE.sub(r"\1", target).split("#", 1)[0].split("?", 1)[0])
    if not target or _SCHEME_RE.match(target) or target.startswith(("/", "~", "\\")):
        return None
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(source_rel), target))
    if joined == ".." or joined.startswith("../") or "\0" in joined:
        return None
    return joined


def _local_links(doc: Doc, kinds: frozenset[str]) -> list[tuple[int, str, str]]:
    """Return ``(line, raw_target, rel_path)`` for local links outside code blocks."""
    links = [link for link in doc.parsed.links if not link.in_code and link.kind in kinds]
    resolved = [(link.line, link.target, link_path(doc.rel, link.target)) for link in links]
    return [(line, target, rel) for line, target, rel in resolved if rel is not None]


def _check_archive_links(doc: Doc, config: Config) -> list[Diagnostic]:
    """PD001: entry documents link at most to the archive index, never to archived files."""
    return [
        Diagnostic(
            RuleCode.PD001,
            doc.rel,
            line,
            f"Entry document links to an archived file ('{target}'); remove the link. "
            "Archived files are reached only through the archive index.",
        )
        for line, target, rel in _local_links(doc, _ARCHIVE_LINK_KINDS)
        if classify(rel, config) is DocType.ARCHIVE and not os.path.isdir(config.root / rel)
    ]


def _check_archive_banner(doc: Doc) -> list[Diagnostic]:
    """PD002: the first non-empty body line of an archived file starts with ``>``."""
    first = next(
        ((no, text) for no, text, _ in doc.parsed.body if text is None or text.strip()),
        (doc.parsed.body_start + 1, None),
    )
    if first[1] is not None and first[1].lstrip().startswith(">"):
        return []
    message = (
        "Archived file must open with a '>' banner line: historical, not current guidance, "
        "read only when asked."
    )
    return [Diagnostic(RuleCode.PD002, doc.rel, first[0], message)]


def _is_recent_date(text: str, latest: date) -> bool:
    try:
        return date.fromisoformat(text) <= latest
    except ValueError:
        # Calendar-invalid strings such as 2026-02-30 are not dates.
        return False


def _check_status(doc: Doc, max_lines: int) -> list[Diagnostic]:
    """PD003 (line budget) and PD004 (as-of date) for the status page."""
    diags = []
    filled = [i for i in range(doc.parsed.body_start, len(doc.lines)) if doc.lines[i].strip()]
    if len(filled) > max_lines:
        message = (
            f"Status has {len(filled)} non-empty lines (limit {max_lines}); move results to "
            "records or findings and drop finished items."
        )
        diags.append(Diagnostic(RuleCode.PD003, doc.rel, filled[max_lines] + 1, message))
    latest = date.today() + timedelta(days=1)
    if not any(
        _is_recent_date(m.group(1), latest) for m in _DATE_RE.finditer("\n".join(doc.lines))
    ):
        message = "Status has no as-of date; add one as YYYY-MM-DD (not in the future)."
        diags.append(Diagnostic(RuleCode.PD004, doc.rel, doc.parsed.body_start + 1, message))
    return diags


class _IgnoreRules:
    """Answers whether a missing link target is ignored by the repository's git rules."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.in_work_tree = any(os.path.lexists(p / ".git") for p in (root, *root.parents))
        self.cache: dict[str, bool] = {}

    def skips(self, rel: str) -> bool:
        """Return True if ``rel`` (as a file or a directory) is ignored or git cannot tell.

        Args:
            rel: Root-relative POSIX path of a missing link target.

        Returns:
            Whether the broken link should not be reported.
        """
        if rel not in self.cache:
            self.cache[rel] = self._query(rel)
        return self.cache[rel]

    def _query(self, rel: str) -> bool:
        command = ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "--", rel, rel + "/"]
        try:
            result = subprocess.run(command, cwd=self.root, capture_output=True, check=False)
        except FileNotFoundError:
            # Without a git executable the ignore rules are unknown; report the link as usual.
            return False
        # 0: a form is ignored. 128 inside a work tree (e.g. a path in an uninitialized
        # submodule) means git cannot decide, so the link is not reported.
        return result.returncode == 0 or (result.returncode == 128 and self.in_work_tree)


def _check_local_links(doc: Doc, root: Path, ignore: _IgnoreRules) -> list[Diagnostic]:
    """PD009: relative local link targets must exist unless git ignores them."""
    return [
        Diagnostic(RuleCode.PD009, doc.rel, line, f"Local link target '{target}' does not exist.")
        for line, target, rel in _local_links(doc, _CHECKED_LINK_KINDS)
        if not os.path.exists(root / rel) and not ignore.skips(rel)
    ]


def _check_findings(docs: list[Doc]) -> list[Diagnostic]:
    """PD007: every finding is linked from a docs index line that also carries a conclusion.

    The conclusion is any word character on the link's line besides the link and a list
    marker, or on the indented continuation line right after it.
    """
    findings = [doc.rel for doc in docs if doc.doc_type is DocType.FINDING]
    if not findings:
        return []
    indexes = [doc for doc in docs if doc.doc_type is DocType.INDEX and doc.read_error is None]
    listed: set[str] = set()
    bare: dict[str, str] = {}
    for index in indexes:
        for link in index.parsed.links:
            rel = link_path(index.rel, link.target) if link.kind in _INDEX_LINK_KINDS else None
            if rel not in findings:
                continue
            raw = index.lines[link.line - 1]
            marker = _LIST_ITEM_RE.match(raw)
            begin = marker.end() if marker is not None and marker.end() <= link.start else 0
            following = index.lines[link.line] if link.line < len(index.lines) else ""
            continued = following[:1] in (" ", "\t") and _WORD_RE.search(following)
            if _WORD_RE.search(raw[begin : link.start] + raw[link.end :]) or continued:
                listed.add(rel)
            else:
                bare.setdefault(rel, f"{index.rel}:{link.line}")
    diags = []
    for rel in findings:
        if rel in listed:
            continue
        if rel in bare:
            message = f"Finding is listed at {bare[rel]} without a conclusion"
        elif indexes:
            message = "Finding is not listed in the docs index"
        else:
            message = "Finding is not listed because there is no docs index (docs/index.md)"
        message += "; list it as '[topic](path) - one-sentence conclusion'."
        diags.append(Diagnostic(RuleCode.PD007, rel, 1, message))
    return diags


def check_project(root: Path, only: str | None = None) -> tuple[list[Doc], list[Diagnostic]]:
    """Run every rule on the repository at ``root``.

    Args:
        root: Repository root directory.
        only: Root-relative path of a single document. Per-file rules then run on that
            document only; cross-file rules still read every document, and only
            diagnostics for this path are returned.

    Returns:
        Discovered documents and diagnostics sorted by path, line and rule.

    Raises:
        ConfigError: If the repository configuration is invalid.
    """
    config = load_config(root.resolve())
    docs = discover(config)
    ignore = _IgnoreRules(config.root)
    diags: list[Diagnostic] = []
    for doc in docs:
        if only is not None and doc.rel != only:
            continue
        if doc.read_error is not None:
            message = f"Cannot read Markdown file: {doc.read_error}."
            diags.append(Diagnostic(RuleCode.PD000, doc.rel, 1, message))
            continue
        if doc.doc_type in _ENTRY_TYPES:
            diags.extend(_check_archive_links(doc, config))
        if doc.doc_type is DocType.ARCHIVE:
            diags.extend(_check_archive_banner(doc))
        else:
            diags.extend(_check_local_links(doc, config.root, ignore))
        if doc.doc_type is DocType.STATUS:
            diags.extend(_check_status(doc, config.status_max_lines))
    diags.extend(_check_findings(docs))
    if only is not None:
        diags = [diag for diag in diags if diag.path == only]
    diags.sort(key=lambda d: (d.path, d.line, d.rule))
    return docs, diags
