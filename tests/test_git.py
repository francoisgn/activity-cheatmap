"""Generation and push against a local bare repository (no network)."""

import io
import subprocess
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

from cheatmap import cli, github, gitops


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def bare_remote(path):
    """Bare repo without the background gc a push triggers (it races the temp dir cleanup)."""
    git("init", "--quiet", "--bare", str(path))
    git("config", "receive.autogc", "false", cwd=path)


class GitTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.remote = self.tmp / "remote.git"
        bare_remote(self.remote)

    def tearDown(self):
        self._tmp.cleanup()

    def test_build_dates_and_counts(self):
        workdir = self.tmp / "out"
        schedule = [(date(2025, 1, 1), 2), (date(2025, 1, 3), 3)]
        self.assertEqual(gitops.build(workdir, schedule, "Me", "me@example.com", "msg", "main"), 5)
        lines = git("log", "--format=%ad %cd %ae", "--date=iso-strict", "main", cwd=workdir).split()
        authored, committed, emails = lines[0::3], lines[1::3], lines[2::3]
        self.assertEqual(Counter(stamp[:10] for stamp in authored), {"2025-01-01": 2, "2025-01-03": 3})
        self.assertEqual(authored, committed)
        self.assertTrue(all(stamp.endswith(("Z", "+00:00")) for stamp in authored))
        self.assertEqual(set(emails), {"me@example.com"})

    def test_prepare_workdir_refuses_foreign_dirs(self):
        foreign = self.tmp / "foreign"
        foreign.mkdir()
        (foreign / "file").write_text("x")
        with self.assertRaises(gitops.GitError):
            gitops.prepare_workdir(foreign)
        generated = self.tmp / "generated"
        gitops.build(generated, [(date(2025, 1, 1), 1)], "Me", "me@example.com", "msg", "main")
        gitops.prepare_workdir(generated)
        self.assertFalse(generated.exists())

    def test_explain(self):
        self.assertIn(
            "create it on GitHub first", gitops.explain("ERROR: Repository not found.\nfatal: Could not read")
        )
        self.assertIn("ssh -T", gitops.explain("git@github.com: Permission denied (publickey)."))
        self.assertIn("network", gitops.explain("ssh: Could not resolve host github.com"))
        self.assertIsNone(gitops.explain("something else"))

    def test_batch_ends(self):
        self.assertEqual(gitops.batch_ends(10, 4), [3, 7, 9])
        self.assertEqual(gitops.batch_ends(8, 4), [3, 7])
        self.assertEqual(gitops.batch_ends(0, 4), [])

    def test_push_in_batches(self):
        workdir = self.tmp / "out"
        gitops.build(workdir, [(date(2025, 1, day), 3) for day in range(1, 5)], "Me", "me@example.com", "m", "main")
        calls, sleeps = [], []
        pushes = gitops.push(
            workdir, str(self.remote), "main", 5, 0.5, False, lambda *a: calls.append(a), sleeps.append
        )
        self.assertEqual(pushes, 3)
        self.assertEqual(calls, [(1, 3, 5), (2, 3, 10), (3, 3, 12)])
        self.assertEqual(sleeps, [0.5, 0.5])
        self.assertEqual(git("rev-list", "--count", "main", cwd=self.remote).strip(), "12")

    def test_push_retries_with_backoff(self):
        workdir = self.tmp / "out"
        gitops.build(workdir, [(date(2025, 1, 1), 2)], "Me", "me@example.com", "m", "main")
        real_git = gitops.git
        failures = iter([gitops.GitError("connection reset")])

        def flaky(*args, **kwargs):
            if args[0] == "push":
                error = next(failures, None)
                if error:
                    raise error
            return real_git(*args, **kwargs)

        sleeps = []
        with mock.patch.object(gitops, "git", side_effect=flaky):
            gitops.push(workdir, str(self.remote), "main", 1, 2.0, False, lambda *a: None, sleeps.append)
        self.assertEqual(sleeps, [4.0, 4.0])  # retry, then the slower pace is kept

    def test_push_fails_fast_on_auth_errors(self):
        workdir = self.tmp / "out"
        gitops.build(workdir, [(date(2025, 1, 1), 1)], "Me", "me@example.com", "m", "main")
        denied = gitops.GitError("Permission denied (publickey)")
        with mock.patch.object(gitops, "git", side_effect=denied), self.assertRaises(gitops.GitError):
            gitops.push(workdir, "remote", "main", 1, 0, False, lambda *a: None, lambda s: self.fail("slept"))


class CliTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(github, "account_created", return_value=date(2008, 1, 1))  # no network
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_end_to_end_and_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / "remote.git"
            bare_remote(remote)
            common = [
                "-p",
                "2025-H1",
                "-P",
                "weekly",
                "--remote",
                str(remote),
                "--workdir",
                str(Path(tmp) / "out"),
                "--name",
                "Me",
                "--email",
                "me@users.noreply.github.com",
                "--delay",
                "0",
                "--batch-size",
                "500",
            ]
            code, output = self.run_cli(*common, "-o", "levels=1,0,0,0,0,0,0")
            self.assertEqual(code, 0, output)
            self.assertEqual(git("rev-list", "--count", "main", cwd=remote).strip(), str(26 * 3))

            code, output = self.run_cli(*common)
            self.assertEqual(code, 1)
            self.assertIn("--force", output)

            code, output = self.run_cli(*common[:4], "--remote", str(Path(tmp) / "missing.git"), "--no-preview")
            self.assertEqual(code, 1)
            self.assertIn("create it on GitHub first", output)

            code, output = self.run_cli(*common, "-o", "levels=0,0,0,0,0,0,2", "--force", "--yes")
            self.assertEqual(code, 0, output)
            self.assertEqual(git("rev-list", "--count", "main", cwd=remote).strip(), str(26 * 6))

    def test_dry_run_and_errors(self):
        code, output = self.run_cli("-p", "2025", "-P", "gradient-diag", "-o", "direction=up-left", "-n")
        self.assertEqual(code, 0, output)
        self.assertIn("dry run", output)
        for argv in (["-p", "2025"], ["-p", "2007", "-P", "solid", "-n"], ["-p", "2025", "-P", "solid", "-o", "x"]):
            code, output = self.run_cli(*argv)
            self.assertEqual(code, 1, argv)


if __name__ == "__main__":
    unittest.main()
