import sys

if sys.version_info < (3, 9):  # noqa: UP036 (runtime guard for older interpreters)
    sys.exit(f"ko      activity-cheatmap needs Python 3.9+, this is {sys.version.split()[0]} ({sys.executable})")

from .cli import main  # noqa: E402

sys.exit(main())
