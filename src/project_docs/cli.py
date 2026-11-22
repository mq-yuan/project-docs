"""Command-line interface: ``project-docs`` (alias ``pdocs``).

Exit codes: 0 pass, 1 violations (check), 2 hook feedback, 3 usage, config or IO error.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import NoReturn

from project_docs import __version__
from project_docs.checker import check_project
from project_docs.config import load_config
from project_docs.discovery import discover
from project_docs.models import ConfigError
from project_docs.scaffold import init_docs


class _ArgumentParser(argparse.ArgumentParser):
    """Argument parser that exits with code 3 on usage errors.

    Exit code 2 is reserved for hook feedback, which Claude Code forwards to the agent.
    """

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise SystemExit(3)


def _directory(raw: str) -> Path:
    path = Path(raw)
    if not path.is_dir():
        raise ConfigError(f"not a directory: {raw}")
    return path.resolve()


def _cmd_check(args: argparse.Namespace) -> int:
    root = _directory(args.path)
    docs, diags = check_project(root)
    if args.format == "json":
        payload = {
            "root": str(root),
            "checked_files": len(docs),
            "passed": not diags,
            "diagnostics": [diag.to_dict() for diag in diags],
        }
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    else:
        for diag in diags:
            sys.stdout.write(diag.format_text() + "\n")
        summary = f"{len(diags)} problem(s)" if diags else "no problems"
        sys.stdout.write(f"Checked {len(docs)} file(s): {summary}.\n")
    return 1 if diags else 0


def _cmd_map(args: argparse.Namespace) -> int:
    for doc in discover(load_config(_directory(args.path))):
        sys.stdout.write(f"{doc.doc_type:<14} {doc.rel}\n")
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    root = _directory(args.path)
    written = init_docs(root, force=args.force)
    for path in written:
        sys.stdout.write(f"Wrote {path.relative_to(root).as_posix()}\n")
    if not written:
        sys.stdout.write("Starter files already exist; use --force to overwrite them.\n")
    return 0


def _hook_root(path: Path) -> Path | None:
    """Return ``$CLAUDE_PROJECT_DIR``, else the nearest ancestor that contains ``.git``."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if project_dir:
        return Path(project_dir).resolve()
    return next((p for p in path.parents if os.path.lexists(p / ".git")), None)


def _cmd_hook(_args: argparse.Namespace) -> int:
    if sys.stdin.isatty():
        raise ConfigError("hook reads a Claude Code PostToolUse JSON event from stdin.")
    try:
        event = json.loads(sys.stdin.read().strip() or "{}")
    except json.JSONDecodeError as exc:
        # Malformed hook input is a usage error, reported with exit code 3.
        raise ConfigError(f"hook input is not valid JSON: {exc}") from exc
    if not isinstance(event, dict):
        return 0
    tool_input = event.get("tool_input")
    raw_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(raw_path, str) or not raw_path.lower().endswith(".md"):
        return 0
    path = Path(raw_path)
    if not path.is_absolute():
        return 0
    path = path.parent.resolve() / path.name

    root = _hook_root(path)
    if root is None or not path.is_relative_to(root) or not load_config(root).explicit:
        return 0
    rel = path.relative_to(root).as_posix()
    own = check_project(root, only=rel)[1]
    if not own:
        return 0
    sys.stderr.write(f"project-docs found {len(own)} problem(s) in {rel}:\n")
    for diag in own:
        sys.stderr.write(f"  {diag.format_text()}\n")
    sys.stderr.write("Fix the document in place, then run `project-docs check`.\n")
    return 2


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        Parser with ``check``, ``map``, ``init`` and ``hook`` subcommands.
    """
    parser = _ArgumentParser(description="Structural checks for project documentation.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Check the documentation of a repository.")
    check.add_argument("path", nargs="?", default=".", help="Repository root (default: .).")
    check.add_argument("--format", choices=("text", "json"), default="text")
    check.set_defaults(func=_cmd_check)

    map_cmd = sub.add_parser("map", help="List discovered documents and their types.")
    map_cmd.add_argument("path", nargs="?", default=".", help="Repository root (default: .).")
    map_cmd.set_defaults(func=_cmd_map)

    init = sub.add_parser("init", help="Write .project-docs.toml, docs/index.md, docs/status.md.")
    init.add_argument("path", nargs="?", default=".", help="Repository root (default: .).")
    init.add_argument("--force", action="store_true", help="Overwrite existing starter files.")
    init.set_defaults(func=_cmd_init)

    hook = sub.add_parser("hook", help="Claude Code PostToolUse hook for Edit|Write.")
    hook.set_defaults(func=_cmd_hook)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Arguments without the program name; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (ConfigError, OSError) as exc:
        # Configuration and filesystem setup problems exit with code 3 and a short message.
        sys.stderr.write(f"project-docs: error: {exc}\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
