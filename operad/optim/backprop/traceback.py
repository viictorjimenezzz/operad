"""`PromptTraceback` — Python-traceback-shaped view of a training tape.

Given a `Tape` and a `path -> TextualGradient` map, render each recorded
node in reverse call order (leaves first), so the user can debug a bad
training batch the same way they debug a bad Python call. The alternate
constructor `PromptTraceback.from_run(tape, loss)` reuses `backward()`'s
structural split rules (no LLM) to derive those per-path gradients from a
single root-level loss.

Rendering surfaces:

- ``str(tb)``              plain-text stanzas, stdlib-only.
- ``tb.__rich__()``         a ``rich.tree.Tree`` when ``rich`` is installed;
                            falls back to the plain renderer otherwise.
- ``tb.to_markdown()``     fenced-block Markdown, safe for PR bodies.
- ``tb.save(path)``        NDJSON dump, one frame per line.

The traceback is an *observer* of the tape and the gradient dict; it
never mutates either.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from operad.optim.backprop.backward import _rule_for
from operad.optim.backprop.tape import Tape, TapeEntry
from operad.optim.parameter import TextualGradient

__all__ = ["PromptTraceback", "TracebackFrame", "traceback"]


_MAX_VALUE_CHARS = 2048
_WRAP_COLS = 120


# ---------------------------------------------------------------------------
# Domain schemas.
# ---------------------------------------------------------------------------


@dataclass
class TracebackFrame:
    """One rendered node of a ``PromptTraceback``."""

    agent_path: str
    depth: int
    is_leaf: bool
    input_dump: Any
    output_dump: Any
    rendered_prompt: str | list[dict[str, str]] | None
    gradient: TextualGradient | None


# ---------------------------------------------------------------------------
# Prompt traceback.
# ---------------------------------------------------------------------------


class PromptTraceback:
    """Debugging view of a training run.

    Construct either with an explicit ``gradients`` dict or via
    ``PromptTraceback.from_run(tape, loss)``; the latter walks the tape
    with the backward split rules to attribute ``loss`` to each node.
    """

    def __init__(
        self,
        tape: Tape,
        gradients: dict[str, TextualGradient] | None = None,
        *,
        redact: Callable[[BaseModel], BaseModel] | None = None,
        max_value_chars: int = _MAX_VALUE_CHARS,
        wrap_cols: int = _WRAP_COLS,
    ) -> None:
        self.tape = tape
        self.gradients: dict[str, TextualGradient] = dict(gradients or {})
        self.redact = redact
        self.max_value_chars = max_value_chars
        self.wrap_cols = wrap_cols

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_run(
        cls,
        tape: Tape,
        loss: TextualGradient,
        *,
        redact: Callable[[BaseModel], BaseModel] | None = None,
        max_value_chars: int = _MAX_VALUE_CHARS,
        wrap_cols: int = _WRAP_COLS,
    ) -> PromptTraceback:
        """Seed ``loss`` at the root and distribute it via the structural
        split rules in ``operad.optim.backprop.backward``.

        This mirrors ``backward()``'s pass-1 split step, minus the LLM
        refinement performed by ``propagate``. The result is the raw
        structural flow of the loss — the gradient each node received as
        input — which is what a debugging user wants to see.
        """
        gradients: dict[str, TextualGradient] = {}
        if tape.entries:
            root_path = tape.entries[0].agent_path
            gradients[root_path] = loss
            for entry in tape.entries:
                g_in = gradients.get(entry.agent_path)
                if g_in is None or entry.is_leaf:
                    continue
                agent = entry.agent_ref()
                if agent is None:
                    continue
                children = tape.children_of(entry.agent_path)
                contributions = _rule_for(agent)(entry, g_in, children)
                for child_path, grad in contributions.items():
                    gradients[child_path] = grad
        return cls(
            tape,
            gradients,
            redact=redact,
            max_value_chars=max_value_chars,
            wrap_cols=wrap_cols,
        )

    # ------------------------------------------------------------------
    # Frame materialization
    # ------------------------------------------------------------------

    def frames(self) -> list[TracebackFrame]:
        """Return one ``TracebackFrame`` per tape entry in reverse-call
        order (deepest/latest first, matching a Python traceback)."""
        return [self._frame_for(entry) for entry in self.tape.entries_in_reverse()]

    def _frame_for(self, entry: TapeEntry) -> TracebackFrame:
        return TracebackFrame(
            agent_path=entry.agent_path,
            depth=entry.agent_path.count("."),
            is_leaf=entry.is_leaf,
            input_dump=self._dump_payload(entry.input),
            output_dump=self._dump_payload(entry.output),
            rendered_prompt=entry.rendered_prompt,
            gradient=self.gradients.get(entry.agent_path),
        )

    def _dump_payload(self, model: BaseModel | None) -> Any:
        if model is None:
            return None
        if self.redact is not None and isinstance(model, BaseModel):
            try:
                model = self.redact(model)
            except Exception:
                pass
        if isinstance(model, BaseModel):
            return model.model_dump(mode="json")
        return model

    # ------------------------------------------------------------------
    # Plain-text rendering
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        lines: list[str] = ["Traceback (most recent agent call last):"]
        for frame in self.frames():
            lines.extend(self._stanza(frame))
        return "\n".join(lines)

    def _stanza(self, frame: TracebackFrame) -> list[str]:
        lines = [f'  File "agent://{frame.agent_path}", in forward']
        lines.append(self._format_payload("Input", frame.input_dump))
        lines.append(self._format_payload("Output", frame.output_dump))
        lines.append(self._format_gradient(frame.gradient))
        return lines

    def _format_payload(self, label: str, value: Any) -> str:
        if value is None:
            body = "<none>"
        else:
            body = json.dumps(value, indent=2, ensure_ascii=False, default=str)
            body = self._truncate(body)
        return self._indent_label(label, body)

    def _format_gradient(self, grad: TextualGradient | None) -> str:
        if grad is None:
            return "    Gradient: <none>"
        body = f"[severity={grad.severity:.2f}] {grad.message}"
        return "    Gradient: " + self._truncate(body)

    def _indent_label(self, label: str, body: str) -> str:
        pad = " " * 4
        head = f"{pad}{label}: "
        if "\n" not in body and len(head) + len(body) <= self.wrap_cols:
            return head + body
        cont = " " * (len(head))
        body_lines = body.splitlines() or [""]
        first = head + body_lines[0]
        rest = [cont + ln for ln in body_lines[1:]]
        return "\n".join([first, *rest])

    def _truncate(self, s: str) -> str:
        if len(s) <= self.max_value_chars:
            return s
        overflow = len(s) - self.max_value_chars
        return s[: self.max_value_chars] + f" ... [truncated {overflow} chars]"

    # ------------------------------------------------------------------
    # Rich rendering (optional)
    # ------------------------------------------------------------------

    def __rich__(self) -> Any:
        try:
            from rich.tree import Tree
        except ImportError:  # pragma: no cover - optional dep
            return str(self)

        tree = Tree("[bold red]PromptTraceback[/] (most recent agent call last)")
        for frame in self.frames():
            style = self._rich_style(frame.gradient)
            node = tree.add(f"[{style}]agent://{frame.agent_path}[/]")
            node.add(self._format_payload("Input", frame.input_dump).strip())
            node.add(self._format_payload("Output", frame.output_dump).strip())
            node.add(self._format_gradient(frame.gradient).strip())
        return tree

    @staticmethod
    def _rich_style(grad: TextualGradient | None) -> str:
        if grad is None or grad.severity == 0.0:
            return "dim"
        if grad.severity >= 0.7:
            return "bold red"
        if grad.severity >= 0.3:
            return "yellow"
        return "default"

    # ------------------------------------------------------------------
    # Markdown rendering
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        sections: list[str] = ["# PromptTraceback", ""]
        for frame in self.frames():
            sections.append(f'### File "agent://{frame.agent_path}"')
            sections.append("")
            sections.append("```text")
            sections.append(self._format_payload("Input", frame.input_dump))
            sections.append(self._format_payload("Output", frame.output_dump))
            sections.append(self._format_gradient(frame.gradient))
            sections.append("```")
            sections.append("")
        return "\n".join(sections).rstrip() + "\n"

    # ------------------------------------------------------------------
    # NDJSON persistence
    # ------------------------------------------------------------------

    def save(self, path: Path | str) -> None:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            for frame in self.frames():
                record = {
                    "agent_path": frame.agent_path,
                    "depth": frame.depth,
                    "is_leaf": frame.is_leaf,
                    "input": frame.input_dump,
                    "output": frame.output_dump,
                    "rendered_prompt": frame.rendered_prompt,
                    "gradient": (
                        frame.gradient.model_dump()
                        if frame.gradient is not None
                        else None
                    ),
                }
                fh.write(json.dumps(record, ensure_ascii=False, default=str))
                fh.write("\n")


# ---------------------------------------------------------------------------
# Factory.
# ---------------------------------------------------------------------------


def traceback(
    tape: Tape,
    loss: TextualGradient | None = None,
    gradients: dict[str, TextualGradient] | None = None,
    *,
    redact: Callable[[BaseModel], BaseModel] | None = None,
) -> PromptTraceback:
    """Build a ``PromptTraceback`` from either a root ``loss`` or an
    explicit ``gradients`` map. Passing both is an error."""
    if loss is not None and gradients is not None:
        raise ValueError("traceback(): pass either `loss` or `gradients`, not both")
    if loss is not None:
        return PromptTraceback.from_run(tape, loss, redact=redact)
    return PromptTraceback(tape, gradients, redact=redact)
