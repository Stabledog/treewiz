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


def _toml_value(v) -> str:
    """Serialize a Python value to a TOML value string."""
    if isinstance(v, bool):
        return "true" if v else "false"
    elif isinstance(v, str):
        return f'"{v}"'
    elif isinstance(v, list):
        items = ", ".join(
            f'"{item}"' if isinstance(item, str) else str(item) for item in v
        )
        return f"[{items}]"
    return str(v)


def _quote_key(key: str) -> str:
    """Quote a TOML key if it contains special characters."""
    # For simplicity, always quote keys with special chars like /
    if "/" in key or " " in key or any(c in key for c in '.-'):
        return f'"{key}"'
    return key


def _write_rc(path: Path, data: dict) -> None:
    """Serialize *data* back to a .treewizrc TOML file."""
    lines = []
    for section, values in data.items():
        if lines:
            lines.append("")
        lines.append(f"[{section}]")
        for key, val in values.items():
            if isinstance(val, dict):
                # Inline table (e.g., tools section)
                inner = ", ".join(f"{k} = {_toml_value(v)}" for k, v in val.items())
                lines.append(f"{key} = {{{inner}}}")
            else:
                # Handle regular values and lists (including blessed entries)
                lines.append(f"{_quote_key(key)} = {_toml_value(val)}")
    content = "\n".join(lines)
    path.write_text(content + "\n" if content else "")


def add_ignore_pattern(rc_path: Path, pattern: str) -> None:
    """Add *pattern* to [ignore] patterns in *rc_path*, creating the file if needed."""
    data = load_rc(rc_path)
    ignore = data.setdefault("ignore", {})
    patterns = ignore.setdefault("patterns", [])
    if pattern not in patterns:
        patterns.append(pattern)
        _write_rc(rc_path, data)


def add_blessed_entry(rc_path: Path, filename: str, left_hash: str, right_hash: str) -> None:
    """Add or update a blessed entry in [blessed] section of *rc_path*.

    Creates the file if needed.
    """
    data = load_rc(rc_path)
    blessed = data.setdefault("blessed", {})
    blessed[filename] = [left_hash, right_hash]
    _write_rc(rc_path, data)
