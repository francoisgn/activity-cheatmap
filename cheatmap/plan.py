"""Plan: which pattern on which periods, and the resulting commits per day.

Real (existing) contributions are ignored: the plan alone decides the levels.
Commits per day = level x scale, so level ratios stay 1:2:3:4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import patterns
from .periods import Period, parse_period, validate_periods

DEFAULT_SCALE = 3
MAX_SCALE = 10
MAX_COMMITS = 25_000
DEFAULT_MESSAGE = "Update activity"

_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_FULL = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SKIP_WORDS = {
    **{name: {index} for index, name in enumerate(_DAYS)},
    **{name: {index} for index, name in enumerate(_FULL)},
    "weekdays": set(range(5)),
    "weekends": {5, 6},
}


class PlanError(ValueError):
    pass


def split_list(values) -> list[str]:
    """['a,b', 'c'] or 'a, b' -> ['a', 'b', 'c']."""
    if values is None:
        return []
    if isinstance(values, (str, int)):
        values = [values]
    return [item.strip() for value in values for item in str(value).split(",") if item.strip()]


def parse_skip(values) -> set[int]:
    """Weekday names/groups -> set of date.weekday() numbers (Monday = 0)."""
    days: set[int] = set()
    for word in split_list(values):
        if word.lower() not in SKIP_WORDS:
            raise PlanError(f"invalid skip '{word}' (mon..sun, weekdays, weekends)")
        days |= SKIP_WORDS[word.lower()]
    return days


@dataclass
class Segment:
    periods: list[str]
    pattern: str
    options: dict = field(default_factory=dict)
    skip: list[str] = field(default_factory=list)


@dataclass
class Plan:
    segments: list[Segment]
    scale: int = DEFAULT_SCALE
    message: str = DEFAULT_MESSAGE


@dataclass
class PeriodLevels:
    period: Period
    levels: dict[date, int]  # only days up to today


@dataclass
class Layout:
    periods: list[PeriodLevels]
    scale: int

    def schedule(self) -> list[tuple[date, int]]:
        """(day, commits) for every day with at least one commit, oldest first."""
        days = [(day, level * self.scale) for item in self.periods for day, level in item.levels.items() if level]
        return sorted(days)

    @property
    def commits(self) -> int:
        return sum(count for _, count in self.schedule())

    @property
    def active_days(self) -> int:
        return len(self.schedule())


def compute(plan: Plan, today: date) -> tuple[Layout, list[str]]:
    if not 1 <= plan.scale <= MAX_SCALE:
        raise PlanError(f"scale must be between 1 and {MAX_SCALE}")
    if not plan.segments:
        raise PlanError("nothing to draw: no segment")
    items: list[PeriodLevels] = []
    for segment in plan.segments:
        skip = parse_skip(segment.skip)
        options = patterns.resolve_options(segment.pattern, segment.options)
        periods = [parse_period(p) for p in split_list(segment.periods)]
        if not periods:
            raise PlanError(f"{segment.pattern}: no period given")
        for period in periods:
            cell = patterns.build(segment.pattern, options, period.cols)
            levels = {}
            for day in period.days(until=today):
                levels[day] = 0 if day.weekday() in skip else cell(*period.cell(day))
            items.append(PeriodLevels(period, levels))
    warnings = validate_periods([item.period for item in items], today)
    items.sort(key=lambda item: item.period.start)
    layout = Layout(items, plan.scale)
    if layout.commits > MAX_COMMITS:
        raise PlanError(f"{layout.commits} commits planned, maximum is {MAX_COMMITS} (lower --scale)")
    return layout, warnings
