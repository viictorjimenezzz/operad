"""Structural comparison between two `Agent` snapshots.

`AgentDiff` is the output of `Agent.diff(other)`. It is computed over
`AgentState` snapshots (see `operad/core/state.py`) so it never mutates
either agent and never touches a provider.

The diff covers, per matched path in the tree:

* class name (the subclass that was instantiated)
* declared I/O type names (diagnostic; not enforced)
* `role` / `task` (string-level diff via `difflib`)
* `rules` (line-level diff via `difflib.ndiff`)
* `examples` (list-level add/remove by dumped value)
* `config` (Pydantic field-level compare)

Structural changes (children added/removed/renamed) are emitted under
the parent's path as `added` / `removed` entries.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Literal

from .state import AgentState

ChangeKind = Literal[
    "class",
    "input_type",
    "output_type",
    "role",
    "task",
    "rules",
    "examples",
    "config",
    "added",
    "removed",
]


@dataclass
class Change:
    """One entry in an `AgentDiff`.

    `path` is the dotted attribute path to the agent (root-relative);
    `detail` is a human-readable block the `AgentDiff.__str__` renderer
    concatenates verbatim.
    """

    path: str
    kind: ChangeKind
    detail: str


@dataclass
class AgentDiff:
    """Result of `Agent.diff(other)`.

    Iterate `.changes` for structured access; `str(diff)` or `print(diff)`
    for a human-readable rendering. Truthy iff any change was recorded.
    """

    changes: list[Change] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.changes)

    def __len__(self) -> int:
        return len(self.changes)

    def __str__(self) -> str:
        if not self.changes:
            return "(no changes)"
        blocks: list[str] = []
        for c in self.changes:
            header = f"@ {c.path} · {c.kind}"
            blocks.append(f"{header}\n{c.detail}" if c.detail else header)
        return "\n\n".join(blocks)


def diff_states(a: AgentState, b: AgentState) -> AgentDiff:
    """Compute an `AgentDiff` between two `AgentState` snapshots.

    Paths are rooted at the reference state's class name, matching the
    convention `Agent.operad()` uses. If the two roots disagree on
    class name, the reference's name is used for path labels and the
    class-level change is surfaced as a separate entry.
    """
    changes: list[Change] = []
    _diff_states(a, b, path=a.class_name, out=changes)
    return AgentDiff(changes=changes)


def _diff_states(
    a: AgentState, b: AgentState, *, path: str, out: list[Change]
) -> None:
    if a.class_name != b.class_name:
        out.append(
            Change(path=path, kind="class", detail=f"{a.class_name} -> {b.class_name}")
        )
    if a.input_type_name != b.input_type_name:
        out.append(
            Change(
                path=path,
                kind="input_type",
                detail=f"{a.input_type_name} -> {b.input_type_name}",
            )
        )
    if a.output_type_name != b.output_type_name:
        out.append(
            Change(
                path=path,
                kind="output_type",
                detail=f"{a.output_type_name} -> {b.output_type_name}",
            )
        )

    if a.role != b.role:
        out.append(Change(path=path, kind="role", detail=_string_diff(a.role, b.role)))
    if a.task != b.task:
        out.append(Change(path=path, kind="task", detail=_string_diff(a.task, b.task)))

    if list(a.rules) != list(b.rules):
        out.append(
            Change(path=path, kind="rules", detail=_rules_diff(a.rules, b.rules))
        )

    if a.examples != b.examples:
        out.append(
            Change(
                path=path, kind="examples", detail=_examples_diff(a.examples, b.examples)
            )
        )

    config_detail = _config_diff(a.config, b.config)
    if config_detail:
        out.append(Change(path=path, kind="config", detail=config_detail))

    _diff_children(a.children, b.children, parent_path=path, out=out)


def _child_path(parent: str, name: str) -> str:
    return f"{parent}.{name}" if parent else name


def _diff_children(
    a: dict[str, AgentState],
    b: dict[str, AgentState],
    *,
    parent_path: str,
    out: list[Change],
) -> None:
    a_keys = set(a)
    b_keys = set(b)
    for name in sorted(a_keys - b_keys):
        out.append(
            Change(
                path=_child_path(parent_path, name),
                kind="removed",
                detail=f"{a[name].class_name}",
            )
        )
    for name in sorted(b_keys - a_keys):
        out.append(
            Change(
                path=_child_path(parent_path, name),
                kind="added",
                detail=f"{b[name].class_name}",
            )
        )
    for name in sorted(a_keys & b_keys):
        _diff_states(
            a[name], b[name], path=_child_path(parent_path, name), out=out
        )


def _string_diff(a: str, b: str) -> str:
    a_lines = a.splitlines() or [""]
    b_lines = b.splitlines() or [""]
    return "\n".join(
        difflib.unified_diff(a_lines, b_lines, lineterm="", n=2, fromfile="a", tofile="b")
    )


def _rules_diff(a: list[str], b: list[str]) -> str:
    return "\n".join(difflib.ndiff(list(a), list(b)))


def _examples_diff(a: list[dict], b: list[dict]) -> str:
    added: list[dict] = [e for e in b if e not in a]
    removed: list[dict] = [e for e in a if e not in b]
    lines: list[str] = []
    for e in removed:
        lines.append(f"- {e}")
    for e in added:
        lines.append(f"+ {e}")
    return "\n".join(lines)


def _config_diff(a_cfg, b_cfg) -> str:
    if a_cfg is None and b_cfg is None:
        return ""
    a_dump = a_cfg.model_dump(mode="json") if a_cfg is not None else None
    b_dump = b_cfg.model_dump(mode="json") if b_cfg is not None else None
    if a_dump == b_dump:
        return ""
    if a_dump is None:
        return f"(none) -> {b_dump}"
    if b_dump is None:
        return f"{a_dump} -> (none)"
    lines: list[str] = []
    for key in sorted(set(a_dump) | set(b_dump)):
        av = a_dump.get(key)
        bv = b_dump.get(key)
        if av != bv:
            lines.append(f"{key}: {av!r} -> {bv!r}")
    return "\n".join(lines)
