"""Source-tree bootstrap for the installable package under ``src/code_engine``.

Installed environments load the package directly from ``src``. This small
bootstrap keeps ``python -m code_engine...`` usable from a repository checkout.
"""

from pathlib import Path

_SOURCE_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "code_engine"
__path__ = [str(_SOURCE_PACKAGE)]
__version__ = "4.0.0a0"

