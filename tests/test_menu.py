import io
import random
import subprocess
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

from cheatmap import art, cli, github, menu, patterns
from cheatmap.plan import compute

TODAY = date(2026, 9, 27)


class HelpersTest(unittest.TestCase):
    def test_parse_selection(self):
        self.assertEqual(menu.parse_selection("1,3", 4), [0, 2])
        self.assertEqual(menu.parse_selection("2-4, 1", 4), [0, 1, 2, 3])
        self.assertEqual(menu.parse_selection("all", 3), [0, 1, 2])
        for bad in ("0", "5", "3-2", "x", ""):
            with self.assertRaises(ValueError):
                menu.parse_selection(bad, 4)

    def test_halves(self):
        self.assertEqual(menu.halves_between(date(2024, 7, 1), date(2025, 6, 30)), ["2024-H2", "2025-H1"])
        self.assertEqual(menu.halves_between(date(2024, 1, 1), date(2025, 6, 30)), ["2024", "2025-H1"])
        self.assertEqual(menu.merge_halves(["2023-H2", "2024-H1", "2024-H2"]), ["2023-H2", "2024"])
        starts = menu.half_starts(TODAY)
        self.assertEqual((starts[0], starts[-1], len(starts)), (date(2008, 1, 1), date(2026, 7, 1), 38))
        self.assertEqual(menu.half_starts(TODAY, 2017)[0], date(2017, 1, 1))

    def test_examples_are_valid(self):
        for title, name, options, skip in menu.EXAMPLES:
            state = menu.State(name, menu.non_default(name, options), ["2025"], skip)
            layout, _ = compute(state.plan(), TODAY)
            self.assertGreater(layout.commits, 0, title)

    def test_random_patterns_are_valid(self):
        rng = random.Random(42)
        for _ in range(200):
            name, options, skip = menu.random_pattern(rng)
            patterns.build(name, options, 53)
            menu.parse_skip(skip)

    def test_argv_round_trip(self):
        state = menu.State("text", {"text": "HI 2026", "fg": 3}, ["2024", "2025"], ["weekends"], scale=4)
        args = cli.parse_args(state.argv("--dry-run"))
        self.assertEqual(cli.build_plan(args).segments[0].options, {"text": "HI 2026", "fg": "3"})
        self.assertEqual(compute(cli.build_plan(args), TODAY)[0].schedule(), compute(state.plan(), TODAY)[0].schedule())
        self.assertIn("'text=HI 2026'", menu.command(state.argv()))

    def test_banner(self):
        lines = art.clawd(color=False)
        self.assertIn("▐▛███▜▌", "\n".join(lines))
        self.assertNotIn("■", art.banner())


class WizardTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(github, "account_created", return_value=date(2008, 1, 1))  # no network
        patcher.start()
        self.addCleanup(patcher.stop)

    def drive(self, answers):
        out = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(mock.patch("builtins.input", side_effect=answers))
            stack.enter_context(mock.patch("sys.stdin.isatty", return_value=True))
            stack.enter_context(mock.patch.object(menu, "github_user", return_value=""))
            stack.enter_context(redirect_stdout(out))
            stack.enter_context(redirect_stderr(out))
            code = menu.main_menu(TODAY)
        return code, out.getvalue()

    def test_generate_and_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / "remote.git"
            subprocess.run(["git", "init", "--quiet", "--bare", str(remote)], check=True)
            # no background gc after the push: it races the temp dir cleanup
            subprocess.run(["git", "config", "receive.autogc", "false"], cwd=remote, check=True)
            workdir = Path(tmp) / "out"
            answers = [
                "2",  # main menu: generate
                "5",  # pattern: solid
                "y",  # customise
                "2",  # level
                "2",  # coverage: by semester
                "18",  # years: 2025 (list starts in 2008)
                "1",  # 2025-H1
                "2",  # skip weekends
                "n",  # no before/after comparison
                "8",  # show the command
                "",  # pause
                "1",  # push
                str(remote),
                "n",  # no force
                "",  # pause
                "q",
            ]
            real_run_cli = menu.run_cli
            with mock.patch.object(menu, "run_cli", side_effect=lambda argv: real_run_cli(argv + self.extra(workdir))):
                code, output = self.drive(answers)
            self.assertEqual(code, 0, output)
            self.assertIn("-p 2025-H1 -P solid -o level=2 --skip weekends --remote '<remote>'", output)
            count = subprocess.run(["git", "rev-list", "--count", "main"], cwd=remote, capture_output=True, text=True)
            self.assertEqual(int(count.stdout), 129 * 2 * 3)  # 129 weekdays x level 2 x scale 3

    @staticmethod
    def extra(workdir):
        return ["--workdir", str(workdir), "--delay", "0", "--name", "Me", "--email", "me@example.com"]

    def test_gallery_back_and_quit(self):
        code, output = self.drive(["1", "1", "12", "b", "b", "b", "3", "", "q"])
        self.assertEqual(code, 0)
        self.assertIn("Clawd parade", output)
        self.assertIn("sprite", output)

    def test_needs_a_terminal(self):
        with mock.patch("sys.stdin.isatty", return_value=False), redirect_stderr(io.StringIO()):
            self.assertEqual(menu.main_menu(TODAY), 1)


if __name__ == "__main__":
    unittest.main()
