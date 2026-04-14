# Treewiz — Design Plan

## Overview

A TUI application for reconciling two parallel file trees that share most code
but have individual differences that cannot be eliminated or unified.

Primary use case: maintaining dotkit, which has public and enterprise versions
evolving independently and needing human diff resolution.

Repo: github.com/Stabledog/treewiz (public), cloned to /workarea/treewiz.

The original CLI tool in gitsmart/treewiz gets renamed to gitsmart/treewiz-cli
and stays in dotkit for now.

## TUI Library: Textual

[Textual](https://github.com/Textualize/textual) (MIT, by Will McGuigan / Textualize)

- Built on Rich — color/styling out of the box
- Widget-based layout with CSS-like styling
- Built-in keybinding system — easy to wire vi keys
- Active development, large community
- Supports split panes, trees, data tables, modals
- Runs in any terminal, no GUI dependencies

## Architecture

### Single TUI App

Launch:
```
treewiz /path/to/other-tree              # from within one tree
treewiz /path/to/tree-a /path/to/tree-b  # explicit both
```

All operations (diff, push, pull, browse) happen within the TUI rather than
as separate CLI subcommands.

### MVC Layering

The design separates business logic from UI:

- **Model layer**: tree scanning, file comparison, ignore/rule evaluation,
  push/pull operations. No dependencies on Textual. Independently testable
  and scriptable.
- **View layer**: Textual widgets, layout, colors, key display.
- **Controller layer**: keybinding dispatch, external tool launching,
  coordination between model and view.

This ensures the core logic can be driven from scripts or a future `--batch`
mode without dragging in the TUI.

### No Persistent Session State

The old treewiz attempted to track file disposition (done/skipped/pending)
across runs. This never worked well and the idea is unsound — file state can
be known by comparing hashes and checking `git status` on both sides.
Maintaining a separate truth source is fragile and confusing.

The TUI may have ephemeral in-session marks (simple boolean checkmarks that
disappear on exit, with a global reset), but nothing persists to disk.

## Core Concept: The Current Node

The app maintains a "current node" — a relative path that applies to both
trees simultaneously:

```
left_root:    /repos/dotkit-pub
right_root:   /repos/dotkit-bb
current_node: gitsmart/treewiz    # relative, applies to both
```

Navigation (drilling into a directory, going up) changes current_node and
both sides update. No need to "cd" in two places.

### L/R Model (Not A/B)

The two trees are **Left** and **Right**, corresponding to their position in
the UI. The user can swap sides freely. Push/pull direction is always relative
to what's on screen: push L->R, pull R->L. This avoids confusion about which
path is "A" vs "B".

## Proposed Layout

```
+- treewiz -- gitsmart/treewiz ---------------------------------+
| [L] /repos/dotkit-pub          [R] /repos/dotkit-bb           |
+--------------------------------+------------------------------+
|  File Browser / Node List      |  Details / Diff Preview      |
|                                |                              |
|  > cli.py        [modified]    |  --- L/cli.py                |
|    inventory.py  [same]        |  +++ R/cli.py                |
|  > session.py    [modified]    |  @@ -15,7 +15,8 @@           |
|    actions.py    [L-only]      |  -old line                   |
|    new_thing.py  [R-only]      |  +new line                   |
|                                |                              |
+--------------------------------+------------------------------+
| j/k:move  l:expand  h:up  d:diff  e:edit  P:push  p:pull ... |
+---------------------------------------------------------------+
```

## Vi Keybindings

| Key | Action |
|-----|--------|
| `j/k` | Move cursor up/down in file list |
| `l` / `Enter` | Drill into directory / open action on file |
| `h` | Go up one directory level |
| `d` | Open external diff (configurable, default `code --diff`) |
| `e` | Open file in editor |
| `t` | Open `tig` on current node directory |
| `/` | Filter/search within current file list |
| `m` | Toggle checkmark on file (session-only, not persisted) |
| `P` | Push selected file(s) L->R |
| `p` | Pull selected file(s) R->L |
| `s` | Toggle show/hide "same" files |
| `X` | Swap left and right trees |
| `!` | Open shell cd'd to current node in selected tree |
| `?` | Help overlay |
| `q` | Quit |

## `.treewizrc` Configuration

TOML format. Cascading (like .gitignore) — can live in tree roots or any
subdirectory. Global defaults in `~/.config/treewiz/config.toml`.

TOML is parsed via Python 3.11+ stdlib `tomllib`, or the `tomli` backport
package for Python 3.10.

```toml
# ~/.config/treewiz/config.toml  (global defaults)
[tools.diff]
cmd = "code --diff {left} {right}"
block = false           # fire-and-forget (GUI app)

[tools.editor]
cmd = "code {file}"
block = false

[tools.history]
cmd = "tig {dir}"
block = true            # TUI, needs the terminal

[display]
show_same = false
color_mismatch = "yellow"
color_left_only = "red"
color_right_only = "green"
```

```toml
# .treewizrc (per-directory overrides)
[ignore]
patterns = ["bb-*", "*.pyc", "__pycache__"]

[rules]
# Files that should never be reconciled
never_reconcile = ["setup.sh", "README.md"]
# Files where left tree is always authoritative
left_wins = ["LICENSE"]
# Files where right tree is always authoritative
right_wins = [".github/workflows/*"]
```

The `[rules]` section is extensible. The parser accepts arbitrary rule keys
and handlers can be added incrementally as new special cases emerge.

## External Tool Integration

| Tool | Trigger | Command |
|------|---------|---------|
| diff viewer | `d` key | Configurable, default `code --diff --wait {left} {right}` |
| editor | `e` key | Configurable, default `code {file}` |
| git history | `t` key | `tig {dir}` |
| shell | `!` key | Open shell cd'd to current node in selected tree |

All tools are configurable via `[tools]` in config.
The TUI suspends while external tools run, then resumes.

## File Inventory (Core Algorithm)

1. Discover files via `git ls-files -s` for tracked files, plus
   `git ls-files --others --exclude-standard` for untracked files.
   This catches uncommitted/untracked files that aren't .gitignored,
   preventing accidental deletion of files not yet in git on both sides.
2. Compare blob hashes for tracked files; fall back to content hashing
   for untracked files.
3. Classify each file: same / modified / L-only / R-only
4. Filter against `.treewizrc` ignore patterns

The current node (relative path) acts as the scope — only files under it
are shown.

## Dependencies

- `textual` (includes `rich`) — TUI framework
No other frameworks. TOML parsing uses stdlib `tomllib` (3.11+). No Click —
the old treewiz used Click for CLI subcommand parsing, but the new version
is a single Textual TUI app, so that's unnecessary.

Shebang: `#!/usr/bin/env python3`

## What Does NOT Belong in Treewiz

- Dotkit-specific logic (reconcile-status.sh, kit markers, loop-kits)
- Those workflows belong in dotkit-level scripts that call treewiz
- Treewiz is a generic two-tree reconciliation tool
- Dotkit may eventually have a `treewiz-install.sh` for setup — that's the
  right place for dotkit-specific integration

## Python Version & Install

- Python 3.12+
- No `tomli` dependency needed — `tomllib` is in stdlib since 3.11
- Install: `git clone` then `python3 -m pip install -e . --user`
