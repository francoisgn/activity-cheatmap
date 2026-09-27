"""Terminal preview of a period, GitHub-style (weeks in columns, Sunday on top)."""

from __future__ import annotations

import shutil
from datetime import date

from .periods import ROWS, Period
from .ui import color_enabled

# 256-colour approximations of GitHub's dark theme greens.
_COLORS = (237, 22, 28, 34, 77)
_PLAIN = ("·", "░", "▒", "▓", "█")
_ROW_LABELS = ("", "Mon", "", "Wed", "", "Fri", "")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_GUTTER = 4


def _cell(level: int | None, color: bool) -> str:
    if level is None:
        return " "
    if color:
        return f"\033[38;5;{_COLORS[level]}m■\033[0m"
    return _PLAIN[level]


def _cell_width(period: Period) -> int:
    """2 characters per cell when the terminal is wide enough, else 1."""
    columns = shutil.get_terminal_size((120, 40)).columns
    return 2 if _GUTTER + period.cols * 2 <= columns else 1


def grid(period: Period, levels: dict[date, int], title: str) -> list[str]:
    color = color_enabled()
    width = _cell_width(period)
    pad = " " * (width - 1)
    lines = [title]

    months = [" "] * (period.cols * width + 3)
    for month in range(period.start.month, period.end.month + 1):
        col = period.cell(date(period.start.year, month, 1))[0] * width
        if all(char == " " for char in months[max(0, col - 1) : col + 3]):
            months[col : col + 3] = _MONTHS[month - 1]
    lines.append(" " * _GUTTER + "".join(months).rstrip())

    cells = [[None] * period.cols for _ in range(ROWS)]
    for day, level in levels.items():
        if period.start <= day <= period.end:
            col, row = period.cell(day)
            cells[row][col] = level
    for row in range(ROWS):
        body = "".join(_cell(level, color) + pad for level in cells[row])
        lines.append(f"{_ROW_LABELS[row]:<{_GUTTER}}{body}".rstrip())
    return lines


def legend() -> str:
    color = color_enabled()
    return " " * _GUTTER + "Less " + " ".join(_cell(level, color) for level in range(5)) + " More"
