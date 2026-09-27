"""Interactive menu: pattern gallery, random patterns and a step-by-step generator.

Every action runs the regular command line (`cli.main`) and shows the
equivalent command, so anything done here can be scripted.
"""

from __future__ import annotations

import random
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import art, cli, config, github, patterns, ui
from .periods import FIRST_YEAR, PeriodError, parse_period, validate_periods
from .plan import DEFAULT_SCALE, MAX_SCALE, Plan, PlanError, Segment, parse_skip


class Back(Exception):
    pass


class Quit(Exception):
    pass


# --- input helpers -------------------------------------------------------


def _read(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        raise Quit from None


def ask(question: str, default: str = "") -> str:
    """Free text. Enter keeps the default, '<' goes back."""
    suffix = ui.dim(f" [{default}]") if default else ""
    answer = _read(f"{ui.paint(ui.BLUE, '?')} {question}{suffix} ").strip()
    if answer == "<":
        raise Back
    return answer or default


def confirm(question: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        answer = ask(f"{question} ({hint})").lower()
        if not answer:
            return default
        if answer in ("y", "yes", "o", "oui"):
            return True
        if answer in ("n", "no", "non"):
            return False


def _heading(title: str) -> None:
    print()
    print(ui.paint(ui.BOLD, title))


def choose(title: str, items: list[tuple[str, str]], back: str | None = "back") -> int:
    """Numbered menu, returns the 0-based index. 'b' raises Back (if allowed), 'q' raises Quit."""
    _heading(title)
    for number, (label, description) in enumerate(items, 1):
        print(f"  {ui.paint(ui.GREEN, f'{number:>2}')}) {label:<28} {ui.dim(description)}")
    back_hint = f"{ui.paint(ui.YELLOW, 'b')}) {back}    " if back else ""
    print(f"   {back_hint}{ui.paint(ui.YELLOW, 'q')}) quit")
    while True:
        answer = _read(f"{ui.paint(ui.BLUE, '>')} ").strip().lower()
        if back and answer in ("b", "<"):
            raise Back
        if answer == "q":
            raise Quit
        if answer.isdigit() and 1 <= int(answer) <= len(items):
            return int(answer) - 1
        ui.warn(f"type a number between 1 and {len(items)}, b or q")


def parse_selection(answer: str, count: int) -> list[int]:
    """'1,3' / '1-3' / 'all' -> sorted 0-based indexes."""
    if answer.strip().lower() == "all":
        return list(range(count))
    picked: set[int] = set()
    for part in answer.replace(" ", "").split(","):
        match = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not match:
            raise ValueError(part)
        first, last = int(match.group(1)), int(match.group(2) or match.group(1))
        if not 1 <= first <= last <= count:
            raise ValueError(part)
        picked.update(range(first - 1, last))
    return sorted(picked)


def choose_many(title: str, items: list[tuple[str, str]]) -> list[int]:
    _heading(title)
    for number, (label, description) in enumerate(items, 1):
        print(f"  {ui.paint(ui.GREEN, f'{number:>2}')}) {label:<28} {ui.dim(description)}")
    while True:
        answer = ask("pick one or more (e.g. 1,3 or 2-4), '<' to go back")
        try:
            picked = parse_selection(answer, len(items))
        except ValueError:
            picked = []
        if picked:
            return picked
        ui.warn("invalid selection")


def pause() -> None:
    _read(ui.dim("  press Enter to continue "))


# --- state ---------------------------------------------------------------


@dataclass
class State:
    pattern: str = ""
    options: dict = field(default_factory=dict)  # only values that differ from the defaults
    periods: list[str] = field(default_factory=list)
    skip: list[str] = field(default_factory=list)
    scale: int = DEFAULT_SCALE
    compare: str = ""

    def plan(self) -> Plan:
        return Plan([Segment(self.periods, self.pattern, self.options, self.skip)], scale=self.scale)

    def argv(self, *extra: str) -> list[str]:
        argv = []
        for period in self.periods:
            argv += ["-p", period]
        argv += ["-P", self.pattern]
        for key, value in self.options.items():
            argv += ["-o", f"{key}={option_text(value)}"]
        if self.skip:
            argv += ["--skip", ",".join(self.skip)]
        if self.scale != DEFAULT_SCALE:
            argv += ["--scale", str(self.scale)]
        return argv + list(extra)


def option_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def non_default(name: str, options: dict) -> dict:
    """Keep only the options that differ from the pattern defaults."""
    defaults = {opt.name: opt.default for opt in patterns.PATTERNS[name].opts}
    return {key: value for key, value in options.items() if value != defaults.get(key)}


def command(argv: list[str]) -> str:
    return "python3 -m cheatmap " + shlex.join(argv)


def run_cli(argv: list[str]) -> int:
    print(ui.dim("  $ " + command(argv)))
    return cli.main(argv)


def github_user() -> str:
    """GitHub login guessed from a noreply commit email, if any."""
    email = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True).stdout
    return github.login_from_email(email)


def account_start() -> date | None:
    """Creation date of the user's GitHub account, None if unknown (cached per run)."""
    login = github_user()
    if not login:
        return None
    try:
        return github.account_created(login)
    except github.FetchError:
        return None


# --- examples ------------------------------------------------------------

EXAMPLES: list[tuple[str, str, dict, list[str]]] = [
    ("Diagonal waves", "gradient-diag", {"direction": "up-right", "cycles": 4, "mirror": True}, []),
    ("Sunrise", "gradient-h", {"direction": "right"}, []),
    ("Mirror fade", "gradient-h", {"cycles": 2, "mirror": True}, []),
    ("Rain", "gradient-v", {"direction": "down"}, []),
    ("Weekly staircase", "weekly", {"levels": [1, 2, 3, 4, 4, 4, 0]}, []),
    ("Office hours", "gradient-diag", {"direction": "down-left", "cycles": 3, "min": 1}, ["weekends"]),
    ("Checkerboard", "checker", {}, []),
    ("Candy stripes", "stripes", {"orientation": "diagonal", "width": 2, "gap": 2}, []),
    ("Diamonds", "diamonds", {}, []),
    ("Sine wave", "wave", {}, []),
    ("Hello", "text", {"text": "HELLO"}, []),
    ("Clawd parade", "sprite", {"name": "clawd"}, []),
    ("Space invaders", "sprite", {"name": "invader"}, []),
    ("Ghosts", "sprite", {"name": "ghost", "gap": 3}, []),
    ("Hearts", "sprite", {"name": "heart", "gap": 1}, []),
]

_WORDS = ("HELLO", "LGTM", "SHIP IT", "CLAWD", "CODE", "HACK", "GIT PUSH", "YOLO", "♥ GIT ♥")
_INT_RANGES = {"cycles": (1, 6), "size": (1, 3), "width": (1, 3), "gap": (0, 3), "period": (6, 20), "amplitude": (1, 3)}


def random_pattern(rng: random.Random) -> tuple[str, dict, list[str]]:
    name = rng.choice([name for name in patterns.PATTERNS if name != "image"])
    options = {}
    for opt in patterns.PATTERNS[name].opts:
        if opt.kind == "choice":
            options[opt.name] = rng.choice(opt.choices)
        elif opt.kind == "bool":
            options[opt.name] = rng.random() < 0.5
        elif opt.kind == "int":
            low, high = _INT_RANGES.get(opt.name, (opt.minimum, opt.minimum))
            options[opt.name] = rng.randint(max(low, opt.minimum), high)
        elif opt.kind == "levels":
            options[opt.name] = [rng.randint(0, 4) for _ in range(7)]
        elif opt.kind == "level":
            ranges = {"min": (0, 1), "max": (3, 4), "bg": (0, 1), "fg": (3, 4)}
            options[opt.name] = rng.randint(*ranges.get(opt.name, (1, 4)))
        elif opt.name == "text":
            options[opt.name] = rng.choice(_WORDS)
    if name == "text":
        options["spacing"] = 1
    skip = rng.choice([[], [], [], ["weekends"]])
    return name, non_default(name, options), skip


def sample_period(today: date) -> str:
    return str(today.year - 1)


def show_sample(title: str, name: str, options: dict, skip: list[str], today: date) -> State:
    state = State(pattern=name, options=non_default(name, options), periods=[sample_period(today)], skip=skip)
    _heading(f"{title}  {ui.dim('(' + name + ')')}")
    run_cli(state.argv("--dry-run"))
    return state


def gallery(today: date) -> State | None:
    items = [
        (title, f"{name} " + " ".join(f"{k}={option_text(v)}" for k, v in opts.items()))
        for title, name, opts, _ in EXAMPLES
    ]
    items.append(("Show them all", "long output"))
    while True:
        index = choose("1.1  Pattern examples", items)
        if index == len(EXAMPLES):
            for title, name, opts, skip in EXAMPLES:
                show_sample(title, name, opts, skip, today)
            continue
        state = show_sample(*EXAMPLES[index], today)
        try:
            action = choose("What next?", [("Use this pattern", "go to generation"), ("Another example", "")])
        except Back:
            continue
        if action == 0:
            return state


def random_menu(today: date) -> State | None:
    rng = random.Random()
    while True:
        name, options, skip = random_pattern(rng)
        state = show_sample("1.2  Random pattern", name, options, skip, today)
        action = choose("What next?", [("Another one", "roll again"), ("Use this pattern", "go to generation")])
        if action == 1:
            return state


def examples_menu(today: date) -> State | None:
    while True:
        try:
            index = choose("1  Pattern examples", [("Examples", "curated gallery"), ("Random", "surprise me")])
        except Back:
            return None
        try:
            return gallery(today) if index == 0 else random_menu(today)
        except Back:
            continue


# --- generation wizard ---------------------------------------------------


def ask_option(opt: patterns.Opt, current):
    """Prompt one pattern option until the value is valid."""
    while True:
        if opt.kind == "choice":
            items = [(choice, "current" if choice == current else "") for choice in opt.choices]
            return opt.choices[choose(f"{opt.name}: {opt.help}", items)]
        shown = "" if current is None else option_text(current)
        hint = {"level": " (0-4)", "levels": " (7 levels 0-4, Monday first)", "bool": " (true/false)"}.get(opt.kind, "")
        answer = ask(f"{opt.name}: {opt.help}{hint}", shown)
        try:
            return patterns.coerce(opt, answer)
        except patterns.PatternError as error:
            ui.warn(str(error))


def step_pattern(state: State, today: date) -> None:
    while not _pick_pattern(state, today):
        pass


def _pick_pattern(state: State, today: date) -> bool:
    names = list(patterns.PATTERNS)
    items = [(name, patterns.PATTERNS[name].help) for name in names]
    index = choose("2.1  Pattern type", items)
    name = names[index]
    pattern = patterns.PATTERNS[name]
    options = dict(state.options) if name == state.pattern else {}
    required = [opt for opt in pattern.opts if opt.default is None]
    customise = not required and confirm("customise the options?", default=False)
    for opt in pattern.opts:
        if opt.default is None or customise:
            options[opt.name] = ask_option(opt, options.get(opt.name, opt.default))
    try:
        patterns.build(name, options, parse_period(sample_period(today)).cols)
    except patterns.PatternError as error:
        ui.ko(str(error))
        return False
    state.pattern, state.options = name, non_default(name, options)
    return True


def half_starts(today: date, first_year: int = FIRST_YEAR) -> list[date]:
    """Jan 1 / Jul 1 of every half year from `first_year` to the current one."""
    starts = []
    for year in range(first_year, today.year + 1):
        starts += [day for day in (date(year, 1, 1), date(year, 7, 1)) if day <= today]
    return starts


def half_label(start: date) -> str:
    return f"{start.year}-H{1 if start.month == 1 else 2}"


def halves_between(start: date, end: date) -> list[str]:
    """Half-year labels from `start` (Jan 1/Jul 1) to `end` (Jun 30/Dec 31), full years merged."""
    labels = []
    year, half = start.year, 1 if start.month == 1 else 2
    while (year, half) <= (end.year, 1 if end.month == 6 else 2):
        labels.append(f"{year}-H{half}")
        year, half = (year, 2) if half == 1 else (year + 1, 1)
    return merge_halves(labels)


def merge_halves(labels: list[str]) -> list[str]:
    merged = []
    for label in labels:
        if label.endswith("-H2") and merged and merged[-1] == label[:-1] + "1":
            merged[-1] = label[:4]
        else:
            merged.append(label)
    return merged


def step_coverage(state: State, today: date) -> None:
    while not _pick_coverage(state, today):
        pass


def _pick_coverage(state: State, today: date) -> bool:
    mode = choose(
        "2.2  Time coverage",
        [
            ("By year", "full years"),
            ("By semester", "H1 = Jan-Jun, H2 = Jul-Dec"),
            ("Start and end", "from 01/01 or 01/07 to 30/06 or 31/12"),
        ],
    )
    created = account_start()
    first_year = max(FIRST_YEAR, created.year) if created else FIRST_YEAR
    if created:
        print(ui.dim(f"  your GitHub account was created on {created:%d/%m/%Y}: earlier years are not offered"))
    else:
        print(ui.dim(f"  GitHub opened in {FIRST_YEAR}: make sure your account existed for the chosen periods"))
    starts = half_starts(today, first_year)
    years = sorted({day.year for day in starts})
    if mode == 0:
        items = [(str(year), "until today" if year == today.year else "") for year in years]
        periods = [str(years[index]) for index in choose_many("Years", items)]
    elif mode == 1:
        picked = [years[index] for index in choose_many("Years of the semesters", [(str(y), "") for y in years])]
        labels = [half_label(day) for day in starts if day.year in picked]
        items = [(label, "until today" if parse_period(label).end > today else "") for label in labels]
        periods = merge_halves([labels[index] for index in choose_many("Semesters", items)])
    else:
        start_year = years[choose("Start year", [(str(year), "") for year in years])]
        options = [day for day in starts if day.year == start_year]
        start = options[choose("Start date", [(f"{day:%d/%m/%Y}", "") for day in options])]
        end_years = [year for year in years if year >= start.year]
        end_year = end_years[choose("End year", [(str(year), "") for year in end_years])]
        ends = [parse_period(half_label(day)).end for day in starts if day.year == end_year and day >= start]
        items = [(f"{day:%d/%m/%Y}", "clipped to today" if day > today else "") for day in ends]
        periods = halves_between(start, ends[choose("End date", items)])
    try:
        for message in validate_periods([parse_period(period) for period in periods], today, created):
            ui.warn(message)
    except PeriodError as error:
        ui.ko(str(error))
        return False
    state.periods = periods
    ui.ok("periods: " + ", ".join(periods) + ui.dim("  (each period is drawn as its own canvas)"))
    return True


def step_skip(state: State, today: date) -> None:
    index = choose(
        "2.3  Days without commits",
        [
            ("None", "every day follows the pattern"),
            ("Weekends", "no commit on Saturday and Sunday"),
            ("Weekdays", "commits on weekends only"),
            ("Custom days", "e.g. mon,wed or sun"),
        ],
    )
    if index == 3:
        while True:
            answer = ask("days to skip (mon..sun, weekdays, weekends)", ",".join(state.skip))
            try:
                parse_skip(answer)
                break
            except PlanError as error:
                ui.warn(str(error))
        state.skip = [item.strip() for item in answer.split(",") if item.strip()]
    else:
        state.skip = [[], ["weekends"], ["weekdays"]][index]


def step_scale(state: State, today: date) -> None:
    _heading("Intensity")
    print(ui.dim(f"  commits per day = level (0-4) x scale; higher = your real activity shows less (1-{MAX_SCALE})"))
    while True:
        answer = ask("scale", str(state.scale))
        if answer.isdigit() and 1 <= int(answer) <= MAX_SCALE:
            state.scale = int(answer)
            return
        ui.warn(f"type a number between 1 and {MAX_SCALE}")


def step_preview(state: State, today: date) -> str | None:
    """Show the result, then return the next action."""
    _heading("2.4  Preview")
    if not state.compare:
        try:
            state.compare = ask_compare()
        except Back:
            return "skip"  # '<' goes back to the previous step
    extra = ["--dry-run"] + (["--compare", state.compare] if state.compare != "-" else [])
    run_cli(state.argv(*extra))
    actions = [
        ("push", "Push to GitHub", "generate the commits and push them"),
        ("save", "Save as YAML plan", "reuse it later with --config"),
        ("pattern", "Change pattern", state.pattern),
        ("coverage", "Change time coverage", ", ".join(state.periods)),
        ("skip", "Change skipped days", ", ".join(state.skip) or "none"),
        ("scale", "Change intensity", f"scale {state.scale}"),
        ("compare", "Change compared user", state.compare if state.compare != "-" else "none"),
        ("command", "Show the command", "for scripts and power users"),
    ]
    index = choose("What next?", [(label, description) for _, label, description in actions], back="main menu")
    return actions[index][0]


def ask_compare() -> str:
    """'-' for no comparison, else the GitHub login to compare with."""
    if not confirm("show your current GitHub graph next to the result (before / after)?", default=True):
        return "-"
    while True:
        login = ask("GitHub user", github_user())
        if re.fullmatch(r"[A-Za-z0-9-]+", login):
            return login
        ui.warn("type a GitHub login (letters, digits, dashes)")


def step_push(state: State) -> bool:
    _heading("2.5  Push")
    print(ui.dim("  the target repository must ALREADY EXIST on GitHub, this tool does not create it:"))
    print(ui.dim("  create it empty (no README), private is fine: https://github.com/new"))
    print(ui.dim("  or: gh repo create cheatmap-output --private"))
    user = github_user() or "<user>"
    remote = ask("remote URL", f"git@github.com:{user}/cheatmap-output.git")
    force = confirm("if the remote already has commits, replace its history?", default=False)
    extra = ["--remote", remote, "--no-preview"] + (["--force"] if force else [])
    return run_cli(state.argv(*extra)) == 0


def step_save(state: State) -> None:
    path = Path(ask("file", "plan.yaml")).expanduser()
    if path.exists() and not confirm(f"{path} exists, overwrite?"):
        return
    config.save(state.plan(), path)
    ui.ok(f"plan saved to {path}")
    print(ui.dim(f"  $ python3 -m cheatmap --config {shlex.quote(str(path))} --dry-run"))


STEPS = {"pattern": step_pattern, "coverage": step_coverage, "skip": step_skip, "scale": step_scale}
ORDER = ["pattern", "coverage", "skip"]


def wizard(today: date, state: State | None = None) -> None:
    """Pattern -> coverage -> skip -> preview -> push. '<' / 'b' goes one step back."""
    state = state or State()
    if state.pattern:
        state.periods = []  # examples are shown on last year: pick the real coverage
        position = 1
    else:
        position = 0
    while position < len(ORDER):
        try:
            STEPS[ORDER[position]](state, today)
            position += 1
        except Back:
            if position == 0:
                return
            position -= 1
    while True:
        try:
            action = step_preview(state, today)
        except Back:
            return
        try:
            if action == "push":
                if step_push(state):
                    pause()
                    return
            elif action == "save":
                step_save(state)
            elif action == "command":
                _heading("Equivalent commands")
                for extra in (["--dry-run"], ["--remote", "<remote>"], ["--save-config", "plan.yaml", "--dry-run"]):
                    print("  " + command(state.argv(*extra)))
                pause()
            elif action == "compare":
                state.compare = ""
            else:
                STEPS[action](state, today)
        except Back:
            continue


# --- main menu -----------------------------------------------------------


def clear() -> None:
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="")


def main_menu(today: date | None = None) -> int:
    if not sys.stdin.isatty():
        ui.ko("the menu needs a terminal: run with options instead (see --help)")
        return 1
    today = today or date.today()
    try:
        while True:
            clear()
            print(art.banner())
            index = choose(
                "Main menu",
                [
                    ("Pattern examples", "gallery and random patterns"),
                    ("Generate", "step by step: pattern, dates, preview, push"),
                    ("List patterns", "all patterns and options"),
                ],
                back=None,
            )
            if index == 0:
                picked = examples_menu(today)
                if picked:
                    wizard(today, picked)
            elif index == 1:
                wizard(today)
            else:
                cli.list_patterns()
                pause()
    except (Quit, KeyboardInterrupt):
        print()
        ui.info("bye")
        return 0
