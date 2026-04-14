"""Color theme constants for treewiz TUI."""

from rich.style import Style

# File state colors
MISMATCH = Style(color="yellow", bold=True)
LEFT_ONLY = Style(color="red")
RIGHT_ONLY = Style(color="green")
SAME = Style(color="bright_black")
BLESSED = Style(color="cyan", bold=True)

# UI elements
HEADER_STYLE = Style(color="white", bold=True)
NODE_PATH = Style(color="cyan", bold=True)
DIR_STYLE = Style(color="blue", bold=True)
CHECKED = Style(color="bright_green")
CURSOR = Style(bgcolor="grey27")

# State badge text
BADGES = {
    "same": ("[same]", SAME),
    "mismatch": ("[mismatch]", MISMATCH),
    "left-only": ("[L-only]", LEFT_ONLY),
    "right-only": ("[R-only]", RIGHT_ONLY),
    "blessed": ("[blessed]", BLESSED),
}
