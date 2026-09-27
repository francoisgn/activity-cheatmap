"""YAML plan files.

Writing needs nothing; reading needs PyYAML (`pip install pyyaml`).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import patterns
from .plan import DEFAULT_MESSAGE, DEFAULT_SCALE, Plan, PlanError, Segment, split_list

_TOP_KEYS = {"scale", "message", "segments"}
_SEGMENT_KEYS = {"periods", "pattern", "options", "skip"}


def _scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_scalar(item) for item in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)  # JSON strings are valid YAML


def dumps(plan: Plan) -> str:
    lines = [
        "# activity-cheatmap plan: python3 -m cheatmap --config <this file>",
        "# periods: YYYY, YYYY-H1 or YYYY-H2 | levels: 0 (empty) to 4 (darkest)",
        f"scale: {plan.scale}",
        f"message: {_scalar(plan.message)}",
        "segments:",
    ]
    for segment in plan.segments:
        lines.append(f"  - periods: {_scalar(split_list(segment.periods))}")
        lines.append(f"    pattern: {segment.pattern}")
        options = patterns.resolve_options(segment.pattern, segment.options)
        if options:
            lines.append("    options:")
            lines.extend(f"      {key}: {_scalar(value)}" for key, value in options.items())
        if segment.skip:
            lines.append(f"    skip: {_scalar(split_list(segment.skip))}")
    return "\n".join(lines) + "\n"


def save(plan: Plan, path: Path) -> None:
    path.write_text(dumps(plan), encoding="utf-8")


def load(path: Path) -> Plan:
    try:
        import yaml
    except ImportError:
        raise PlanError("reading YAML needs PyYAML: pip install pyyaml") from None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise PlanError(f"{path}: {error}") from None
    return from_dict(data or {}, base_dir=path.parent)


def from_dict(data: dict, base_dir: Path | None = None) -> Plan:
    if not isinstance(data, dict):
        raise PlanError("config must be a mapping")
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise PlanError(f"unknown key(s): {', '.join(sorted(unknown))}")
    segments = []
    for index, raw in enumerate(data.get("segments") or [], 1):
        if not isinstance(raw, dict):
            raise PlanError(f"segment {index}: must be a mapping")
        unknown = set(raw) - _SEGMENT_KEYS
        if unknown:
            raise PlanError(f"segment {index}: unknown key(s) {', '.join(sorted(unknown))}")
        if "pattern" not in raw:
            raise PlanError(f"segment {index}: 'pattern' is required")
        options = dict(raw.get("options") or {})
        if raw["pattern"] == "image" and "file" in options and base_dir is not None:
            file = Path(str(options["file"])).expanduser()
            options["file"] = str(file if file.is_absolute() else base_dir / file)
        segments.append(
            Segment(
                periods=split_list(raw.get("periods")),
                pattern=str(raw["pattern"]),
                options=options,
                skip=split_list(raw.get("skip")),
            )
        )
    try:
        scale = int(data.get("scale", DEFAULT_SCALE))
    except (TypeError, ValueError):
        raise PlanError("scale must be an integer") from None
    return Plan(segments, scale=scale, message=str(data.get("message", DEFAULT_MESSAGE)))
