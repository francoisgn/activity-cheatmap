"""Terminal output: coloured status lines (ok/warn/ko/info) and a spinner.

Colours are disabled when the stream is not a TTY or when NO_COLOR is set.
"""

from __future__ import annotations

import itertools
import os
import sys
import threading
import time


def color_enabled(stream=None) -> bool:
    stream = stream or sys.stdout
    return stream.isatty() and not os.environ.get("NO_COLOR")


GREEN, YELLOW, RED, BLUE, CYAN, DIM, BOLD = "32", "33", "31", "34", "36", "2", "1"


def paint(code: str, text: str, stream=None) -> str:
    return f"\033[{code}m{text}\033[0m" if color_enabled(stream) else text


def _say(code: str, label: str, msg: str, stream=None) -> None:
    stream = stream or sys.stdout
    print(f"{paint(code, f'{label:<7}', stream)} {msg}", file=stream, flush=True)


def ok(msg: str) -> None:
    _say(GREEN, "ok", msg)


def warn(msg: str) -> None:
    _say(YELLOW, "warn", msg)


def ko(msg: str) -> None:
    _say(RED, "ko", msg, sys.stderr)


def info(msg: str) -> None:
    _say(BLUE, "info", msg)


def dim(text: str) -> str:
    return paint(DIM, text)


class Spinner:
    """Context manager animating a spinner on stderr while work runs.

    `update()` changes the message (e.g. progress), `detail` is appended to the
    final ok line. On exception a ko line is printed and the exception re-raised.
    """

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, msg: str):
        self.msg = msg
        self.detail = ""
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._tty = sys.stderr.isatty()

    def update(self, msg: str) -> None:
        with self._lock:
            self.msg = msg

    def _run(self) -> None:
        for frame in itertools.cycle(self.FRAMES):
            if self._stop.is_set():
                break
            with self._lock:
                line = f"\r{paint(BLUE, frame, sys.stderr)}       {self.msg}"
            sys.stderr.write(line + "\033[K")
            sys.stderr.flush()
            time.sleep(0.08)
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def __enter__(self) -> Spinner:
        if self._tty:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._stop.set()
        if self._thread:
            self._thread.join()
        if exc_type is None:
            ok(self.msg + (f" {dim('(' + self.detail + ')')}" if self.detail else ""))
        elif exc_type is not KeyboardInterrupt:
            ko(self.msg)
        return False


def spin(msg: str) -> Spinner:
    return Spinner(msg)
