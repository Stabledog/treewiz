"""File inventory: discover and classify files across two git trees."""

from __future__ import annotations

import fnmatch
import hashlib
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class FileState(Enum):
    SAME = "same"
    MISMATCH = "mismatch"
    LEFT_ONLY = "left-only"
    RIGHT_ONLY = "right-only"


@dataclass
class FileEntry:
    """A single file known to one or both trees."""

    path: str  # relative to current_node (e.g. "core.py" or "sub/core.py")
    state: FileState
    left_hash: str | None = None
    right_hash: str | None = None
    checked: bool = False  # ephemeral in-session checkmark


@dataclass
class TreePair:
    """Two parallel trees with a shared relative cursor."""

    left_root: Path
    right_root: Path
    current_node: str = ""  # relative path from git root, e.g. "gitsmart/treewiz"

    def left_path(self, entry: FileEntry) -> Path:
        if self.current_node:
            return self.left_root / self.current_node / entry.path
        return self.left_root / entry.path

    def right_path(self, entry: FileEntry) -> Path:
        if self.current_node:
            return self.right_root / self.current_node / entry.path
        return self.right_root / entry.path

    def left_node_dir(self) -> Path:
        if self.current_node:
            return self.left_root / self.current_node
        return self.left_root

    def right_node_dir(self) -> Path:
        if self.current_node:
            return self.right_root / self.current_node
        return self.right_root


@dataclass
class Inventory:
    """Result of scanning two trees at a given node."""

    tree_pair: TreePair
    files: dict[str, FileEntry] = field(default_factory=dict)
    dirs: list[str] = field(default_factory=list)  # subdirectories at this level

    @property
    def same(self) -> list[FileEntry]:
        return [f for f in self.files.values() if f.state == FileState.SAME]

    @property
    def mismatched(self) -> list[FileEntry]:
        return [f for f in self.files.values() if f.state == FileState.MISMATCH]

    @property
    def left_only(self) -> list[FileEntry]:
        return [f for f in self.files.values() if f.state == FileState.LEFT_ONLY]

    @property
    def right_only(self) -> list[FileEntry]:
        return [f for f in self.files.values() if f.state == FileState.RIGHT_ONLY]


def git_root(path: Path) -> Path:
    """Return the git toplevel for the repo containing *path*."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(path),
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


# ---------------------------------------------------------------------------
# File listing — tracked + untracked
# ---------------------------------------------------------------------------

def _ls_tracked(repo_root: Path, scope: str) -> dict[str, str]:
    """Return {relative_path: blob_hash} for tracked files under *scope*."""
    scope_dir = scope if scope else "."
    result = subprocess.run(
        ["git", "ls-files", "-s", scope_dir],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    files: dict[str, str] = {}
    prefix = (scope + "/") if scope else ""
    for line in result.stdout.splitlines():
        meta, path = line.split("\t", 1)
        blob_hash = meta.split()[1]
        if prefix and path.startswith(prefix):
            path = path[len(prefix):]
        elif prefix:
            continue
        files[path] = blob_hash
    return files


def _ls_untracked(repo_root: Path, scope: str) -> dict[str, str]:
    """Return {relative_path: content_hash} for untracked (non-ignored) files."""
    scope_dir = scope if scope else "."
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", scope_dir],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    files: dict[str, str] = {}
    prefix = (scope + "/") if scope else ""
    for line in result.stdout.splitlines():
        path = line.strip()
        if not path:
            continue
        if prefix and path.startswith(prefix):
            path = path[len(prefix):]
        elif prefix:
            continue
        # Hash file content so we can compare across trees
        full = repo_root / (f"{scope}/{path}" if scope else path)
        try:
            content = full.read_bytes()
            files[path] = hashlib.sha256(content).hexdigest()
        except OSError:
            pass
    return files


def _ls_files(repo_root: Path, scope: str) -> dict[str, str]:
    """Return {relative_path: hash} for all relevant files (tracked + untracked)."""
    tracked = _ls_tracked(repo_root, scope)
    untracked = _ls_untracked(repo_root, scope)
    # Tracked wins if somehow both have the same path
    return {**untracked, **tracked}


# ---------------------------------------------------------------------------
# Ignore patterns — .treewizrc [ignore] section
# ---------------------------------------------------------------------------

def _load_ignore_patterns(repo_root: Path, directory: str) -> set[str]:
    """Load ignore patterns from .treewizrc or .treewiz-ignore in *directory*."""
    base = repo_root / directory if directory else repo_root

    # Try .treewizrc first (TOML [ignore] patterns = [...])
    rc = base / ".treewizrc"
    if rc.exists():
        try:
            import tomllib
            with open(rc, "rb") as f:
                data = tomllib.load(f)
            patterns = data.get("ignore", {}).get("patterns", [])
            if patterns:
                return set(patterns)
        except Exception:
            pass

    # Fall back to legacy .treewiz-ignore
    ignore_file = base / ".treewiz-ignore"
    if not ignore_file.exists():
        return set()
    patterns: set[str] = set()
    try:
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.add(line)
    except OSError:
        pass
    return patterns


def _should_ignore(path: str, left_root: Path, right_root: Path, scope: str) -> bool:
    """Check if *path* should be ignored based on ignore patterns.

    Walks each component from root to leaf; if any component matches a pattern
    in its parent directory, the whole path is ignored.
    """
    # Always ignore config files themselves
    basename = path.rsplit("/", 1)[-1]
    if basename in (".treewiz-ignore", ".treewizrc"):
        return True

    components = path.split("/")
    for i, component in enumerate(components):
        if i == 0:
            parent_in_scope = ""
        else:
            parent_in_scope = "/".join(components[:i])

        if scope and parent_in_scope:
            parent_dir = f"{scope}/{parent_in_scope}"
        elif scope:
            parent_dir = scope
        else:
            parent_dir = parent_in_scope

        left_patterns = _load_ignore_patterns(left_root, parent_dir)
        right_patterns = _load_ignore_patterns(right_root, parent_dir)
        for pattern in left_patterns | right_patterns:
            if fnmatch.fnmatch(component, pattern):
                return True

    return False


# ---------------------------------------------------------------------------
# Directory aggregation — for the file browser
# ---------------------------------------------------------------------------

def _extract_top_level(paths: list[str]) -> tuple[list[str], list[str]]:
    """Split paths into top-level dirs and top-level files at the current node.

    Returns (sorted_dirs, sorted_files).
    """
    dirs: set[str] = set()
    files: list[str] = []
    for p in paths:
        if "/" in p:
            dirs.add(p.split("/", 1)[0])
        else:
            files.append(p)
    return sorted(dirs), sorted(files)


def _dir_state(dir_name: str, entries: dict[str, FileEntry]) -> FileState:
    """Compute aggregate state for a directory.

    Priority: MISMATCH > LEFT_ONLY/RIGHT_ONLY > SAME.
    """
    dominated = FileState.SAME
    for path, entry in entries.items():
        if not path.startswith(dir_name + "/"):
            continue
        if entry.state == FileState.MISMATCH:
            return FileState.MISMATCH
        if entry.state in (FileState.LEFT_ONLY, FileState.RIGHT_ONLY):
            dominated = entry.state
    return dominated


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def scan(tree_pair: TreePair) -> Inventory:
    """Scan two trees at the current node and build an inventory."""
    left_root = tree_pair.left_root
    right_root = tree_pair.right_root
    scope = tree_pair.current_node

    left_files = _ls_files(left_root, scope)
    right_files = _ls_files(right_root, scope)

    all_paths = sorted(set(left_files) | set(right_files))

    # Filter ignored paths
    filtered = [
        p for p in all_paths
        if not _should_ignore(p, left_root, right_root, scope)
    ]

    entries: dict[str, FileEntry] = {}
    for path in filtered:
        lh = left_files.get(path)
        rh = right_files.get(path)
        if lh and rh:
            state = FileState.SAME if lh == rh else FileState.MISMATCH
        elif lh:
            state = FileState.LEFT_ONLY
        else:
            state = FileState.RIGHT_ONLY
        entries[path] = FileEntry(path=path, state=state, left_hash=lh, right_hash=rh)

    dirs, _ = _extract_top_level(filtered)

    return Inventory(tree_pair=tree_pair, files=entries, dirs=dirs)
