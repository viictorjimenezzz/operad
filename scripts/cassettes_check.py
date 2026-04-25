"""Cassette drift watchdog.

Walks every tests/**/cassettes/*.jsonl file and reports candidates that
may need re-recording. Stale detection is mtime-based: a cassette is
flagged when any operad source file (operad/**/*.py) is newer than the
cassette. This is a heuristic — a CassetteMiss during pytest is the
authoritative signal.

Exit 0 by default (informational); pass --strict for non-zero exit on
any stale cassette (useful as a CI gate).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _operad_source_files(root: Path) -> list[Path]:
    return list((root / "operad").rglob("*.py"))


def _check(root: Path) -> list[tuple[Path, str]]:
    """Return list of (cassette_path, reason) for flagged cassettes."""
    source_files = _operad_source_files(root)
    if not source_files:
        return []

    newest_source_mtime = max(p.stat().st_mtime for p in source_files)
    issues: list[tuple[Path, str]] = []

    for cassette_path in sorted(root.glob("tests/**/cassettes/*.jsonl")):
        cassette_mtime = cassette_path.stat().st_mtime

        # mtime stale check
        if newest_source_mtime > cassette_mtime:
            newer = [
                p for p in source_files if p.stat().st_mtime > cassette_mtime
            ]
            label = newer[0].relative_to(root) if newer else "operad source"
            issues.append(
                (cassette_path, f"newer source: {label} (mtime-based heuristic; re-record to clear)")
            )
            continue

        # format validation: each line must have required hash fields
        try:
            text = cassette_path.read_text()
        except OSError as exc:
            issues.append((cassette_path, f"unreadable: {exc}"))
            continue

        for lineno, raw in enumerate(text.splitlines(), start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as exc:
                issues.append((cassette_path, f"line {lineno}: invalid JSON — {exc}"))
                break
            missing = [f for f in ("key", "hash_model", "hash_prompt", "hash_input") if f not in entry]
            if missing:
                issues.append(
                    (cassette_path, f"line {lineno}: missing fields {missing}")
                )
                break

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any stale cassettes are found.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Repository root (default: parent of this script).",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    issues = _check(root)

    if not issues:
        print("cassettes-check: all cassettes look fresh.")
        return 0

    print(f"cassettes-check: {len(issues)} candidate(s) may need re-recording:\n")
    for path, reason in issues:
        print(f"  {path.relative_to(root)}")
        print(f"    {reason}")
    print(f"\nRun `make cassettes-refresh` to re-record against a live backend.")

    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
