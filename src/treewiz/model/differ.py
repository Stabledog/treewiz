"""Diff wrappers: git diff --no-index across repo boundaries."""

from __future__ import annotations

import subprocess
from pathlib import Path

from treewiz.model.inventory import FileEntry, FileState, Inventory


def diff_files(left: Path, right: Path, color: bool = True) -> str:
    """Run ``git diff --no-index`` between two files.  Returns diff text."""
    cmd = ["git", "diff", "--no-index"]
    if color:
        cmd.append("--color")
    cmd += [str(left), str(right)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def diff_entry(inv: Inventory, entry: FileEntry, color: bool = True) -> str:
    """Generate diff for a single *entry*.  Returns empty string for non-mismatched."""
    if entry.state != FileState.MISMATCH:
        return ""
    return diff_files(
        inv.tree_pair.left_path(entry),
        inv.tree_pair.right_path(entry),
        color=color,
    )
