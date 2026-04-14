"""Push/pull: copy files between left and right trees."""

from __future__ import annotations

import shutil

from treewiz.model.inventory import FileEntry, FileState, Inventory


def push_files(inv: Inventory, entries: list[FileEntry]) -> list[str]:
    """Copy files L -> R.  Only mismatched and left-only.  Never removes right-only."""
    copied = []
    tp = inv.tree_pair
    for entry in entries:
        if entry.state not in (FileState.MISMATCH, FileState.LEFT_ONLY):
            continue
        src = tp.left_path(entry)
        dst = tp.right_path(entry)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        copied.append(entry.path)
    return copied


def pull_files(inv: Inventory, entries: list[FileEntry]) -> list[str]:
    """Copy files R -> L.  Only mismatched and right-only.  Never removes left-only."""
    copied = []
    tp = inv.tree_pair
    for entry in entries:
        if entry.state not in (FileState.MISMATCH, FileState.RIGHT_ONLY):
            continue
        src = tp.right_path(entry)
        dst = tp.left_path(entry)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        copied.append(entry.path)
    return copied
