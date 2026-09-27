"""Menu banner: Clawd cooking."""

from __future__ import annotations

from .ui import color_enabled

# Colour per character class (256 colours): chef hat, Clawd, pan, steam, flames.
_ORANGE, _WHITE, _GREY, _STEAM, _FIRE = 173, 255, 244, 250, 208

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

SUBTITLE = "activity-cheatmap · draw on your GitHub contribution graph"


def _colored(text: str, mask: str) -> str:
    out = []
    for char, key in zip(text, mask):
        color = _MASK_COLORS.get(key)
        out.append(f"\033[38;5;{color}m{char}\033[0m" if color and char != " " else char)
    return "".join(out)


def clawd(color: bool | None = None) -> list[str]:
    color = color_enabled() if color is None else color
    return [(_colored(text, mask) if color else text).rstrip() for text, mask in _CLAWD]


def banner() -> str:
    return "\n".join(clawd() + ["", "  " + SUBTITLE])
