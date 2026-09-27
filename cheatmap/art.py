"""Menu banner: Clawd cooking, and the title drawn like a contribution graph."""

from __future__ import annotations

import shutil

from . import font
from .ui import color_enabled

# Colour per character class (256 colours): chef hat, Clawd, pan, steam, flames.
_ORANGE, _WHITE, _GREY, _STEAM, _FIRE, _GREEN = 173, 255, 244, 250, 208, 34

# Each line: text, and a mask of the same length giving the colour of each character.
_CLAWD = [
    ("        .-~~~-.                          ", "        HHHHHHH                          "),
    ("       (  ~ ~  )                ) ) )    ", "       HHHHHHHHH                SSSSS    "),
    ("        '-----'                ( ( (     ", "        HHHHHHH                SSSSS     "),
    ("         |___|                  ) ) )    ", "         HHHHH                  SSSSS    "),
    ("        ▐▛███▜▌                          ", "        CCCCCCC                          "),
    ("       ▝▜█████▛▘━━━━━━━━━━━━(__________) ", "       CCCCCCCCCPPPPPPPPPPPPPPPPPPPPPPPP "),
    ("         ▘▘ ▝▝                ^^^^^^     ", "         CCCCC                FFFFFF     "),
]
_MASK_COLORS = {"H": _WHITE, "C": _ORANGE, "P": _GREY, "S": _STEAM, "F": _FIRE}

TITLE = "CLAWD COOKING"
SUBTITLE = "activity-cheatmap · draw on your GitHub contribution graph"


def _colored(text: str, mask: str) -> str:
    out = []
    for char, key in zip(text, mask, strict=True):
        color = _MASK_COLORS.get(key)
        out.append(f"\033[38;5;{color}m{char}\033[0m" if color and char != " " else char)
    return "".join(out)


def clawd(color: bool | None = None) -> list[str]:
    color = color_enabled() if color is None else color
    return [(_colored(text, mask) if color else text).rstrip() for text, mask in _CLAWD]


def pixel_title(text: str = TITLE, color: bool | None = None) -> list[str]:
    """`text` in the 7-pixel font, one cell per pixel, like a contribution graph."""
    color = color_enabled() if color is None else color
    lit = f"\033[38;5;{_GREEN}m■\033[0m" if color else "■"
    dark = "\033[38;5;237m·\033[0m" if color else " "
    return [("".join(lit if pixel else dark for pixel in row)).rstrip() for row in font.render(text)]


def banner() -> str:
    lines = clawd()
    width = len(font.render(TITLE)[0])
    if shutil.get_terminal_size((80, 24)).columns >= width + 2:
        lines += [""] + ["  " + line for line in pixel_title()]
    else:
        lines += ["", f"        ~ {TITLE} ~"]
    lines += ["", "  " + SUBTITLE]
    return "\n".join(lines)
