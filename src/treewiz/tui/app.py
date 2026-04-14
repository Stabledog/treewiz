"""Main Textual application for treewiz."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from treewiz.model.inventory import FileEntry, FileState, TreePair, scan
from treewiz.model.actions import push_files, pull_files
from treewiz.model.config import load_config
from treewiz.tui.file_browser import FileBrowser
from treewiz.tui.diff_panel import DiffPanel


class TreewizApp(App):
    """TUI for reconciling two parallel file trees."""

    TITLE = "treewiz"

    CSS = """
    Screen {
        layout: vertical;
    }

    #tree-header {
        dock: top;
        height: 3;
        padding: 0 1;
        background: $surface;
        color: $text;
    }

    #tree-header-left {
        width: 1fr;
        color: red;
    }

    #tree-header-right {
        width: 1fr;
        color: green;
    }

    #main-area {
        height: 1fr;
    }

    #node-bar {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "open_diff", "Diff"),
        Binding("e", "open_editor", "Edit"),
        Binding("t", "open_tig", "Tig"),
        Binding("s", "push_file", "Push L→R"),
        Binding("p", "pull_file", "Pull R→L"),
        Binding("exclamation_mark", "open_shell", "Shell"),
        Binding("question_mark", "help", "Help"),
        Binding("r", "refresh", "Refresh"),
        Binding("X", "swap_trees", "Swap L⇄R"),
    ]

    def __init__(self, left_root: Path, right_root: Path) -> None:
        super().__init__()
        self._left_root = left_root.resolve()
        self._right_root = right_root.resolve()
        self._current_node = ""
        self._tree_pair = TreePair(self._left_root, self._right_root, self._current_node)
        self._config = load_config(self._left_root, self._right_root, self._current_node)
        self._current_entry: FileEntry | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="node-bar")
        with Horizontal(id="tree-header"):
            yield Static(id="tree-header-left")
            yield Static(id="tree-header-right")
        with Horizontal(id="main-area"):
            yield FileBrowser()
            yield DiffPanel()
        yield Footer()

    def on_mount(self) -> None:
        self._update_headers()
        self._rescan()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate(self, node: str) -> None:
        """Change current node and rescan."""
        self._current_node = node
        self._tree_pair = TreePair(self._left_root, self._right_root, node)
        self._config = load_config(self._left_root, self._right_root, node)
        self._update_headers()
        self._rescan()

    def _rescan(self) -> None:
        """Rescan both trees and refresh the browser and diff panel."""
        inv = scan(self._tree_pair)
        browser = self.query_one(FileBrowser)
        browser.set_inventory(inv)
        diff_panel = self.query_one(DiffPanel)
        diff_panel.set_inventory(inv)
        diff_panel.clear()
        self._current_entry = None

    def _update_headers(self) -> None:
        node_bar = self.query_one("#node-bar", Static)
        node_display = self._current_node or "/"
        node_bar.update(f" node: {node_display}")

        left_hdr = self.query_one("#tree-header-left", Static)
        right_hdr = self.query_one("#tree-header-right", Static)
        left_full = self._left_root / self._current_node if self._current_node else self._left_root
        right_full = self._right_root / self._current_node if self._current_node else self._right_root
        left_hdr.update(f" [L] {left_full}")
        right_hdr.update(f" [R] {right_full}")

    # ------------------------------------------------------------------
    # File browser messages
    # ------------------------------------------------------------------

    def on_file_browser_file_highlighted(self, event: FileBrowser.FileHighlighted) -> None:
        diff_panel = self.query_one(DiffPanel)
        if event.is_dir:
            diff_panel.show_dir_info(event.dir_name)
            self._current_entry = None
        else:
            self._current_entry = event.entry
            diff_panel.show_entry(event.entry)

    def on_file_browser_file_selected(self, event: FileBrowser.FileSelected) -> None:
        if event.is_dir:
            if self._current_node:
                new_node = f"{self._current_node}/{event.dir_name}"
            else:
                new_node = event.dir_name
            self._navigate(new_node)

    def on_file_browser_go_up(self, event: FileBrowser.GoUp) -> None:
        if self._current_node:
            parts = self._current_node.rsplit("/", 1)
            new_node = parts[0] if len(parts) > 1 else ""
            self._navigate(new_node)

    # ------------------------------------------------------------------
    # External tools
    # ------------------------------------------------------------------

    def _tool_info(self, name: str) -> tuple[str, bool]:
        """Return (cmd_template, block) for a named tool."""
        tool = self._config.get("tools", {}).get(name, {})
        if isinstance(tool, str):
            # Legacy flat string format — treat as blocking
            return tool, True
        return tool.get("cmd", ""), tool.get("block", True)

    def _run_tool(self, cmd: str, block: bool) -> None:
        """Run an external command, blocking (suspend TUI) or fire-and-forget."""
        if block:
            with self.suspend():
                os.system(cmd)
        else:
            subprocess.Popen(cmd, shell=True, start_new_session=True)

    def action_open_diff(self) -> None:
        entry = self._current_entry
        if not entry or entry.state != FileState.MISMATCH:
            self.notify("No mismatched file selected", severity="warning")
            return
        tp = self._tree_pair
        left = str(tp.left_path(entry))
        right = str(tp.right_path(entry))
        cmd_template, block = self._tool_info("diff")
        cmd = cmd_template.format(left=left, right=right)
        self._run_tool(cmd, block)
        if block:
            self._rescan()

    def action_open_editor(self) -> None:
        entry = self._current_entry
        if not entry:
            self.notify("No file selected", severity="warning")
            return
        tp = self._tree_pair
        paths = []
        if entry.state in (FileState.MISMATCH, FileState.LEFT_ONLY, FileState.SAME):
            paths.append(str(tp.left_path(entry)))
        if entry.state in (FileState.MISMATCH, FileState.RIGHT_ONLY, FileState.SAME):
            paths.append(str(tp.right_path(entry)))
        cmd_template, block = self._tool_info("editor")
        if block:
            with self.suspend():
                for p in paths:
                    os.system(cmd_template.format(file=p))
            self._rescan()
        else:
            for p in paths:
                subprocess.Popen(cmd_template.format(file=p), shell=True, start_new_session=True)

    def action_open_tig(self) -> None:
        tp = self._tree_pair
        left_dir = str(tp.left_node_dir())
        cmd_template, block = self._tool_info("history")
        cmd = cmd_template.format(dir=left_dir)
        self._run_tool(cmd, block)

    def action_open_shell(self) -> None:
        tp = self._tree_pair
        node_dir = str(tp.left_node_dir())
        with self.suspend():
            shell = os.environ.get("SHELL", "/bin/bash")
            subprocess.run([shell], cwd=node_dir, env={
                **os.environ,
                "TREEWIZ_NODE": self._current_node,
                "TVL": str(tp.left_node_dir()),
                "TVR": str(tp.right_node_dir()),
            })

    # ------------------------------------------------------------------
    # Push / Pull
    # ------------------------------------------------------------------

    def action_push_file(self) -> None:
        entry = self._current_entry
        if not entry or entry.state not in (FileState.MISMATCH, FileState.LEFT_ONLY):
            self.notify("Nothing to push", severity="warning")
            return
        inv = scan(self._tree_pair)
        copied = push_files(inv, [entry])
        if copied:
            self.notify(f"Pushed: {', '.join(copied)}")
        self._rescan()

    def action_pull_file(self) -> None:
        entry = self._current_entry
        if not entry or entry.state not in (FileState.MISMATCH, FileState.RIGHT_ONLY):
            self.notify("Nothing to pull", severity="warning")
            return
        inv = scan(self._tree_pair)
        copied = pull_files(inv, [entry])
        if copied:
            self.notify(f"Pulled: {', '.join(copied)}")
        self._rescan()

    # ------------------------------------------------------------------
    # Swap
    # ------------------------------------------------------------------

    def action_refresh(self) -> None:
        """Rescan both trees."""
        self._rescan()
        self.notify("Refreshed")

    def action_swap_trees(self) -> None:
        """Swap left and right trees."""
        self._left_root, self._right_root = self._right_root, self._left_root
        self._tree_pair = TreePair(self._left_root, self._right_root, self._current_node)
        self._config = load_config(self._left_root, self._right_root, self._current_node)
        self._update_headers()
        self._rescan()
        self.notify("Swapped L ⇄ R")

    def action_help(self) -> None:
        help_text = (
            "j/k: move up/down       |  ctrl+d/u: page down/up  |  l/Enter: enter dir\n"
            "h: go up                |  d: diff                 |  e: edit file\n"
            "t: tig                  |  s: push L→R             |  p: pull R→L\n"
            "m: check/uncheck        |  =: toggle same          |  r: refresh\n"
            "X: swap L⇄R             |  !: shell                |  q: quit"
        )
        self.notify(help_text, title="Keybindings", timeout=10)
