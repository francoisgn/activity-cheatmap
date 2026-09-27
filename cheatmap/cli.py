"""Command line entry point."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from . import __version__, config, github, gitops, patterns, render, ui
from .periods import PeriodError
from .plan import DEFAULT_MESSAGE, DEFAULT_SCALE, MAX_SCALE, Layout, Plan, PlanError, Segment, compute

DEFAULT_BATCH = 1000
DEFAULT_DELAY = 2.0
PUSH_ESTIMATE = 3.0  # rough seconds per push, for the ETA

EPILOG = """\
without arguments, an interactive menu starts.

examples:
  %(prog)s --period 2025 --pattern gradient-diag -o direction=up-right -o cycles=4 --dry-run
  %(prog)s --period 2024 --period 2025 --pattern weekly -o levels=1,2,3,4,4,4,0 --skip weekends
  %(prog)s --period 2026-H1 --pattern text -o text=HELLO --save-config hello.yaml --dry-run
  %(prog)s --config hello.yaml --compare octocat --dry-run
  %(prog)s --config hello.yaml --remote git@github.com:octocat/cheatmap-output.git
"""


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cheatmap",
        description="Draw patterns on your GitHub contribution graph with backdated commits.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--list-patterns", action="store_true", help="list patterns and their options")
    parser.add_argument("-m", "--menu", action="store_true", help="interactive menu (default without arguments)")

    plan = parser.add_argument_group("plan (either a YAML file or pattern options)")
    plan.add_argument("-c", "--config", type=Path, help="YAML plan (needs PyYAML)")
    plan.add_argument("-p", "--period", action="append", help="YYYY, YYYY-H1 or YYYY-H2 (repeatable)")
    plan.add_argument("-P", "--pattern", help="pattern name, see --list-patterns")
    plan.add_argument("-o", "--opt", action="append", default=[], metavar="KEY=VALUE", help="pattern option")
    plan.add_argument("--skip", action="append", help="days without commits: mon..sun, weekdays, weekends")
    plan.add_argument("--scale", type=int, help=f"commits per level (1-{MAX_SCALE}, default {DEFAULT_SCALE})")
    plan.add_argument("--message", help=f'commit message (default "{DEFAULT_MESSAGE}")')
    plan.add_argument("--save-config", type=Path, metavar="FILE", help="write the plan as YAML")

    preview = parser.add_argument_group("preview")
    preview.add_argument("-n", "--dry-run", action="store_true", help="preview only, create and push nothing")
    preview.add_argument("--compare", metavar="USER", help="show the current graph of USER before the plan")
    preview.add_argument(
        "--user",
        metavar="LOGIN",
        help="GitHub login, to check the account creation date (default: from --compare or the email)",
    )
    preview.add_argument("--no-preview", action="store_true", help="do not draw the graph (scripts)")

    push = parser.add_argument_group("generation and push")
    push.add_argument("-r", "--remote", help="empty GitHub repository receiving the commits")
    push.add_argument("--workdir", type=Path, help="local output repository (default: out/<repo>)")
    push.add_argument("--branch", default="main", help="branch to push (default: main)")
    push.add_argument("--name", help="commit author name (default: git config user.name)")
    push.add_argument("--email", help="commit author email, must be on your GitHub account")
    push.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH, help=f"commits per push (default {DEFAULT_BATCH})"
    )
    push.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY, help=f"seconds between pushes (default {DEFAULT_DELAY:g})"
    )
    push.add_argument("--force", action="store_true", help="replace the history of a non-empty remote")
    push.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation with --force")
    return parser.parse_args(argv)


def list_patterns() -> None:
    for pattern in patterns.PATTERNS.values():
        print(f"{ui.paint(ui.BOLD, pattern.name)}  {ui.dim(pattern.help)}")
        for opt in pattern.opts:
            values = "|".join(opt.choices) if opt.choices else opt.kind
            default = "required" if opt.default is None else f"default {config._scalar(opt.default)}"
            print(f"    {opt.name:<12} {values:<42} {opt.help} {ui.dim('(' + default + ')')}")


def parse_opts(items: list[str]) -> dict:
    options = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise PlanError(f"invalid option '{item}' (expected KEY=VALUE)")
        options[key.strip()] = value
    return options


def build_plan(args: argparse.Namespace) -> Plan:
    cli_plan = args.period or args.pattern or args.opt or args.skip
    if args.config:
        if cli_plan:
            raise PlanError("--config cannot be combined with --period/--pattern/--opt/--skip")
        plan = config.load(args.config)
    else:
        if not args.period or not args.pattern:
            raise PlanError("give --config FILE, or --period and --pattern")
        segment = Segment(args.period, args.pattern, parse_opts(args.opt), args.skip or [])
        plan = Plan([segment])
    if args.scale is not None:
        plan.scale = args.scale
    if args.message is not None:
        plan.message = args.message
    return plan


def show_preview(layout: Layout, before: dict | None, today: date) -> None:
    for item in layout.periods:
        period = item.period
        commits = sum(level * layout.scale for level in item.levels.values())
        print()
        if before is not None:
            current = {day: level for day, level in before.items() if period.start <= day <= min(period.end, today)}
            print(
                "\n".join(
                    render.grid(
                        period,
                        current,
                        ui.paint(ui.BOLD, f"{period.label}  before") + ui.dim("  (current GitHub graph)"),
                    )
                )
            )
            print()
        title = ui.paint(ui.BOLD, f"{period.label}  after") + ui.dim(
            f"  ({commits} commits, existing activity ignored)"
        )
        print("\n".join(render.grid(period, item.levels, title)))
    print()
    print(render.legend())
    print()


def git_identity(args: argparse.Namespace) -> tuple[str, str]:
    def from_git(key: str) -> str:
        result = subprocess.run(["git", "config", key], capture_output=True, text=True)
        return result.stdout.strip()

    name = args.name or from_git("user.name")
    email = args.email or from_git("user.email")
    if not name or not email:
        raise PlanError("commit identity unknown: set --name and --email (or git config user.name/user.email)")
    return name, email


def account_start(args: argparse.Namespace) -> date | None:
    """Creation date of the GitHub account, or None (with a warning) if unknown."""
    login = args.user or args.compare
    if not login:
        email = args.email or subprocess.run(["git", "config", "user.email"], capture_output=True, text=True).stdout
        login = github.login_from_email(email)
    if not login:
        ui.warn("GitHub account unknown (--user): contributions dated before its creation will not show")
        return None
    try:
        return github.account_created(login)
    except github.FetchError as error:
        ui.warn(f"{error}: check that the account existed for all periods")
        return None


def repo_name(remote: str) -> str:
    name = re.split(r"[/:]", remote.rstrip("/"))[-1]
    return re.sub(r"\.git$", "", name) or "output"


def confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        raise PlanError("confirmation needs a terminal, add --yes to skip it")
    return input(f"{ui.paint(ui.YELLOW, 'confirm')} {question} [type yes] ").strip().lower() == "yes"


def run(args: argparse.Namespace, argv_empty: bool = False) -> int:
    if args.list_patterns:
        list_patterns()
        return 0
    if args.menu or argv_empty:
        from .menu import main_menu

        return main_menu()

    plan = build_plan(args)
    today = date.today()
    layout, warnings = compute(plan, today, account_start(args))
    for message in warnings:
        ui.warn(message)

    if args.save_config:
        config.save(plan, args.save_config)
        ui.ok(f"plan saved to {args.save_config}")

    before = None
    if args.compare:
        years = sorted({day.year for item in layout.periods for day in item.levels})
        try:
            with ui.spin(f"reading github.com/{args.compare} ({len(years)} year(s))"):
                before = github.fetch_levels(args.compare, years)
        except github.FetchError as error:
            ui.warn(f"{error}, showing the plan only")

    if not args.no_preview:
        show_preview(layout, before, today)
    pushes = -(-layout.commits // max(args.batch_size, 1))
    ui.info(
        f"{len(layout.periods)} period(s), {layout.active_days} active days, "
        f"{layout.commits} commits (scale {plan.scale}), {pushes} push(es)"
    )

    if args.dry_run:
        ui.info("dry run: nothing created, nothing pushed")
        return 0
    if not args.remote:
        if args.save_config:
            return 0
        raise PlanError("--remote is required (or use --dry-run)")
    if args.batch_size < 1 or args.delay < 0:
        raise PlanError("--batch-size must be >= 1 and --delay >= 0")
    if layout.commits == 0:
        ui.warn("the plan has no commit, nothing to push")
        return 0

    name, email = git_identity(args)
    if not email.endswith("@users.noreply.github.com"):
        ui.warn(f"commits will be authored by {email}: it must be a verified email of your GitHub account")

    with ui.spin(f"checking {args.remote}"):
        branches = gitops.remote_branches(args.remote)
    if branches:
        if not args.force:
            raise PlanError(f"remote is not empty ({', '.join(branches)}), use --force to replace '{args.branch}'")
        others = [branch for branch in branches if branch != args.branch]
        if others:
            ui.warn(f"other branches are kept on the remote: {', '.join(others)}")
        question = f"force-push {layout.commits} commits to {args.remote} ({args.branch}), replacing its history?"
        if not args.yes and not confirm(question):
            ui.warn("aborted, nothing pushed")
            return 1

    workdir = args.workdir or Path("out") / repo_name(args.remote)
    with ui.spin(f"creating {layout.commits} commits in {workdir}") as spinner:
        gitops.prepare_workdir(workdir)
        gitops.build(workdir, layout.schedule(), name, email, plan.message, args.branch)
        spinner.detail = f"{layout.active_days} days"

    eta = pushes * (args.delay + PUSH_ESTIMATE)
    ui.info(f"pushing in {pushes} batch(es) of {args.batch_size} commits, ~{eta:.0f}s")
    with ui.spin("pushing") as spinner:

        def progress(number: int, total: int, commits: int) -> None:
            spinner.update(
                f"push {number}/{total} - {commits * 100 // layout.commits}% ({commits}/{layout.commits} commits)"
            )

        done = gitops.push(workdir, args.remote, args.branch, args.batch_size, args.delay, args.force, progress)
        spinner.update(f"pushed {layout.commits} commits to {args.remote}")
        spinner.detail = f"{done} push(es)"
    ui.info("GitHub can take a few minutes to update the graph")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    try:
        return run(args, argv_empty=not argv)
    except gitops.GitError as error:
        hint = gitops.explain(str(error))
        ui.ko(hint or str(error))
        if hint:
            detail = str(error).strip().splitlines()[0] if str(error).strip() else ""
            print(ui.dim(f"        git: {detail}"), file=sys.stderr)
        return 1
    except (PlanError, PeriodError, patterns.PatternError) as error:
        ui.ko(str(error))
        return 1
    except KeyboardInterrupt:
        ui.warn("interrupted")
        return 130
