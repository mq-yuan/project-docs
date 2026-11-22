"""project-docs: documentation rules for coding agents plus a structural linter."""

from importlib.metadata import PackageNotFoundError, version

from project_docs.checker import check_project
from project_docs.models import ConfigError, Diagnostic, DocType, RuleCode

try:
    __version__ = version("project-docs")
except PackageNotFoundError:
    # Running from an uninstalled source tree.
    __version__ = "0.1.0"

__all__ = ["ConfigError", "Diagnostic", "DocType", "RuleCode", "__version__", "check_project"]
