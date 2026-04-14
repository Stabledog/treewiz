"""Diff panel: right pane showing diff preview for the selected file."""

from __future__ import annotations

from textual.widget import Widget
from textual.widgets import Static
from textual.containers import VerticalScroll

from rich.text import Text

from treewiz.model.inventory import FileEntry, FileState, Inventory
from treewiz.model.differ import diff_entry
from treewiz.tui import theme


class DiffPanel(Widget):
    """Read-only panel showing diff output or file state info."""

    DEFAULT_CSS = """
    DiffPanel {
        width: 1fr;
        height: 1fr;
        border: solid $accent;
        border-title-color: $text;
    }

    DiffPanel VerticalScroll {
        width: 1fr;
        height: 1fr;
    }

    DiffPanel #diff-content {
        width: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._inventory: Inventory | None = None

    def compose(self):
        with VerticalScroll():
            yield Static("", id="diff-content")

    def set_inventory(self, inv: Inventory) -> None:
        self._inventory = inv

    def show_entry(self, entry: FileEntry | None) -> None:
        """Update the panel to show info about *entry*."""
        content = self.query_one("#diff-content", Static)

        if entry is None:
            content.update("")
            return

        if entry.state == FileState.MISMATCH:
            if self._inventory:
                diff_text = diff_entry(self._inventory, entry, color=False)
                if diff_text:
                    content.update(_colorize_diff(diff_text))
                else:
                    content.update(Text("(files are identical)", style="dim"))
            return

        if entry.state == FileState.LEFT_ONLY:
            content.update(Text(f"  {entry.path}\n  exists only in LEFT tree", style=theme.LEFT_ONLY))
        elif entry.state == FileState.RIGHT_ONLY:
            content.update(Text(f"  {entry.path}\n  exists only in RIGHT tree", style=theme.RIGHT_ONLY))
        elif entry.state == FileState.SAME:
            content.update(Text(f"  {entry.path}\n  identical in both trees", style=theme.SAME))

    def show_dir_info(self, dir_name: str) -> None:
        """Show summary for a directory."""
        content = self.query_one("#diff-content", Static)
        if not self._inventory:
            content.update("")
            return
        # Count files under this dir
        prefix = dir_name + "/"
        entries = [e for p, e in self._inventory.files.items() if p.startswith(prefix)]
        mismatched = sum(1 for e in entries if e.state == FileState.MISMATCH)
        left_only = sum(1 for e in entries if e.state == FileState.LEFT_ONLY)
        right_only = sum(1 for e in entries if e.state == FileState.RIGHT_ONLY)
        same = sum(1 for e in entries if e.state == FileState.SAME)

        t = Text()
        t.append(f"  {dir_name}/\n\n", style=theme.DIR_STYLE)
        if mismatched:
            t.append(f"  {mismatched} mismatch\n", style=theme.MISMATCH)
        if left_only:
            t.append(f"  {left_only} L-only\n", style=theme.LEFT_ONLY)
        if right_only:
            t.append(f"  {right_only} R-only\n", style=theme.RIGHT_ONLY)
        if same:
            t.append(f"  {same} same\n", style=theme.SAME)
        content.update(t)

    def clear(self) -> None:
        self.query_one("#diff-content", Static).update("")


def _colorize_diff(text: str) -> Text:
    """Apply colors to unified diff output."""
    result = Text()
    for line in text.splitlines(keepends=True):
        if line.startswith("+++") or line.startswith("---"):
            result.append(line, style="bold")
        elif line.startswith("@@"):
            result.append(line, style="cyan")
        elif line.startswith("+"):
            result.append(line, style="green")
        elif line.startswith("-"):
            result.append(line, style="red")
        else:
            result.append(line)
    return result
