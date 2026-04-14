"""Modal for choosing which tree receives the ignore pattern."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static
from rich.text import Text


class IgnoreTargetModal(ModalScreen[str | None]):
    """Ask user whether to write the ignore rule to the left or right tree."""

    BINDINGS = [
        Binding("l", "choose_left", "", show=False),
        Binding("r", "choose_right", "", show=False),
        Binding("escape", "cancel", "", show=False),
    ]

    DEFAULT_CSS = """
    IgnoreTargetModal {
        align: center middle;
    }
    IgnoreTargetModal > Static {
        background: $surface;
        border: thick $primary;
        padding: 1 3;
        width: auto;
    }
    """

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def compose(self) -> ComposeResult:
        text = Text()
        text.append("Add '")
        text.append(self._name, style="bold")
        text.append("' to ignore in:\n\n  ")
        text.append("L", style="bold yellow on blue")
        text.append("eft   ")
        text.append("R", style="bold yellow on blue")
        text.append("ight   ")
        text.append("Esc", style="bold yellow on blue")
        text.append(" cancel")
        yield Static(text)

    def action_choose_left(self) -> None:
        self.dismiss("left")

    def action_choose_right(self) -> None:
        self.dismiss("right")

    def action_cancel(self) -> None:
        self.dismiss(None)
