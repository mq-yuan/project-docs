"""Shared types: document roles, rule codes, diagnostics and configuration."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path


class ConfigError(Exception):
    """Usage, configuration or setup problem; the CLI exits with code 3."""


class DocType(StrEnum):
    """Document roles assigned during discovery."""

    ENTRY = "entry"
    INDEX = "index"
    STATUS = "status"
    CONTRACT = "contract"
    GUIDE = "guide"
    RECORD = "record"
    FINDING = "finding"
    ARCHIVE = "archive"
    ARCHIVE_INDEX = "archive_index"
    OTHER = "other"


# Types that config `[paths]` may assign by name.
NAMED_TYPES: dict[str, DocType] = {
    t.value: t for t in DocType if t not in (DocType.ENTRY, DocType.OTHER)
}


class RuleCode(StrEnum):
    """Structural rules. Codes are stable; retired codes are never reused."""

    PD000 = "PD000"  # Markdown file is unreadable
    PD001 = "PD001"  # Entry document links into the archive
    PD002 = "PD002"  # Archived file does not open with a blockquote banner
    PD003 = "PD003"  # Status page exceeds its non-empty line budget
    PD004 = "PD004"  # Status page has no valid as-of date
    PD007 = "PD007"  # Finding is not listed in the docs index with a conclusion
    PD009 = "PD009"  # Local link target does not exist


@dataclass(frozen=True)
class Diagnostic:
    """One rule violation at a file location."""

    rule: RuleCode
    path: str
    line: int
    message: str

    def format_text(self) -> str:
        """Format the diagnostic as ``path:line: CODE message``.

        Returns:
            Single-line diagnostic text.
        """
        return f"{self.path}:{self.line}: {self.rule} {self.message}"

    def to_dict(self) -> dict[str, str | int]:
        """Serialize the diagnostic for JSON output.

        Returns:
            Mapping with ``rule``, ``path``, ``line`` and ``message``.
        """
        return {**asdict(self), "rule": str(self.rule)}


@dataclass
class Config:
    """Resolved configuration for one repository root.

    Attributes:
        root: Absolute repository root.
        status_max_lines: Non-empty line budget for the status page.
        exclude: Root-relative globs of files and directories to skip.
        paths: Root-relative globs that assign a document type.
        explicit: True when loaded from ``.project-docs.toml`` or ``[tool.project-docs]``.
    """

    root: Path
    status_max_lines: int = 60
    exclude: list[str] = field(default_factory=list)
    paths: dict[DocType, list[str]] = field(default_factory=dict)
    explicit: bool = False
