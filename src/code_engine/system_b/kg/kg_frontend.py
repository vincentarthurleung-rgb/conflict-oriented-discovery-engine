"""Frontend asset helpers."""

from pathlib import Path

STATIC_ROOT = Path(__file__).parent / "static"


def frontend_assets():
    return [STATIC_ROOT / name for name in ("index.html", "app.js", "style.css")]
