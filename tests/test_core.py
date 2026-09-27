import tempfile
import unittest
from datetime import date
from pathlib import Path

from cheatmap import config, font, github, patterns
from cheatmap.periods import PeriodError, parse_period, validate_periods
from cheatmap.plan import Plan, PlanError, Segment, compute, parse_skip

TODAY = date(2026, 9, 27)


class PeriodTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_period("2024").end, date(2024, 12, 31))
        self.assertEqual(parse_period("2024-H1").end, date(2024, 6, 30))
        self.assertEqual(parse_period("2024-s2").start, date(2024, 7, 1))
        self.assertEqual(parse_period(2025).label, "2025")
        for bad in ("2024-H3", "2024-06", "24", "2024-Q1"):
            with self.assertRaises(PeriodError):
                parse_period(bad)

    def test_grid_starts_on_sunday(self):
        period = parse_period("2025")  # 2025-01-01 is a Wednesday
        self.assertEqual(period.origin, date(2024, 12, 29))
        self.assertEqual(period.cell(date(2025, 1, 1)), (0, 3))
        self.assertEqual(period.cols, 53)

    def test_validation(self):
        ok = [parse_period(p) for p in ("2023", "2024", "2025")]
        self.assertEqual(validate_periods(ok, TODAY), [])
        self.assertEqual(len(validate_periods([parse_period("2026")], TODAY)), 1)  # clipped
        for bad in (["2022"], ["2026-H1", "2026"], ["2023", "2024", "2025", "2026-H1"], ["2027"]):
            with self.assertRaises(PeriodError):
                validate_periods([parse_period(p) for p in bad], TODAY)


def levels_of(name, cols=53, **options):
    cell = patterns.build(name, options, cols)
    return [[cell(col, row) for col in range(cols)] for row in range(7)]


class PatternTest(unittest.TestCase):
    def test_gradient_h_covers_all_levels(self):
        row = levels_of("gradient-h")[0]
        self.assertEqual((row[0], row[-1]), (0, 4))
        self.assertEqual(sorted(set(row)), [0, 1, 2, 3, 4])
        self.assertEqual(levels_of("gradient-h", direction="left")[0], row[::-1])

    def test_gradient_v(self):
        grid = levels_of("gradient-v", direction="up")
        self.assertEqual((grid[0][0], grid[6][0]), (4, 0))

    def test_gradient_diag_four_directions(self):
        corners = {"down-right": (6, 52), "down-left": (6, 0), "up-right": (0, 52), "up-left": (0, 0)}
        for direction, (row, col) in corners.items():
            grid = levels_of("gradient-diag", direction=direction)
            self.assertEqual(grid[row][col], 4, direction)
            self.assertEqual(grid[6 - row][52 - col], 0, direction)

    def test_weekly_is_monday_first(self):
        grid = levels_of("weekly", levels="1,2,3,4,0,0,0")
        self.assertEqual([grid[row][0] for row in range(7)], [0, 1, 2, 3, 4, 0, 0])

    def test_text(self):
        grid = levels_of("text", cols=27, text="HI", align="left")
        self.assertEqual(grid[0][:9], [4, 0, 0, 0, 4, 0, 4, 4, 4])
        with self.assertRaises(patterns.PatternError):
            levels_of("text", cols=27, text="HELLO")
        with self.assertRaises(patterns.PatternError):
            levels_of("text", text="€")

    def test_image_text_art(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp) / "art.txt"
            art.write_text("04\n#.\n")
            grid = levels_of("image", cols=10, file=str(art), align="left")
        self.assertEqual([grid[0][:2], grid[1][:2], grid[2][:2]], [[0, 4], [4, 1], [0, 0]])

    def test_option_errors(self):
        for name, options in (("solid", {"level": 5}), ("solid", {"colour": 1}), ("weekly", {"levels": "1,2"})):
            with self.assertRaises(patterns.PatternError):
                patterns.resolve_options(name, options)
        with self.assertRaises(patterns.PatternError):
            patterns.resolve_options("nope", {})

    def test_every_pattern_builds(self):
        required = {"text": {"text": "OK"}}
        for name in patterns.PATTERNS:
            if name != "image":
                for row in levels_of(name, **required.get(name, {})):
                    self.assertTrue(all(0 <= level <= 4 for level in row), name)

    def test_font_glyphs_are_7_rows(self):
        for char, rows in font.GLYPHS.items():
            self.assertEqual(len(rows), 7, char)
            self.assertEqual(len({len(row) for row in rows}), 1, char)


class PlanTest(unittest.TestCase):
    def test_skip(self):
        self.assertEqual(parse_skip(["mon,tue", "weekends"]), {0, 1, 5, 6})
        with self.assertRaises(PlanError):
            parse_skip(["lundi"])

    def test_compute(self):
        plan = Plan([Segment(["2025"], "solid", {"level": 2}, ["weekends"])], scale=3)
        layout, warnings = compute(plan, TODAY)
        self.assertEqual(warnings, [])
        schedule = layout.schedule()
        self.assertTrue(all(day.weekday() < 5 and count == 6 for day, count in schedule))
        self.assertEqual(layout.active_days, 261)
        self.assertEqual(layout.commits, 261 * 6)

    def test_current_period_is_clipped_to_today(self):
        layout, _ = compute(Plan([Segment(["2026-H2"], "solid")]), TODAY)
        self.assertEqual(layout.schedule()[-1][0], TODAY)

    def test_limits(self):
        with self.assertRaises(PlanError):
            compute(Plan([Segment(["2025"], "solid")], scale=11), TODAY)
        with self.assertRaises(PlanError):
            compute(Plan([Segment(["2023", "2024", "2025"], "solid")], scale=10), TODAY)


class ConfigTest(unittest.TestCase):
    def test_dumps(self):
        plan = Plan([Segment(["2024", "2025-H1"], "text", {"text": 'say "hi"'}, ["weekends"])], scale=2)
        text = config.dumps(plan)
        self.assertIn('periods: ["2024", "2025-H1"]', text)
        self.assertIn('text: "say \\"hi\\""', text)
        self.assertIn('skip: ["weekends"]', text)

    def test_round_trip(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        plan = Plan([Segment(["2024"], "weekly", {"levels": "0,1,2,3,4,0,1"}, ["sat"])], scale=4, message="m")
        loaded = config.from_dict(yaml.safe_load(config.dumps(plan)))
        self.assertEqual(loaded.scale, 4)
        self.assertEqual(loaded.segments[0].options["levels"], [0, 1, 2, 3, 4, 0, 1])
        self.assertEqual(compute(loaded, TODAY)[0].schedule(), compute(plan, TODAY)[0].schedule())

    def test_from_dict_errors(self):
        for data in (
            {"segmentz": []},
            {"segments": [{"periods": "2024"}]},
            {"segments": [{"pattern": "solid", "x": 1}]},
        ):
            with self.assertRaises(PlanError):
                config.from_dict(data)


class GithubTest(unittest.TestCase):
    def test_parse(self):
        html = (
            '<td tabindex="0" data-date="2025-01-05" id="a" data-level="0" class="ContributionCalendar-day"></td>'
            '<td data-date="2025-01-06" data-level="3" role="gridcell" class="ContributionCalendar-day"></td>'
        )
        self.assertEqual(github.parse(html), {date(2025, 1, 5): 0, date(2025, 1, 6): 3})


if __name__ == "__main__":
    unittest.main()
