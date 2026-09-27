"""Current contribution levels, read from the public profile calendar.

No API, no token: one HTML page per year, with a pause between requests.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from datetime import date

URL = "https://github.com/users/{user}/contributions?from={year}-01-01&to={year}-12-31"
USER_AGENT = "activity-cheatmap (+https://github.com/francoisgn/activity-cheatmap)"
REQUEST_DELAY = 1.5  # seconds between two requests
TIMEOUT = 20

_TD = re.compile(r"<td[^>]*ContributionCalendar-day[^>]*>")
_DATE = re.compile(r'data-date="(\d{4}-\d{2}-\d{2})"')
_LEVEL = re.compile(r'data-level="(\d)"')


class FetchError(RuntimeError):
    pass


def parse(html: str) -> dict[date, int]:
    levels = {}
    for tag in _TD.findall(html):
        day, level = _DATE.search(tag), _LEVEL.search(tag)
        if day and level:
            levels[date.fromisoformat(day.group(1))] = int(level.group(1))
    return levels


def fetch_levels(user: str, years: list[int], delay: float = REQUEST_DELAY) -> dict[date, int]:
    levels: dict[date, int] = {}
    for index, year in enumerate(sorted(set(years))):
        if index:
            time.sleep(delay)
        request = urllib.request.Request(URL.format(user=user, year=year), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                html = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            raise FetchError(f"github.com answered {error.code} for user '{user}' ({year})") from None
        except (urllib.error.URLError, TimeoutError) as error:
            raise FetchError(f"cannot reach github.com: {error}") from None
        year_levels = parse(html)
        if not year_levels:
            raise FetchError(f"no calendar found for user '{user}' ({year})")
        levels.update(year_levels)
    return levels
