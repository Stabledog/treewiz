"""File browser widget: left panel showing files at the current node."""

from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from rich.text import Text

from treewiz.model.inventory import FileEntry, FileState, Inventory
from treewiz.tui import theme


class FileBrowser(Widget, can_focus=True):
    """Scrollable file/directory list with vi-style navigation."""

    DEFAULT_CSS = """
    FileBrowser {
        width: 1fr;
        height: 1fr;
        border: solid $accent;
        border-title-color: $text;
    }

    FileBrowser OptionList {
        width: 1fr;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("ctrl+d", "page_down", "Page down", show=False),
        Binding("ctrl+u", "page_up", "Page up", show=False),
        Binding("l", "select_item", "Enter", show=False),
        Binding("enter", "select_item", "Enter", show=False),
        Binding("h", "go_up", "Back", show=False),
        Binding("u", "go_up", "Back", show=False),
        Binding("equals_sign", "toggle_same", "Toggle same", show=False),
        Binding("m", "toggle_check", "Check/uncheck", show=False),
    ]

    show_same: reactive[bool] = reactive(False)

    class FileHighlighted(Message):
        """Cursor moved to a new file."""

        def __init__(self, entry: FileEntry | None, is_dir: bool = False, dir_name: str = "") -> None:
            super().__init__()
            self.entry = entry
            self.is_dir = is_dir
            self.dir_name = dir_name

    class FileSelected(Message):
        """User pressed enter/l on a file."""

        def __init__(self, entry: FileEntry | None, is_dir: bool = False, dir_name: str = "") -> None:
            super().__init__()
            self.entry = entry
            self.is_dir = is_dir
            self.dir_name = dir_name

    class GoUp(Message):
        """User pressed h to go up a directory level."""

    def __init__(self) -> None:
        super().__init__()
        self._inventory: Inventory | None = None
        self._items: list[dict] = []  # [{type: "dir"|"file", name:, entry:?}]

    def compose(self):
        yield OptionList(id="file-list")

    @property
    def option_list(self) -> OptionList:
        return self.query_one("#file-list", OptionList)

    def set_inventory(self, inv: Inventory) -> None:
        """Populate the browser from an inventory scan."""
        self._inventory = inv
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild the option list from current inventory and display settings."""
        inv = self._inventory
        if inv is None:
            return

        ol = self.option_list
        ol.clear_options()
        self._items.clear()

        # Directories first
        for d in inv.dirs:
            from treewiz.model.inventory import _dir_state
            state = _dir_state(d, inv.files)
            if state == FileState.SAME and not self.show_same:
                continue
            label = Text()
            label.append("  ", style="")
            label.append(f"{d}/", style=theme.DIR_STYLE)
            label.append(f"  {_badge_text(state)}", style=_badge_style(state))
            self._items.append({"type": "dir", "name": d})
            ol.add_option(Option(label))

        # Files at this level (no "/" in path)
        for path, entry in sorted(inv.files.items()):
            if "/" in path:
                continue  # belongs to a subdirectory
            if entry.state == FileState.SAME and not self.show_same:
                continue
            check = " \u2713" if entry.checked else "  "
            label = Text()
            label.append(check, style=theme.CHECKED if entry.checked else "")
            label.append(f"{entry.path}", style=_badge_style(entry.state))
            label.append(f"  {_badge_text(entry.state)}", style=_badge_style(entry.state))
            self._items.append({"type": "file", "name": path, "entry": entry})
            ol.add_option(Option(label))

        if not self._items:
            ol.add_option(Option(Text("  (empty)", style="dim")))
            return

        # Auto-highlight first item so selection-dependent actions work
        ol.highlighted = 0
        self._notify_highlighted(0)

    def watch_show_same(self, value: bool) -> None:
        self._rebuild()

    def _notify_highlighted(self, idx: int) -> None:
        """Post a FileHighlighted message for the item at *idx*."""
        if idx < len(self._items):
            item = self._items[idx]
            if item["type"] == "dir":
                self.post_message(self.FileHighlighted(None, is_dir=True, dir_name=item["name"]))
            else:
                self.post_message(self.FileHighlighted(item["entry"]))

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self._notify_highlighted(event.option_index)

    def action_cursor_down(self) -> None:
        ol = self.option_list
        if ol.option_count > 0:
            idx = ol.highlighted or 0
            if idx < ol.option_count - 1:
                ol.highlighted = idx + 1

    def action_cursor_up(self) -> None:
        ol = self.option_list
        if ol.option_count > 0:
            idx = ol.highlighted or 0
            if idx > 0:
                ol.highlighted = idx - 1

    def action_page_down(self) -> None:
        ol = self.option_list
        if ol.option_count > 0:
            # Move down by approximately half the visible height (page size)
            page_size = max(1, ol.region.height - 2) // 2
            idx = ol.highlighted or 0
            new_idx = min(idx + page_size, ol.option_count - 1)
            ol.highlighted = new_idx

    def action_page_up(self) -> None:
        ol = self.option_list
        if ol.option_count > 0:
            # Move up by approximately half the visible height (page size)
            page_size = max(1, ol.region.height - 2) // 2
            idx = ol.highlighted or 0
            new_idx = max(idx - page_size, 0)
            ol.highlighted = new_idx

    def action_select_item(self) -> None:
        ol = self.option_list
        idx = ol.highlighted
        if idx is not None and idx < len(self._items):
            item = self._items[idx]
            if item["type"] == "dir":
                self.post_message(self.FileSelected(None, is_dir=True, dir_name=item["name"]))
            else:
                self.post_message(self.FileSelected(item["entry"]))

    def action_go_up(self) -> None:
        self.post_message(self.GoUp())

    def action_toggle_same(self) -> None:
        self.show_same = not self.show_same

    def action_toggle_check(self) -> None:
        ol = self.option_list
        idx = ol.highlighted
        if idx is not None and idx < len(self._items):
            item = self._items[idx]
            if item["type"] == "file":
                entry: FileEntry = item["entry"]
                entry.checked = not entry.checked
                self._rebuild()
                # Restore cursor position
                if idx < ol.option_count:
                    ol.highlighted = idx


def _badge_text(state: FileState) -> str:
    info = theme.BADGES.get(state.value, ("", ""))
    return info[0]


def _badge_style(state: FileState):
    info = theme.BADGES.get(state.value)
    return info[1] if info else ""
