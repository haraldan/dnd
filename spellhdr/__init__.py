"""Spellbook Header Inserter — pure PyMuPDF library (no web dependencies)."""

from .config import Config, load_config, save_config, config_path
from .merge import build_output, render_band, header_page_info

__all__ = [
    "Config",
    "load_config",
    "save_config",
    "config_path",
    "build_output",
    "render_band",
    "header_page_info",
]
