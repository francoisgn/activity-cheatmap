# activity-cheatmap

```
        .-~~~-.
       (  ~ ~  )                ) ) )
        '-----'                ( ( (
         |___|                  ) ) )
        ▐▛███▜▌
       ▝▜█████▛▘━━━━━━━━━━━━(__________)
         ▘▘ ▝▝                ^^^^^^

         C L A W D   C O O K I N G
```

Draw patterns on your GitHub contribution graph with backdated commits:
gradients, weekly rhythms, geometric shapes, text and pixel art.
Unlike random fillers, every day's shade is decided by the pattern.

Inspired by [dacappo/github-heatmap](https://github.com/dacappo/github-heatmap), rewritten from scratch.

```
2025  after  (1920 commits, existing activity ignored)          ← the "Clawd parade" example
    Jan     Feb     Mar       Apr     May       Jun     Jul     Aug       Sep     Oct     Nov       Dec
      · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
Mon   █ █ █ █ █ █ █ · · · · █ █ █ █ █ █ █ · · · · █ █ █ █ █ █ █ · · · · █ █ █ █ █ █ █ · · · · █ █ █ █ █ █ █ ·
      █ · █ █ █ · █ · · · · █ · █ █ █ · █ · · · · █ · █ █ █ · █ · · · · █ · █ █ █ · █ · · · · █ · █ █ █ · █ ·
Wed █ █ █ █ █ █ █ █ █ · · █ █ █ █ █ █ █ █ █ · · █ █ █ █ █ █ █ █ █ · · █ █ █ █ █ █ █ █ █ · · █ █ █ █ █ █ █ █ █
    · █ █ █ █ █ █ █ · · · · █ █ █ █ █ █ █ · · · · █ █ █ █ █ █ █ · · · · █ █ █ █ █ █ █ · · · · █ █ █ █ █ █ █
Fri · █ · █ · █ · █ · · · · █ · █ · █ · █ · · · · █ · █ · █ · █ · · · · █ · █ · █ · █ · · · · █ · █ · █ · █
    · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
```

## How it works

1. You describe a **plan**: periods + pattern, from the menu, CLI options or a YAML file.
2. The result is previewed in the terminal, optionally next to your current
   graph (before / after).
3. The commits are created **locally** in a separate repository (`out/<repo>`)
   with `git fast-import`: a few seconds for thousands of commits, no network.
4. The history is pushed to **your own empty repository**, in throttled batches.

The tool (this repo) and the fake commits (your output repo) stay separate:
clone this repo, create an empty repo on GitHub, push to it.

## Requirements

- Python 3.10+ and git 2.28+, no dependency for the core.
- Optional: `pip install pyyaml` to read YAML plans, `pip install pillow` for image files.
  Or `pip install ".[all]"`, which also installs a `cheatmap` command.

## Quick start: the menu

```sh
git clone git@github.com:francoisgn/activity-cheatmap.git && cd activity-cheatmap
python3 -m cheatmap
```

Without arguments, an interactive menu starts:

```
Main menu
├── 1  Pattern examples
│   ├── 1.1  Examples         curated gallery, previewed on last year → "use this pattern"
│   └── 1.2  Random           roll random patterns until one fits    → "use this pattern"
├── 2  Generate
│   ├── 2.1  Pattern type     + its options (text, direction, levels…)
│   ├── 2.2  Time coverage    by year, by semester, or start (01/01, 01/07) → end (30/06, 31/12)
│   ├── 2.3  Days to skip     none, weekends, weekdays, custom days
│   ├── 2.4  Preview          before (your current graph) / after, then:
│   │                         push · save as YAML · change any step · show the command
│   └── 2.5  Push             remote URL, replace or not, throttled push with progress
└── 3  List patterns
```

Navigation: type the number, `b` to go back, `q` to quit. In text prompts,
Enter keeps the value in brackets and `<` goes back. Every preview and push
prints the equivalent command line, and *Show the command* gives it ready to
copy into a script.

## Command line (scripts, power users)

Everything the menu does is a plain command:

```sh
# 1. preview
python3 -m cheatmap --period 2025 --pattern gradient-diag -o direction=up-right -o cycles=4 --dry-run

# 2. compare with your current graph (reads your public profile page)
python3 -m cheatmap --period 2025 --pattern gradient-diag -o direction=up-right -o cycles=4 --dry-run --compare <user>

# 3. create an EMPTY repository on GitHub, then generate and push
python3 -m cheatmap --period 2025 --pattern gradient-diag -o direction=up-right -o cycles=4 \
  --remote git@github.com:<user>/cheatmap-output.git
```

| Option | Use |
|---|---|
| `-p, --period` | `YYYY`, `YYYY-H1`, `YYYY-H2`, repeatable |
| `-P, --pattern` / `-o key=value` | pattern and its options |
| `--skip` | days without commits |
| `--scale` | commits per level (1-10, default 3) |
| `-c, --config` / `--save-config` | read / write a YAML plan |
| `-n, --dry-run` | preview only |
| `--compare USER` | show the current graph of USER before the plan |
| `--no-preview` | no graph in the output (scripts) |
| `-r, --remote` | output repository to push to |
| `--force` / `-y, --yes` | replace a non-empty remote / without the confirmation |
| `--batch-size`, `--delay` | push throttling (default 1000 commits, 2s) |
| `--name`, `--email`, `--branch`, `--workdir`, `--message` | commit identity and output details |
| `-m, --menu` | start the menu explicitly |

`python3 -m cheatmap --help` has the full list.

## Periods

Full years or half years only, to keep things simple:

| Period | Dates |
|---|---|
| `2025` | Jan 1 – Dec 31 |
| `2025-H1` (or `S1`) | Jan 1 – Jun 30 |
| `2025-H2` (or `S2`) | Jul 1 – Dec 31 |

- Up to **3 years** in total (6 halves), from January 1st of *current year − 3*.
- Periods cannot overlap. The current period is clipped to today; future periods are refused.
- Each period is its own canvas: patterns are computed on the period's grid
  (one column per week starting on Sunday, one row per weekday), like the yearly
  views of your GitHub profile.

## Levels and commits

GitHub shows **5 shades**: empty + 4 greens. Patterns work with **levels 0 to 4**,
and each day gets `level × scale` commits (`--scale`, default 3, max 10).

GitHub computes the shades relatively to your own activity, not from fixed
counts. Keeping the 1:2:3:4 ratio and using every level in a period gives the
expected shades. Your real contributions are **ignored** by the plan and add up
on top of it: a higher `--scale` makes them less visible.

## Patterns

`python3 -m cheatmap --list-patterns` lists everything with defaults.
Options are passed with `-o key=value`.

| Pattern | Description | Main options |
|---|---|---|
| `gradient-h` | horizontal fade | `direction=right\|left`, `cycles`, `mirror`, `min`, `max` |
| `gradient-v` | vertical fade | `direction=down\|up`, `cycles`, `mirror`, `min`, `max` |
| `gradient-diag` | diagonal fade | `direction=down-right\|down-left\|up-right\|up-left`, `cycles`, `mirror`, `min`, `max` |
| `weekly` | one level per weekday | `levels=1,2,3,4,4,4,0` (Monday first) |
| `solid` | same level everywhere | `level` |
| `checker` | checkerboard | `size`, `fg`, `bg` |
| `stripes` | stripes | `orientation=vertical\|horizontal\|diagonal\|anti-diagonal`, `width`, `gap`, `fg`, `bg` |
| `diamonds` | row of diamonds | `gap`, `invert` |
| `wave` | sine wave | `period`, `amplitude` |
| `text` | 7-pixel font (A–Z, 0–9, `! ? . , : ' - + / < > = # ♥`) | `text`, `fg`, `bg`, `spacing`, `align` |
| `image` | pixel art from a file | `file`, `tile`, `gap`, `fit`, `invert`, `align` |
| `sprite` | built-in pixel art: `clawd`, `invader`, `ghost`, `heart` | `name`, `tile`, `gap`, `align` |

`direction` is the side that gets darker. `cycles` repeats the gradient,
`mirror=true` makes it go light → dark → light.

A year holds about 8 characters of text, a half year about 4.

**Pixel art**: a `.txt` file of up to 7 lines, with digits `0`–`4` or density
characters (space = empty, `.` light, `:` medium, `+` dark, `#` darkest), see
[examples/invader.txt](examples/invader.txt). Any other image format (PNG, JPEG…)
needs Pillow and is shrunk to 7 pixels high, dark pixels = dark cells: simple,
high-contrast images work best.

## Days without commits

`--skip` empties days whatever the pattern says: `mon` … `sun`, `weekdays`,
`weekends`, comma-separated or repeated (`--skip mon,wed --skip weekends`).

## YAML plans

Several patterns in one run, one per segment. Generate a file from the CLI
with `--save-config`, edit it, run it with `--config`:

```sh
python3 -m cheatmap -p 2025 -P text -o "text=HI THERE" --save-config plan.yaml --dry-run
python3 -m cheatmap --config plan.yaml --dry-run
```

```yaml
scale: 3
message: "Update activity"
segments:
  - periods: ["2024"]
    pattern: gradient-diag
    options:
      direction: "up-right"
      cycles: 4
      mirror: true
  - periods: ["2025"]
    pattern: text
    options:
      text: "HI THERE"
  - periods: ["2026-H1"]
    pattern: weekly
    options:
      levels: [1, 2, 3, 4, 4, 0, 0]
    skip: ["weekends"]
```

Image paths are relative to the YAML file. See [examples/](examples/).

## Being gentle with GitHub

- Commits are built locally; GitHub only sees one `git ls-remote` and the pushes.
- History is pushed oldest first in batches of `--batch-size` commits (default 1000),
  with `--delay` seconds between pushes (default 2s). About 1 minute for 3 years.
- A failed push is retried up to 3 times with a doubling delay (max 60s), and the
  slower pace is kept for the rest of the run. Authentication and rejection errors stop immediately.
- `--compare` reads your public profile page (one request per year, 1.5s apart), no API.
- Hard limit of 25,000 commits per run.

## Regenerating

The remote must be empty. To replace a previous drawing, add `--force`: you
are asked to type `yes` (`--yes` skips the question) before the history of the
branch is force-pushed. Other branches on the remote are left untouched.

The local output (`out/<repo>`, or `--workdir`) is rebuilt on each run; the tool
refuses to delete a directory it did not create.

## Making it show up

- The commit email must be a verified email of your GitHub account. The
  default is `git config user.email`; the `<id>+<user>@users.noreply.github.com`
  address works. Override it with `--email`.
- Commits count on the default branch only (`--branch`, default `main`).
- For a private output repository, enable *Private contributions* in your profile settings.
- GitHub can take a few minutes to refresh the graph.

## Development

```sh
python3 -m unittest discover -s tests
pre-commit install      # ruff, YAML/TOML checks and unit tests on each commit
```

## Support

If this made your graph smile, you can buy me a coffee:

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-francoisgn-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/francoisgn)
