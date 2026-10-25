"""Light and dark themes (Could tier, [D55]).

A theme is plain data: colours for the map and a Qt style sheet for the widgets. The
light style sheet only styles what needs to follow the theme (banner, hints, map buttons)
and leaves the platform's own look alone; the dark one restyles every widget.
"""

from dataclasses import dataclass


def luminance(colour: str) -> float:
    """WCAG relative luminance of '#RRGGBB'."""
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two '#RRGGBB' colours, from 1 to 21."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@dataclass(frozen=True)
class Theme:
    """Everything that changes between light and dark."""

    name: str
    background: str  # map background
    label: str  # station name text
    marker_outline: str
    marker_fill: str  # an ordinary station
    interchange_fill: str
    closed_fill: str
    walk: str  # the dotted walk line
    glow: bool  # draw a soft halo under the route
    dot_fill: str  # route station dots
    dot_outline: str
    ring_fill: str  # change badge ring
    ring_outline: str
    badge_fill: str  # change label box, #AARRGGBB
    badge_text: str
    stylesheet: str


def banner_and_hint_qss(error: tuple[str, str, str], info: tuple[str, str, str],
                        hint: str) -> str:
    """Rules for the message banner (background, text, border per kind) and field hints."""
    rules = [f"QLabel#hint {{ color: {hint}; }}"]
    for kind, (bg, fg, border) in (("error", error), ("info", info)):
        rules.append(f'#banner[kind="{kind}"] {{ background: {bg}; border: 1px solid {border}; }}')
        rules.append(f'#banner[kind="{kind}"] QLabel {{ background: transparent; color: {fg}; }}')
    return "\n".join(rules)


def controls_qss(background: str, text: str, border: str, hover: str) -> str:
    """Rules for the buttons floating on the map."""
    return f"""
#mapControls QToolButton {{ background: {background}; color: {text};
    border: 1px solid {border}; border-radius: 6px; font-weight: bold; padding: 0; }}
#mapControls QToolButton:hover {{ background: {hover}; }}
#mapControls QToolButton:disabled {{ color: {border}; }}
"""


# Light hint red is 6.0:1 on white; the dark one is lighter so it keeps 4.5:1 on #202124.
LIGHT_QSS = banner_and_hint_qss(
    ("#FDECEA", "#8C1D18", "#F2B8B5"), ("#E8F0FE", "#174EA6", "#AECBFA"), "#B3261E"
) + controls_qss("rgba(255,255,255,235)", "#202124", "#9AA0A6", "#F1F3F4")

DARK_QSS = """
QWidget { background: #202124; color: #E8EAED; }
QLabel { background: transparent; }
QLineEdit, QComboBox, QListWidget { background: #2B2C30; color: #E8EAED;
    border: 1px solid #5F6368; border-radius: 4px; padding: 3px; }
QListWidget::item:selected, QComboBox QAbstractItemView::item:selected {
    background: #3A4A63; color: #FFFFFF; }
QPushButton, QToolButton { background: #303134; color: #E8EAED; border: 1px solid #5F6368;
    border-radius: 4px; padding: 5px 10px; }
QPushButton:hover, QToolButton:hover { background: #3C4043; }
QPushButton:disabled, QToolButton:disabled { color: #80868B; }
QMenu { background: #2B2C30; color: #E8EAED; border: 1px solid #5F6368; }
QMenu::item:selected { background: #3A4A63; }
QToolTip { background: #303134; color: #E8EAED; border: 1px solid #5F6368; }
QStatusBar { background: #202124; color: #E8EAED; }
QGraphicsView { border: 1px solid #3C4043; }
""" + banner_and_hint_qss(
    ("#4A2523", "#F9B4AE", "#8C3A36"), ("#1F3350", "#AECBFA", "#3B5F94"), "#FF8A80"
) + controls_qss("rgba(48,49,52,235)", "#E8EAED", "#5F6368", "#3C4043")

LIGHT = Theme(
    name="light", background="#FAFAF7", label="#222222", marker_outline="#333333",
    marker_fill="#555555", interchange_fill="#FFFFFF", closed_fill="#BBBBBB", walk="#666666",
    glow=False, dot_fill="#FFFFFF", dot_outline="#222222", ring_fill="#FFFFFF",
    ring_outline="#111111", badge_fill="#EBFFFFFF", badge_text="#111111", stylesheet=LIGHT_QSS)

DARK = Theme(
    name="dark", background="#18191D", label="#E8EAED", marker_outline="#0E0F12",
    marker_fill="#AEB4BC", interchange_fill="#F1F3F4", closed_fill="#4A4D55", walk="#C4C7CC",
    glow=True, dot_fill="#F1F3F4", dot_outline="#0E0F12", ring_fill="#202226",
    ring_outline="#F1F3F4", badge_fill="#F0202226", badge_text="#F1F3F4", stylesheet=DARK_QSS)

THEMES = {LIGHT.name: LIGHT, DARK.name: DARK}


def theme_named(name: object) -> Theme:
    """The theme called `name`; anything unknown (an old or damaged setting) is light."""
    return THEMES.get(name, LIGHT) if isinstance(name, str) else LIGHT


def other_theme(theme: Theme) -> Theme:
    """The theme the toggle button switches to."""
    return DARK if theme is LIGHT else LIGHT
