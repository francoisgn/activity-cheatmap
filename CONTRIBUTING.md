# Contributing

Contributions are welcome: bug reports, ideas, new patterns or sprites, fixes.

## Permission to contribute

This project is licensed under the [PolyForm Strict License 1.0.0](LICENSE),
which does not allow changes or distribution. As an exception, **the licensor
grants you permission to fork this repository on GitHub and to make changes to
the software, solely to prepare and submit contributions (issues and pull
requests) to this repository.** This permission does not cover using,
publishing or distributing your changes for any other purpose.

## License of your contributions

By submitting a contribution, you confirm that you have the right to submit
it (you wrote it, or it is otherwise yours to give), and you grant francoisgn a
perpetual, worldwide, non-exclusive, royalty-free, irrevocable license to use,
modify, distribute, sublicense and relicense your contribution, as part of this
project or otherwise, under any terms, including terms other than the current
license of the project.

## How to contribute

- **Bugs and ideas**: open an issue. Security problems go through the private
  report described in [SECURITY.md](SECURITY.md), never a public issue.
- **Pull requests**: keep them focused, one topic per PR.

Before opening a pull request:

```sh
pre-commit install              # ruff, YAML/TOML checks and unit tests on each commit
pre-commit run --all-files
python3 -m unittest discover -s tests
```

Conventions:

- Python 3.9+ and the standard library only for the core (PyYAML and Pillow stay optional).
- Program output in English, coloured statuses (`ok`, `warn`, `ko`, `info`) through `cheatmap/ui.py`.
- Shell snippets in docs stay portable (POSIX sh / bash), not tied to zsh.
- New patterns or sprites come with a test and a line in the README.
