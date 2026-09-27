"""Heatmap patterns.

A pattern turns a grid cell (col, row) into a level 0–4 (GitHub shows
5 shades: empty + 4 greens). `build()` returns a `cell -> level` function
for a grid of `cols` columns and 7 rows (row 0 = Sunday).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import font
from .periods import ROWS
from .sprites import SPRITES

MAX_LEVEL = 4
CellFn = Callable[[int, int], int]


class PatternError(ValueError):
    pass


@dataclass
class Opt:
    name: str
    kind: str  # int | bool | str | choice | level | levels
    default: Any
    help: str
    choices: tuple[str, ...] = ()
    minimum: int = 1


@dataclass
class PatternDef:
    name: str
    help: str
    opts: list[Opt]
    factory: Callable[[dict, int], CellFn] = field(repr=False)


PATTERNS: dict[str, PatternDef] = {}


def register(name: str, help_text: str, *opts: Opt):
    def decorator(factory):
        PATTERNS[name] = PatternDef(name, help_text, list(opts), factory)
        return factory

    return decorator


# --- options -------------------------------------------------------------

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _level(value, name: str) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        raise PatternError(f"{name}: '{value}' is not a level (0-{MAX_LEVEL})") from None
    if not 0 <= level <= MAX_LEVEL:
        raise PatternError(f"{name}: level {level} out of range 0-{MAX_LEVEL}")
    return level


def coerce(opt: Opt, value):
    name = opt.name
    if opt.kind == "int":
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise PatternError(f"{name}: '{value}' is not an integer") from None
        if number < opt.minimum:
            raise PatternError(f"{name}: must be >= {opt.minimum}")
        return number
    if opt.kind == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).lower()
        if text in _TRUE | _FALSE:
            return text in _TRUE
        raise PatternError(f"{name}: '{value}' is not a boolean")
    if opt.kind == "choice":
        text = str(value).lower()
        if text not in opt.choices:
            raise PatternError(f"{name}: '{value}' not in {', '.join(opt.choices)}")
        return text
    if opt.kind == "level":
        return _level(value, name)
    if opt.kind == "levels":
        items = value if isinstance(value, (list, tuple)) else str(value).split(",")
        levels = [_level(item, name) for item in items]
        if len(levels) != 7:
            raise PatternError(f"{name}: expected 7 levels (Mon..Sun), got {len(levels)}")
        return levels
    return str(value)


def resolve_options(name: str, raw: dict | None) -> dict:
    """Validate `raw` options for pattern `name`, fill in defaults."""
    if name not in PATTERNS:
        raise PatternError(f"unknown pattern '{name}' (see --list-patterns)")
    spec = {opt.name: opt for opt in PATTERNS[name].opts}
    raw = dict(raw or {})
    unknown = set(raw) - set(spec)
    if unknown:
        raise PatternError(f"{name}: unknown option(s) {', '.join(sorted(unknown))}")
    resolved = {}
    for opt in spec.values():
        if opt.name in raw:
            resolved[opt.name] = coerce(opt, raw[opt.name])
        elif opt.default is None:
            raise PatternError(f"{name}: option '{opt.name}' is required")
        else:
            resolved[opt.name] = opt.default
    return resolved


def build(name: str, options: dict, cols: int) -> CellFn:
    return PATTERNS[name].factory(resolve_options(name, options), cols)


# --- helpers -------------------------------------------------------------


def _band(t: float, low: int, high: int) -> int:
    """Map t in [0, 1] to one of the levels low..high in equal bands."""
    if high < low:
        low, high = high, low
    count = high - low + 1
    return low + min(int(t * count), count - 1)


def _wave(position: float, span: float, opts: dict) -> float:
    """Position along the gradient -> t in [0, 1), repeated `cycles` times."""
    u = position / span * opts["cycles"]
    t = u - math.floor(u)
    return 1 - abs(2 * t - 1) if opts["mirror"] else t


def _gradient_opts(directions: tuple[str, ...]) -> list[Opt]:
    return [
        Opt("direction", "choice", directions[0], "side that gets darker", directions),
        Opt("cycles", "int", 1, "number of repetitions across the period"),
        Opt("mirror", "bool", False, "fade in then out (light-dark-light)"),
        Opt("min", "level", 0, "lightest level"),
        Opt("max", "level", MAX_LEVEL, "darkest level"),
    ]


# --- gradients -----------------------------------------------------------


@register("gradient-h", "horizontal fade across the weeks", *_gradient_opts(("right", "left")))
def _gradient_h(opts, cols):
    def cell(col, row):
        position = col if opts["direction"] == "right" else cols - 1 - col
        return _band(_wave(position, cols, opts), opts["min"], opts["max"])

    return cell


@register("gradient-v", "vertical fade across weekdays", *_gradient_opts(("down", "up")))
def _gradient_v(opts, cols):
    def cell(col, row):
        position = row if opts["direction"] == "down" else ROWS - 1 - row
        return _band(_wave(position, ROWS, opts), opts["min"], opts["max"])

    return cell


_DIAGONALS = ("down-right", "down-left", "up-right", "up-left")


@register("gradient-diag", "diagonal fade (4 directions)", *_gradient_opts(_DIAGONALS))
def _gradient_diag(opts, cols):
    direction = opts["direction"]

    def cell(col, row):
        x = col if direction.endswith("right") else cols - 1 - col
        y = row if direction.startswith("down") else ROWS - 1 - row
        return _band(_wave(x + y, cols + ROWS - 1, opts), opts["min"], opts["max"])

    return cell


# --- regular patterns ----------------------------------------------------


@register(
    "weekly",
    "one level per weekday",
    Opt("levels", "levels", [1, 2, 3, 4, 4, 4, 0], "7 levels, Monday first"),
)
def _weekly(opts, cols):
    levels = opts["levels"]
    return lambda col, row: levels[(row + 6) % 7]  # row 0 = Sunday


@register("solid", "same level everywhere", Opt("level", "level", MAX_LEVEL, "level"))
def _solid(opts, cols):
    return lambda col, row: opts["level"]


@register(
    "checker",
    "checkerboard",
    Opt("size", "int", 1, "square size in cells"),
    Opt("fg", "level", MAX_LEVEL, "dark squares"),
    Opt("bg", "level", 0, "light squares"),
)
def _checker(opts, cols):
    size = opts["size"]

    def cell(col, row):
        return opts["fg"] if (col // size + row // size) % 2 == 0 else opts["bg"]

    return cell


@register(
    "stripes",
    "stripes",
    Opt(
        "orientation", "choice", "vertical", "stripe direction", ("vertical", "horizontal", "diagonal", "anti-diagonal")
    ),
    Opt("width", "int", 1, "stripe width in cells"),
    Opt("gap", "int", 1, "gap between stripes", minimum=0),
    Opt("fg", "level", MAX_LEVEL, "stripe level"),
    Opt("bg", "level", 0, "gap level"),
)
def _stripes(opts, cols):
    period = opts["width"] + opts["gap"]
    axis = {
        "vertical": lambda col, row: col,
        "horizontal": lambda col, row: row,
        "diagonal": lambda col, row: col + row,
        "anti-diagonal": lambda col, row: col - row + ROWS,
    }[opts["orientation"]]

    def cell(col, row):
        return opts["fg"] if axis(col, row) % period < opts["width"] else opts["bg"]

    return cell


@register(
    "diamonds",
    "row of diamonds, darker at the centre",
    Opt("gap", "int", 1, "empty columns between diamonds", minimum=0),
    Opt("invert", "bool", False, "darker at the edges"),
)
def _diamonds(opts, cols):
    period = ROWS + opts["gap"]
    center = ROWS // 2

    def cell(col, row):
        x = col % period
        if x >= ROWS:
            return 0
        distance = abs(x - center) + abs(row - center)
        if distance > center:
            return 0
        return distance + 1 if opts["invert"] else MAX_LEVEL - distance

    return cell


@register(
    "wave",
    "sine wave",
    Opt("period", "int", 13, "wave length in weeks", minimum=2),
    Opt("amplitude", "int", 3, "height in rows (max 3)", minimum=0),
)
def _wave_pattern(opts, cols):
    amplitude = min(opts["amplitude"], 3)

    def cell(col, row):
        center = 3 - amplitude * math.sin(2 * math.pi * col / opts["period"])
        return max(0, MAX_LEVEL - int(abs(row - center) * 2))

    return cell


# --- bitmaps -------------------------------------------------------------


def _place(bitmap: list[list[int]], cols: int, align: str, fill: int = 0, tile_gap: int | None = None) -> CellFn:
    """Position a 7-row bitmap of levels in the grid, optionally repeated."""
    width = max((len(row) for row in bitmap), default=0)
    if width > cols:
        raise PatternError(f"content is {width} columns wide, the period only has {cols}")
    if tile_gap is not None and width:
        period = width + tile_gap
        repeat = (cols + tile_gap) // period
        width = repeat * period - tile_gap
    offset = {"left": 0, "center": (cols - width) // 2, "right": cols - width}[align]

    def cell(col, row):
        x = col - offset
        if not 0 <= x < width:
            return fill
        if tile_gap is not None:
            x %= period
        line = bitmap[row] if row < len(bitmap) else []
        return line[x] if x < len(line) else fill

    return cell


_ALIGN = Opt("align", "choice", "center", "horizontal position", ("center", "left", "right"))


@register(
    "text",
    "text in a 7-pixel font (~8 characters per year, ~4 per half)",
    Opt("text", "str", None, "text to write"),
    Opt("fg", "level", MAX_LEVEL, "text level"),
    Opt("bg", "level", 0, "background level"),
    Opt("spacing", "int", 1, "columns between characters", minimum=0),
    _ALIGN,
)
def _text(opts, cols):
    unsupported = sorted({c for c in opts["text"] if not font.supported(c)})
    if unsupported:
        raise PatternError(f"text: unsupported character(s) {' '.join(unsupported)}")
    pixels = font.render(opts["text"], opts["spacing"])
    bitmap = [[opts["fg"] if lit else opts["bg"] for lit in row] for row in pixels]
    return _place(bitmap, cols, opts["align"], opts["bg"])


# Text-art density: characters from light to dark.
_DENSITY = {**dict.fromkeys(" _", 0), **dict.fromkeys(".,`'", 1), **dict.fromkeys(":-~;", 2)}
_DENSITY.update(dict.fromkeys("+=oxcs*", 3))


def _char_level(char: str) -> int:
    if char.isdigit():
        return min(int(char), MAX_LEVEL)
    return _DENSITY.get(char, MAX_LEVEL)


def load_text_art(path: Path) -> list[list[int]]:
    """7 lines of digits 0-4 or density characters (' ' . : + #)."""
    lines = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
    if len(lines) > ROWS:
        raise PatternError(f"{path}: {len(lines)} lines, maximum is {ROWS}")
    return [[_char_level(c) for c in line.rstrip()] for line in lines]


def load_raster(path: Path, cols: int, fit: str, invert: bool) -> list[list[int]]:
    """Any image Pillow can read, downscaled to 7 rows, dark pixels = high level."""
    try:
        from PIL import Image
    except ImportError:
        raise PatternError("image files need Pillow: pip install pillow (or use a .txt grid)") from None
    with Image.open(path) as source:
        image = source.convert("RGBA")
    width = cols if fit == "stretch" else max(1, min(cols, round(image.width * ROWS / image.height)))
    image = image.resize((width, ROWS), Image.BOX)
    bitmap = []
    for y in range(ROWS):
        line = []
        for x in range(width):
            r, g, b, a = image.getpixel((x, y))
            lightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            darkness = lightness if invert else 1 - lightness
            line.append(0 if a < 128 else round(darkness * MAX_LEVEL))
        bitmap.append(line)
    return bitmap


@register(
    "image",
    "pixel art: .txt grid (7 lines of 0-4 or ' .:+#') or image file (needs Pillow)",
    Opt("file", "str", None, "path to the .txt grid or image"),
    Opt("fit", "choice", "contain", "images: keep ratio or stretch to the period", ("contain", "stretch")),
    Opt("invert", "bool", False, "images: light pixels = dark cells"),
    Opt("tile", "bool", False, "repeat the image across the period"),
    Opt("gap", "int", 2, "tile: columns between copies", minimum=0),
    _ALIGN,
)
def _image(opts, cols):
    path = Path(opts["file"]).expanduser()
    if not path.is_file():
        raise PatternError(f"image: file not found: {path}")
    if path.suffix.lower() == ".txt":
        bitmap = load_text_art(path)
    else:
        bitmap = load_raster(path, cols, opts["fit"], opts["invert"])
    return _place(bitmap, cols, opts["align"], tile_gap=opts["gap"] if opts["tile"] else None)


@register(
    "sprite",
    "built-in pixel art: " + ", ".join(SPRITES),
    Opt("name", "choice", "clawd", "sprite", tuple(SPRITES)),
    Opt("tile", "bool", True, "repeat the sprite across the period"),
    Opt("gap", "int", 2, "tile: columns between copies", minimum=0),
    _ALIGN,
)
def _sprite(opts, cols):
    bitmap = [[_char_level(char) for char in line] for line in SPRITES[opts["name"]]]
    return _place(bitmap, cols, opts["align"], tile_gap=opts["gap"] if opts["tile"] else None)
