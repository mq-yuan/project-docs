"""Test helpers: a throwaway repository and dates relative to today."""

import subprocess
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from project_docs import check_project
from project_docs.models import Diagnostic


def iso(days: int = 0) -> str:
    """Return today's date shifted by ``days`` as ``YYYY-MM-DD``."""
    return (date.today() + timedelta(days=days)).isoformat()


@dataclass
class Repo:
    """A repository rooted in a pytest ``tmp_path``."""

    root: Path

    def write(self, rel: str, text: str = "") -> Path:
        """Write a UTF-8 file, creating parent directories."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def git_init(self, rel: str = ".") -> None:
        """Initialize a git repository at ``rel``."""
        subprocess.run(["git", "init", "-q", str(self.root / rel)], check=True)

    def check(self) -> list[Diagnostic]:
        """Run all rules and return the diagnostics."""
        return check_project(self.root)[1]

    def found(self) -> set[tuple[str, str]]:
        """Return ``(rule, path)`` pairs of all diagnostics."""
        return {(str(d.rule), d.path) for d in self.check()}
