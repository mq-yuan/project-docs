"""Configuration from ``.project-docs.toml`` or ``[tool.project-docs]`` in ``pyproject.toml``."""

import re
import tomllib
from pathlib import Path

from project_docs.models import NAMED_TYPES, Config, ConfigError

CONFIG_FILE = ".project-docs.toml"
_KEYS = ("status_max_lines", "exclude", "paths")


def normalize_glob(pattern: str) -> str:
    """Strip surrounding whitespace, a leading ``./`` and leading or trailing slashes.

    Args:
        pattern: Glob pattern as written in the configuration.

    Returns:
        Root-relative pattern.
    """
    return pattern.strip().removeprefix("./").strip("/")


def glob_match(rel_path: str, pattern: str) -> bool:
    """Match a root-relative POSIX path against a glob.

    ``*`` and ``?`` stay within one path segment, ``**/`` matches any number of
    leading directories, and a trailing ``/**`` also matches the directory itself.

    Args:
        rel_path: Root-relative POSIX path.
        pattern: Glob pattern relative to the repository root.

    Returns:
        True if the path matches.
    """
    pat = normalize_glob(pattern)
    regex = ""
    i = 0
    while i < len(pat):
        if pat.startswith("**/", i):
            regex, i = regex + "(?:.*/)?", i + 3
        elif pat.startswith("/**", i) and i + 3 == len(pat):
            regex, i = regex + "(?:/.*)?", i + 3
        elif pat.startswith("**", i):
            regex, i = regex + ".*", i + 2
        elif pat[i] == "*":
            regex, i = regex + "[^/]*", i + 1
        elif pat[i] == "?":
            regex, i = regex + "[^/]", i + 1
        else:
            regex, i = regex + re.escape(pat[i]), i + 1
    return re.fullmatch(regex, rel_path) is not None


def _read_toml(path: Path) -> dict[str, object]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        # An unreadable or malformed config file is a setup error (exit code 3).
        raise ConfigError(f"cannot read {path.name}: {exc}") from exc


def _raw_config(root: Path) -> tuple[dict[str, object], str] | None:
    """Return the raw config table and its source label, or None if not configured."""
    standalone = root / CONFIG_FILE
    if standalone.is_file():
        return _read_toml(standalone), CONFIG_FILE
    pyproject = root / "pyproject.toml"
    # Skip parsing pyproject files that cannot contain the table at all.
    if not pyproject.is_file():
        return None
    if "project-docs" not in pyproject.read_text(encoding="utf-8", errors="replace"):
        return None
    tool = _read_toml(pyproject).get("tool")
    table = tool.get("project-docs") if isinstance(tool, dict) else None
    if table is None:
        return None
    source = "pyproject.toml [tool.project-docs]"
    if not isinstance(table, dict):
        raise ConfigError(f"{source}: expected a table.")
    return table, source


def _is_str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def load_config(root: Path) -> Config:
    """Load and validate the configuration of a repository.

    ``.project-docs.toml`` takes precedence over ``[tool.project-docs]``; without
    either, defaults are used and ``Config.explicit`` is False.

    Args:
        root: Absolute repository root.

    Returns:
        Resolved configuration.

    Raises:
        ConfigError: On unknown keys, wrong value types or unreadable files.
    """
    found = _raw_config(root)
    if found is None:
        return Config(root=root)
    raw, source = found

    unknown = sorted(set(raw) - set(_KEYS))
    if unknown:
        raise ConfigError(
            f"{source}: unknown key(s) {', '.join(unknown)}; allowed keys: {', '.join(_KEYS)}."
        )

    max_lines = raw.get("status_max_lines", 60)
    if isinstance(max_lines, bool) or not isinstance(max_lines, int) or max_lines < 1:
        raise ConfigError(
            f"{source}: 'status_max_lines' must be a positive integer, got {max_lines!r}."
        )

    exclude = raw.get("exclude", [])
    if not _is_str_list(exclude):
        raise ConfigError(f"{source}: 'exclude' must be a list of glob strings.")

    raw_paths = raw.get("paths", {})
    if not isinstance(raw_paths, dict):
        raise ConfigError(f"{source}: 'paths' must be a table of document type = glob(s).")
    paths = {}
    for key, value in raw_paths.items():
        if key not in NAMED_TYPES:
            raise ConfigError(
                f"{source}: unknown document type 'paths.{key}'; allowed: {', '.join(NAMED_TYPES)}."
            )
        globs = [value] if isinstance(value, str) else value
        if not _is_str_list(globs):
            raise ConfigError(f"{source}: 'paths.{key}' must be a glob string or list of globs.")
        paths[NAMED_TYPES[key]] = globs

    return Config(
        root=root,
        status_max_lines=max_lines,
        exclude=exclude,
        paths=paths,
        explicit=True,
    )
