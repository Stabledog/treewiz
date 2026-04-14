"""Configuration: .treewizrc and global config loading."""

from __future__ import annotations

import tomllib
from pathlib import Path

DEFAULT_CONFIG = {
    "tools": {
        "diff": {"cmd": "code --diff {left} {right}", "block": False},
        "editor": {"cmd": "code {file}", "block": False},
        "history": {"cmd": "tig {dir}", "block": True},
    },
    "display": {
        "show_same": False,
    },
}


def _merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (override wins)."""
    merged = dict(base)
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def load_rc(path: Path) -> dict:
    """Parse a single .treewizrc file. Raises error on parse failure."""
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse {path}: {e}") from e


def load_config(left_root: Path, right_root: Path, current_node: str) -> dict:
    """Build merged config: global defaults -> ~/.config -> per-dir cascade.

    Per-directory .treewizrc files are checked at each level from tree root
    down to current_node, in both left and right trees.  Deeper files override
    shallower.
    """
    cfg = dict(DEFAULT_CONFIG)

    # Global user config
    global_rc = Path.home() / ".config" / "treewiz" / "config.toml"
    cfg = _merge(cfg, load_rc(global_rc))

    # Per-directory cascade from root down to current_node
    parts = current_node.split("/") if current_node else []
    for depth in range(len(parts) + 1):
        subdir = "/".join(parts[:depth]) if depth else ""
        for root in (left_root, right_root):
            base = root / subdir if subdir else root
            rc = base / ".treewizrc"
            cfg = _merge(cfg, load_rc(rc))

    return cfg
