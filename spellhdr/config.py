"""Persistent, host-mountable configuration for the header inserter.

Settings live in a single YAML file whose path comes from the
``SPELLHDR_CONFIG_PATH`` environment variable (default ``/config/config.yaml``).
Writes are atomic so a reader on the mounted volume never sees a half-written file.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
import tempfile

import yaml

DEFAULT_CONFIG_PATH = "/config/config.yaml"


@dataclasses.dataclass
class Config:
    """All user-tunable settings. Every field is persisted and editable in the UI."""

    # 0-based page of the header file the banners are clipped from.
    header_page_index: int = 0

    # Spell-slots band vertical range (PDF points, from top of the page).
    slots_y0: float = 555.0
    slots_y1: float = 655.0

    # Modifiers band vertical range (PDF points, from top of the page).
    modifiers_y0: float = 130.0
    modifiers_y1: float = 185.0

    # Whether the slots band is drawn on the first output page.
    include_slots_on_first: bool = True

    # Content push adjustment (points): content is shifted down by
    # (sum of included band heights) - push_overlap. May be negative.
    push_overlap: float = 30.0

    # Raster DPI for the banner images.
    render_dpi: int = 300

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Build a Config from a dict, ignoring unknown keys and keeping defaults."""
        fields = {f.name for f in dataclasses.fields(cls)}
        known = {k: v for k, v in (data or {}).items() if k in fields}
        cfg = cls(**known)
        cfg.validate()
        return cfg

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def validate(self) -> None:
        """Coerce/clamp fields to sane types and ranges."""
        self.header_page_index = max(0, int(self.header_page_index))
        for name in ("slots_y0", "slots_y1", "modifiers_y0", "modifiers_y1",
                     "push_overlap"):
            setattr(self, name, float(getattr(self, name)))
        # Keep each band ordered (y0 <= y1).
        if self.slots_y1 < self.slots_y0:
            self.slots_y0, self.slots_y1 = self.slots_y1, self.slots_y0
        if self.modifiers_y1 < self.modifiers_y0:
            self.modifiers_y0, self.modifiers_y1 = self.modifiers_y1, self.modifiers_y0
        self.include_slots_on_first = bool(self.include_slots_on_first)
        self.render_dpi = max(72, min(1200, int(self.render_dpi)))


def config_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("SPELLHDR_CONFIG_PATH", DEFAULT_CONFIG_PATH))


def load_config() -> Config:
    """Load config from disk; if missing/unreadable, return defaults (and persist)."""
    path = config_path()
    try:
        text = path.read_text()
    except (FileNotFoundError, OSError):
        cfg = Config()
        try:
            save_config(cfg)
        except OSError:
            pass  # e.g. /config not mounted yet — fall back to in-memory defaults
        return cfg
    try:
        data = yaml.safe_load(text) or {}
        return Config.from_dict(data)
    except (yaml.YAMLError, TypeError, ValueError):
        return Config()


def save_config(cfg: Config) -> None:
    """Atomically write config to disk (temp file + os.replace)."""
    cfg.validate()
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(cfg.to_dict(), sort_keys=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
