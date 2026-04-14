# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Treewiz** is a TUI (Terminal User Interface) application for reconciling two parallel file trees. It's designed for scenarios where two codebases share most code but have independent variations that can't be unified (e.g., public vs. enterprise versions).

The app displays two side-by-side directory trees, classifies files as SAME, MISMATCH, LEFT_ONLY, or RIGHT_ONLY, and provides interactive tools to diff, edit, and push/pull files between the trees. External tools (diff viewer, editor, git history) are configurable and can be launched from the TUI.

**Key Dependencies:**
- **Textual** (>=0.40): MIT-licensed TUI framework built on Rich, provides widgets, CSS-like styling, keybindings, and layout
- **Python** 3.12+
- Optional dev dependency: pytest

## Development Commands

```bash
# Install in editable mode with dev extras
pip install -e ".[dev]"

# Run the app (two forms)
treewiz /path/to/other-tree           # from within one tree's root
treewiz /path/to/tree-a /path/to/tree-b

# Or via module
python -m treewiz /path/to/other-tree

# Run tests (when test directory exists)
pytest

# Check project metadata
python -c "import treewiz; print(treewiz.__version__)"
```

## Architecture

Treewiz follows a **three-layer MVC pattern**:

### Model Layer (`src/treewiz/model/`)
Business logic with **zero Textual dependencies**—independently testable and scriptable:

- **inventory.py**: Core data structures and file scanning
  - `FileState` enum: SAME, MISMATCH, LEFT_ONLY, RIGHT_ONLY
  - `FileEntry`: Single file metadata (path, state, hashes, checked flag)
  - `TreePair`: Two parallel directory roots with shared relative cursor (current_node)
  - `Inventory`: Collection of FileEntry objects scanned from both trees
  - `scan()`: Walk both trees, compute hashes, classify files against ignore rules
  
- **differ.py**: Content comparison (hash-based, ignore rules)

- **actions.py**: File operations
  - `push_files()`: Copy from left→right (never deletes right-only files)
  - `pull_files()`: Copy from right→left (never deletes left-only files)

- **config.py**: Configuration loading from `.treewizrc` files
  - Merges defaults, system config, and per-node config
  - Supports TOML format with tool customization (diff, editor, history commands)
  - Tools can be "blocking" (suspends TUI) or non-blocking (fire-and-forget)

### View Layer (`src/treewiz/tui/`)
Textual widgets that render the UI:

- **app.py**: Main `TreewizApp` widget container, keybinding dispatch, message routing
  - Manages left/right roots and current_node (relative path cursor)
  - Composes FileBrowser and DiffPanel side-by-side
  - Runs external tools via `_run_tool()` (blocks or spawns subprocess)
  - Key actions: open_diff, open_editor, open_tig, push_file, pull_file, refresh, swap_trees

- **file_browser.py**: Scrollable file list with navigation (j/k, l/h, Enter) and checkmarks
  
- **diff_panel.py**: Shows file hash/size diffs or directory info for highlighted file

- **theme.py**: Textual styling/colors

### Entry Point (`src/treewiz/__main__.py`)
Parses two directory paths (or one + cwd), validates they exist, launches `TreewizApp`.

## Key Patterns & Design Decisions

1. **TreePair + current_node**: The app maintains a shared cursor (`current_node`, a relative path like `"subdir/module"`) that both trees navigate together. This allows zooming into subdirectories while keeping both sides aligned.

2. **FileState classification**: Every file is classified against three criteria:
   - Left exists, Right exists → SAME or MISMATCH
   - Only left → LEFT_ONLY
   - Only right → RIGHT_ONLY
   
   Hashes determine SAME vs. MISMATCH for files that exist in both.

3. **Lazy scanning**: `scan(tree_pair)` reads both trees on-demand, not cached. Navigation (changing `current_node`) triggers a rescan.

4. **Configuration layering**: `.treewizrc` files can exist at three levels (default, system, per-node) and are merged. Tools are TOML-configurable with command templates and block/non-block mode.

5. **No deletion semantics**: Push and pull copy but never delete. LEFT_ONLY files stay left; RIGHT_ONLY files stay right. This prevents accidental data loss.

6. **Shell integration**: `` action_open_shell() `` spawns an interactive shell with `TREEWIZ_NODE`, `TVL`, `TVR` environment variables for scripting.

## Keybindings (from help text in app.py)

```
j/k: move up/down          l/Enter: enter dir          h: go up
d: external diff           e: edit file                t: tig (history)
s: push L→R                p: pull R→L                 m: check/uncheck
=: toggle same             r: refresh                  X: swap L⇄R
!: shell                   q: quit
```

## Testing & Quality

- No test directory yet; this is a 0.1.0 project
- Model layer is Textual-free and ready for unit tests
- TUI layer (actions, message routing) is harder to test without a TUI harness but can be validated manually or with Textual's test mode

## Configuration: `.treewizrc`

`.treewizrc` files are TOML-formatted and control tool bindings, display behavior, and file exclusions. They can exist at three levels:

1. **Global user config**: `~/.config/treewiz/config.toml` (applies to all trees)
2. **Tree root**: `.treewizrc` in each tree's root
3. **Per-directory**: `.treewizrc` at any subdirectory (overrides parent settings)

Deeper configs override shallower ones. All config files are merged together.

### Available Sections

#### `[tools]` — External Tool Commands

Define how diff, editor, and history viewers are invoked. Each tool has:
- `cmd`: Command template with placeholder variables
- `block`: Boolean (default `true`) — whether the TUI should suspend while the tool runs

**Placeholder variables:**
- `{left}`: Full path to left-side file
- `{right}`: Full path to right-side file
- `{file}`: Full path to file (for editors; used for all file states)
- `{dir}`: Full path to current directory

**Example:**
```toml
[tools]
diff = { cmd = "vimdiff {left} {right}", block = true }
editor = { cmd = "nvim {file}", block = true }
history = { cmd = "git log -p {dir}", block = false }
```

Default tools (if not overridden):
- `diff`: VS Code diff mode (non-blocking)
- `editor`: VS Code (non-blocking)
- `history`: `tig` (blocking)

#### `[display]` — UI Options

```toml
[display]
show_same = true  # show identical files in the file browser (default: false)
```

#### `[ignore]` — Exclude Files from Comparison

Use glob patterns to exclude files and directories from scanning. Patterns are matched against individual path components using shell-style wildcards (`*`, `?`, `[...]`).

**Pattern matching rules:**
- Patterns in a `.treewizrc` only apply to **immediate children** of that directory
- When checking a path like `dir/subdir/file.txt`, the scanning walks through each component and checks the patterns in the `.treewizrc` at each level
- A file is ignored if any component of its path matches a pattern in that component's parent directory's `.treewizrc`
- Config files themselves (`.treewizrc`, `.treewiz-ignore`) are always ignored

**Example scoping:**
```
left-tree/
  .treewizrc [patterns = ["build", "*.tmp"]]
    dir/
      .treewizrc [patterns = ["node_modules"]]
        build/      # Ignored (matches root .treewizrc, "build" is immediate child of left-tree/)
        dir/file.tmp  # Ignored (matches root .treewizrc, "file.tmp" is immediate child of left-tree/)
        subdir/
          build/    # NOT ignored (no pattern in left-tree/dir/.treewizrc matches "build")
          node_modules/  # Ignored (matches dir/.treewizrc, is immediate child of dir/)
```

**Example:**
```toml
[ignore]
patterns = [
    "*.o",              # ignore compiled object files
    "*.pyc",            # ignore Python cache
    "__pycache__",      # ignore Python bytecode directories
    "node_modules",     # ignore npm dependencies
    ".git",             # ignore git metadata
    "build",            # ignore build artifacts
]
```

### Full Example

```toml
[tools]
diff = { cmd = "vimdiff {left} {right}", block = true }
editor = { cmd = "nvim {file}", block = true }
history = { cmd = "git log -p {dir}", block = false }

[display]
show_same = true

[ignore]
patterns = ["*.pyc", "__pycache__", "node_modules", ".git", "*.o"]
```

### Per-Directory Config

You can place `.treewizrc` at any level in the tree. For example:

```
left-tree/
  .treewizrc                    # applies to whole tree
  src/
    .treewizrc                  # overrides parent for src/ and below
```

This is useful when different subdirectories have different ignore rules.

## Common Workflows

- **Diff-based reconciliation**: Highlight a mismatched file → `d` (launches configured diff tool)
- **Bulk push**: Navigate to a directory, mark files with `m`, then manually push each
- **Shell integration**: `!` opens a shell with both trees' paths in `TVL` and `TVR` for batch operations
- **Navigate subdirs**: Use `l`/`Enter` to enter a directory, `h` to go up (updates both trees' current_node)
- **Swap to reverse**: `X` swaps left and right if you want to push from what was right to what was left
