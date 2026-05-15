# Treewiz — Transition From treewiz-cli

## Background

Treewiz exists in two forms that share ancestry but have diverged:

1. **`treewiz-cli`** — the original Click-based CLI, lives in `~/.local/bin/treewiz-kit/`
   as a dotkit. Subcommand-per-operation design (`status`, `diff`, `edit`, `push`, `pull`,
   `active-dirs`, `loop-kits`).

2. **`treewiz`** (this repo) — a Textual TUI rewrite. All operations happen inside one
   interactive app instead of separate CLI subcommands.

## What Was Ported / Rewritten

| Concept | treewiz-cli (original) | treewiz (this repo) |
|---------|------------------------|---------------------|
| Naming | ref / tgt (reference=cwd, target=arg) | left / right (screen position) |
| File discovery | `git ls-files -s` only | tracked + untracked (`--others --exclude-standard`) |
| Hash comparison | git blob hashes directly | SHA-256 of file content (works across tracked/untracked) |
| Ignore mechanism | `.treewiz-cli-ignore` flat file | `.treewizrc` TOML `[ignore]` section (+ legacy fallback) |
| Config | none | `.treewizrc` TOML with `[tools]`, `[display]`, `[ignore]`, `[blessed]` |
| Session state | Persistent JSON in `.git/treewiz-cli/sessions/` | None (explicitly rejected as unsound) |
| UI | Click subcommands + raw terminal for `loop-kits` | Full Textual TUI |
| Dependencies | Click, Python 3.10+ | Textual, Python 3.12+ |

The core model modules (`inventory.py`, `actions.py`, `differ.py`) were rewritten with the
same structure but different naming conventions and richer features. They are **not** shared
code — each project has its own copy.

## What Remains Only in treewiz-cli (Not Ported)

These features have no equivalent in the TUI yet:

- **`session.py`** — Resumable file disposition tracking (done/skipped/pending).
  Intentionally abandoned: the TUI plan says hashes + git status are the source of truth.

- **`activity.py`** / `active-dirs` — Shows which directories had recent git commits
  in each tree. Useful for scoping reconciliation. Could become a treewiz feature someday.

- **`loop.py`** / `loop-kits` — Interactive dotkit-level selector that runs
  `reconcile-status.sh` and lets you mark kits as YES/IGNORE. This is dotkit-specific
  and should stay in the dotkit, not in generic treewiz.

- **`editor.py`** — VS Code `--diff --wait` integration. Superseded by treewiz's
  configurable `[tools.diff]` in `.treewizrc`.

## Intended End State

1. **`treewiz` (this repo)** is the canonical tool for two-tree reconciliation.
   Generic, public, no dotkit coupling.

2. **`treewiz-cli` (the dotkit)** retains only dotkit-specific workflows:
   - `loop-kits` (calls `reconcile-status.sh`, manages `.reconcile-*` markers)
   - Possibly `active-dirs` until that gets absorbed into the TUI
   - The duplicated model code (`inventory.py`, `actions.py`, `differ.py`) should
     eventually be replaced by importing from `treewiz.model` as a library dependency.

3. The dotkit's `status`, `diff`, `edit`, `push`, `pull` subcommands are superseded
   by the TUI and can be deprecated once the TUI is stable.

## Current State (May 2026)

Both tools are at v0.1.0. The TUI is functional but has no tests. The CLI has tests
and is actively used for dotkit reconciliation via `loop-kits`. Neither depends on the
other at the code level — they are fully independent Python packages that happen to
solve overlapping problems.

The refactoring to unify them has not started. When it does, the path is:
1. Add treewiz as a dependency of treewiz-kit (or make the model installable separately)
2. Replace `treewiz_cli/inventory.py`, `actions.py`, `differ.py` with imports from `treewiz.model`
3. Keep `loop.py`, `activity.py`, `session.py` in the dotkit (they are CLI/dotkit-specific)
4. Deprecate the CLI subcommands that duplicate TUI functionality
