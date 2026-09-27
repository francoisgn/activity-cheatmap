"""Periods (full year or half year) and the GitHub calendar grid.

A period is `YYYY` (full year), `YYYY-H1`/`YYYY-S1` (Jan–Jun) or
`YYYY-H2`/`YYYY-S2` (Jul–Dec). Nothing finer on purpose.

Grid: like GitHub, one column per week starting on Sunday, one row per
weekday (row 0 = Sunday … row 6 = Saturday).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

MAX_HALVES = 6  # 3 years of history
MAX_YEARS_BACK = 3  # earliest allowed year = current year - 3
ROWS = 7

_PERIOD_RE = re.compile(r"^(\d{4})(?:[-_ ]?([HS])([12]))?$", re.IGNORECASE)


class PeriodError(ValueError):
    pass


@dataclass(frozen=True)
class Period:
    label: str
    start: date
    end: date

    @property
    def halves(self) -> int:
        return 2 if (self.start.month, self.end.month) == (1, 12) else 1

    @property
    def origin(self) -> date:
        """Sunday on or before the start date: column 0 of the grid."""
        return self.start - timedelta(days=(self.start.weekday() + 1) % 7)

    @property
    def cols(self) -> int:
        return (self.end - self.origin).days // 7 + 1

    def cell(self, day: date) -> tuple[int, int]:
        """(col, row) of a date in this period's grid."""
        delta = (day - self.origin).days
        return delta // 7, delta % 7

    def days(self, until: date | None = None):
        """Dates of the period, optionally clipped to `until` (inclusive)."""
        last = min(self.end, until) if until else self.end
        day = self.start
        while day <= last:
            yield day
            day += timedelta(days=1)


def parse_period(text) -> Period:
    raw = str(text).strip()
    match = _PERIOD_RE.match(raw)
    if not match:
        raise PeriodError(f"invalid period '{raw}' (expected YYYY, YYYY-H1 or YYYY-H2)")
    year = int(match.group(1))
    half = match.group(3)
    if half is None:
        return Period(str(year), date(year, 1, 1), date(year, 12, 31))
    if half == "1":
        return Period(f"{year}-H1", date(year, 1, 1), date(year, 6, 30))
    return Period(f"{year}-H2", date(year, 7, 1), date(year, 12, 31))


def validate_periods(periods: list[Period], today: date) -> list[str]:
    """Raise PeriodError on invalid sets, return warnings otherwise."""
    warnings = []
    if not periods:
        raise PeriodError("no period given")
    earliest = today.year - MAX_YEARS_BACK
    ordered = sorted(periods, key=lambda p: p.start)
    for period in ordered:
        if period.start.year < earliest:
            raise PeriodError(f"{period.label}: too old, earliest allowed year is {earliest}")
        if period.start > today:
            raise PeriodError(f"{period.label}: starts in the future")
        if period.end > today:
            warnings.append(f"{period.label}: clipped to today ({today.isoformat()})")
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if cur.start <= prev.end:
            raise PeriodError(f"{prev.label} and {cur.label} overlap")
    total = sum(p.halves for p in ordered)
    if total > MAX_HALVES:
        raise PeriodError(f"{total / 2:g} years requested, maximum is {MAX_HALVES // 2} years")
    return warnings
