"""Reverse-pass gradient propagation over a recorded `Tape`.

``backward(tape, loss)`` walks a tape produced by ``operad.optim.tape()``
and writes a ``TextualGradient`` onto every trainable ``Parameter``'s
``.grad`` slot. The walk is two-pass:

1. **Forward pass (start-order over ``tape.entries``).** Seeds
   ``downstream_grad[root] = loss``, runs ``BackpropAgent`` at each node
   to refine the critique on that node's output, applies
   ``_backward_hooks``, and — for composite nodes — calls the registered
   split rule to hand each child its own downstream gradient. This is
   the "reverse graph walk" in the dataflow sense: gradients flow
   output → input, even though we iterate the tape in start-order
   (parent-before-child).

2. **Reverse pass (over ``tape.entries_in_reverse()``, leaves only).**
   For each leaf, dispatches ``parameter_grad(...)`` concurrently across
   its trainable ``Parameter``s (bounded by ``concurrency``) and writes
   ``.grad`` in place.

Custom composite types register their own split rules via
``register_backward_rule(cls, fn)``. Built-in rules cover ``Pipeline``,
``Parallel``, and ``Switch``; every other composite falls back to a
uniform fan-out with a one-time ``RuntimeWarning``.

Observability: each refined node-gradient and each per-parameter
gradient emits a synthetic ``_backward.<path>`` ``AgentEvent`` so the
existing observer stack (``JsonlObserver``, etc.) can follow the
backward pass. The event's ``run_id`` is taken from the tape entry so
the backward pass correlates with the forward pass in downstream tools.

Known limitations (filed as follow-up issues):
- ``_pipeline_split`` hands the full gradient to the last stage and a
  copy to every earlier stage. ``propagate`` today refines a node's
  output-critique; it does not produce an input-gradient, so we cannot
  chain stage-k's output-grad into stage-(k-1)'s output-grad.
- ``_switch_split`` gives the router a null gradient. A future rule can
  attribute "you routed to the wrong branch" back into the router when
  the branch's output-critique points away from the taken branch.
- ``Debate`` (an algorithm, not an ``Agent`` subclass) falls through to
  the generic composite rule and receives uniform fan-out.
"""

from __future__ import annotations

import asyncio
import time
import warnings
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from operad.core.agent import Agent
from operad.optim.grad_agent import (
    BackpropAgent,
    ParameterGradAgent,
    parameter_grad,
    parameter_grad_for,
    propagate,
)
from operad.optim.parameter import Parameter, ParameterKind, TextualGradient
from operad.optim.tape import Tape, TapeEntry
from operad.runtime.observers.base import AgentEvent, registry


# ---------------------------------------------------------------------------
# Split-rule type + registry
# ---------------------------------------------------------------------------


SplitRule = Callable[
    [TapeEntry, TextualGradient, list[TapeEntry]],
    dict[str, TextualGradient],
]

_RULES: dict[type[Agent[Any, Any]], SplitRule] = {}


def register_backward_rule(
    composite_cls: type[Agent[Any, Any]], fn: SplitRule
) -> None:
    """Register a structural split rule for a composite ``Agent`` class.

    Rule resolution walks ``type(agent).__mro__``; the first class with a
    registered rule wins, so registering a subclass overrides a parent's
    rule. ``_generic_composite_rule`` applies when nothing matches.
    """
    _RULES[composite_cls] = fn


def _rule_for(agent: Agent[Any, Any]) -> SplitRule:
    for cls in type(agent).__mro__:
        rule = _RULES.get(cls)
        if rule is not None:
            return rule
    return _generic_composite_rule


# ---------------------------------------------------------------------------
# Built-in split rules
# ---------------------------------------------------------------------------


def _pipeline_split(
    entry: TapeEntry,
    out_grad: TextualGradient,
    children: list[TapeEntry],
) -> dict[str, TextualGradient]:
    """Pipeline: last stage's output IS the composite's output, so hand
    it the full gradient. Earlier stages receive a copy of the same
    gradient as a coarse default — ``propagate`` refines output-critiques
    and has no primitive for translating an output-grad into an
    input-grad (which would be stage-(k-1)'s output-grad). A dedicated
    per-stage chaining rule is a future extension."""
    _ = entry
    result: dict[str, TextualGradient] = {}
    if not children:
        return result
    last_path = children[-1].agent_path
    for child in children:
        if child.agent_path == last_path:
            result[child.agent_path] = out_grad
        else:
            result[child.agent_path] = out_grad.model_copy()
    return result


def _parallel_split(
    entry: TapeEntry,
    out_grad: TextualGradient,
    children: list[TapeEntry],
) -> dict[str, TextualGradient]:
    """Parallel: uniform fan-out. Every branch receives the same
    gradient. Weighted splits (e.g. keyed by ``combine`` weights) are
    a future extension."""
    _ = entry
    return {child.agent_path: out_grad.model_copy() for child in children}


def _switch_split(
    entry: TapeEntry,
    out_grad: TextualGradient,
    children: list[TapeEntry],
) -> dict[str, TextualGradient]:
    """Switch: only the taken branch receives the gradient. The taken
    branch is identified by matching each child's ``response`` against
    the Switch's ``response``. Router and untaken branches get the
    null gradient."""
    null = TextualGradient.null_gradient()
    result: dict[str, TextualGradient] = {
        child.agent_path: null for child in children
    }
    switch_response = _response_of(entry)
    if switch_response is None:
        return result
    for child in children:
        if child.agent_path.endswith(".router"):
            continue
        if _models_equal(_response_of(child), switch_response):
            result[child.agent_path] = out_grad
            break
    return result


_GENERIC_WARNED: set[str] = set()


def _generic_composite_rule(
    entry: TapeEntry,
    out_grad: TextualGradient,
    children: list[TapeEntry],
) -> dict[str, TextualGradient]:
    """Fallback: fan out uniformly to every child, with a one-time
    ``RuntimeWarning`` per composite class so callers know they may
    want a custom rule."""
    agent = entry.agent_ref()
    cls_name = type(agent).__name__ if agent is not None else "?"
    if cls_name not in _GENERIC_WARNED:
        _GENERIC_WARNED.add(cls_name)
        warnings.warn(
            f"backward(): no structural split rule for {cls_name!r}; "
            "falling back to uniform fan-out. Register one with "
            "register_backward_rule() to customize.",
            RuntimeWarning,
            stacklevel=3,
        )
    return {child.agent_path: out_grad.model_copy() for child in children}


def _register_builtin_rules() -> None:
    from operad.agents.parallel import Parallel
    from operad.agents.pipeline import Pipeline
    from operad.agents.reasoning.switch import Switch

    _RULES[Pipeline] = _pipeline_split
    _RULES[Parallel] = _parallel_split
    _RULES[Switch] = _switch_split


_register_builtin_rules()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_null(grad: TextualGradient) -> bool:
    return grad.severity == 0.0 and not grad.message


def _deref(entry: TapeEntry) -> Agent[Any, Any]:
    agent = entry.agent_ref()
    if agent is None:
        raise RuntimeError(
            f"backward: agent at {entry.agent_path!r} was "
            "garbage-collected before backward()"
        )
    return agent


def _prompt_str(entry: TapeEntry) -> str:
    rp = entry.rendered_prompt
    if rp is None:
        return ""
    if isinstance(rp, list):
        return "\n\n".join(
            m.get("content", "") for m in rp if m.get("role") == "system"
        )
    return rp


def _response_of(entry: TapeEntry) -> Any:
    """Unwrap the ``OperadOutput`` envelope stored on the entry.

    ``TapeObserver`` records the full envelope; ``propagate`` /
    ``parameter_grad`` want the raw typed response (the ``Out`` model
    the node produced), not the envelope's hash-decorated wrapper.
    """
    out = entry.output
    if out is None:
        return None
    return getattr(out, "response", out)


def _models_equal(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    if a is b:
        return True
    try:
        return a.model_dump(mode="json") == b.model_dump(mode="json")
    except Exception:
        return False


def _params_for_agent(
    agent: Agent[Any, Any], user_params: list[Parameter[Any]] | None
) -> list[Parameter[Any]]:
    """Return the trainable parameters on ``agent``.

    When the caller supplied ``parameters`` to ``backward()``, filter
    that list to the instances whose weakref resolves to ``agent``. The
    caller-supplied instances are the ones the optimizer holds; writing
    ``.grad`` onto them is the only write that is observable afterwards.

    Without ``parameters``, fall back to a fresh view from the agent.
    Writes onto fresh views do not persist across further
    ``agent.parameters()`` calls but still flow into
    ``parameter_grad`` / hooks / observer events.
    """
    if user_params is None:
        return [p for p in agent.parameters(recurse=False) if p.requires_grad]

    out: list[Parameter[Any]] = []
    for p in user_params:
        if not p.requires_grad:
            continue
        try:
            owner = p._agent()
        except RuntimeError:
            continue
        if owner is agent:
            out.append(p)
    return out


def _run_backward_hooks(
    agent: Agent[Any, Any], grad: TextualGradient
) -> TextualGradient:
    for fn in tuple(getattr(agent, "_backward_hooks", ())):
        result = fn(agent, grad)
        if result is not None:
            grad = result
    return grad


async def _emit_backward_event(
    entry: TapeEntry,
    *,
    phase: str,
    grad: TextualGradient | None = None,
    param_path: str | None = None,
) -> None:
    metadata: dict[str, Any] = {"phase": phase}
    if grad is not None:
        metadata["severity"] = grad.severity
        metadata["message_len"] = len(grad.message)
    if param_path is not None:
        metadata["param_path"] = param_path
    now = time.monotonic()
    await registry.notify(
        AgentEvent(
            run_id=entry.run_id,
            agent_path=f"_backward.{entry.agent_path}",
            kind="end",
            input=None,
            output=None,
            error=None,
            started_at=now,
            finished_at=now,
            metadata=metadata,
        )
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def backward(
    tape: Tape,
    loss: TextualGradient,
    *,
    parameters: Iterable[Parameter[Any]] | None = None,
    propagator_factory: Callable[[], BackpropAgent] | None = None,
    parameter_grad_factory: (
        Callable[[ParameterKind], ParameterGradAgent] | None
    ) = None,
    concurrency: int = 4,
) -> None:
    """Walk ``tape`` in reverse and populate ``.grad`` on every trainable
    parameter beneath the root.

    ``loss`` is the output gradient of the whole computation (typically
    produced by a ``Loss`` instance).

    ``parameters`` is the list of ``Parameter`` instances to write grads
    onto. Pass the same list the optimizer holds: ``Agent.parameters()``
    yields fresh read-through views on every call, so mutating a view
    produced inside ``backward`` would not reach the optimizer's view.
    When omitted, ``backward`` falls back to ``agent.parameters()`` at
    each leaf — the grads still reach the right logical slot and still
    flow through ``parameter_grad``/hooks/events, but no caller can
    observe them afterwards.

    ``propagator_factory`` and ``parameter_grad_factory`` override the
    default ``BackpropAgent`` / ``ParameterGradAgent`` instances used at
    each node. Factories are synchronous and must return a built agent;
    the default path lazily constructs and ``abuild()``s a shared
    instance on first use.

    ``concurrency`` bounds the number of concurrent ``parameter_grad``
    calls per leaf. Pass 1 (the propagate/split walk) is sequential
    because each composite depends on its predecessor's refined grad.
    """
    if not tape.entries:
        warnings.warn(
            "backward() called on empty tape; no-op",
            RuntimeWarning,
            stacklevel=2,
        )
        return

    sem = asyncio.Semaphore(concurrency)

    user_params: list[Parameter[Any]] | None = (
        list(parameters) if parameters is not None else None
    )

    _prop_cache: dict[str, BackpropAgent] = {}
    _pg_cache: dict[ParameterKind, ParameterGradAgent] = {}

    async def _get_propagator() -> BackpropAgent:
        if propagator_factory is not None:
            return propagator_factory()
        if "default" not in _prop_cache:
            agent = BackpropAgent()
            await agent.abuild()
            _prop_cache["default"] = agent
        return _prop_cache["default"]

    async def _get_param_grad(kind: ParameterKind) -> ParameterGradAgent:
        if parameter_grad_factory is not None:
            return parameter_grad_factory(kind)
        if kind not in _pg_cache:
            agent = parameter_grad_for(kind)()
            await agent.abuild()
            _pg_cache[kind] = agent
        return _pg_cache[kind]

    root_path = tape.entries[0].agent_path
    downstream_grad: dict[str, TextualGradient] = {root_path: loss}
    node_output_grad: dict[str, TextualGradient] = {}

    # --- Pass 1: propagate + split, start-order --------------------------
    for entry in tape.entries:
        path = entry.agent_path
        g_in = downstream_grad.get(path, TextualGradient.null_gradient())
        if _is_null(g_in):
            continue
        agent = _deref(entry)
        prompt = _prompt_str(entry)
        propagator = await _get_propagator()

        try:
            g_out = await propagate(
                agent,
                prompt,
                entry.input,
                _response_of(entry),
                g_in,
                propagator,
            )
        except Exception as exc:
            raise RuntimeError(
                f"backward: propagate failed at {path!r}: {exc}"
            ) from exc

        g_out = _run_backward_hooks(agent, g_out)
        node_output_grad[path] = g_out
        await _emit_backward_event(entry, phase="propagate.end", grad=g_out)

        if entry.is_leaf:
            continue

        rule = _rule_for(agent)
        child_entries = tape.children_of(path)
        contributions = rule(entry, g_out, child_entries)
        null = TextualGradient.null_gradient()
        for child in child_entries:
            downstream_grad[child.agent_path] = contributions.get(
                child.agent_path, null
            )

    # --- Pass 2: per-parameter grads on leaves, reverse order -----------
    for entry in tape.entries_in_reverse():
        if not entry.is_leaf:
            continue
        g_out = node_output_grad.get(entry.agent_path)
        if g_out is None or _is_null(g_out):
            continue
        agent = _deref(entry)
        prompt = _prompt_str(entry)
        params = _params_for_agent(agent, user_params)
        if not params:
            continue

        await _backprop_leaf_params(
            entry, agent, prompt, g_out, params, _get_param_grad, sem
        )


async def _backprop_leaf_params(
    entry: TapeEntry,
    agent: Agent[Any, Any],
    prompt: str,
    g_out: TextualGradient,
    params: list[Parameter[Any]],
    get_param_grad: Callable[[ParameterKind], Awaitable[ParameterGradAgent]],
    sem: asyncio.Semaphore,
) -> None:
    input_value = entry.input
    output_value = _response_of(entry)

    async def _one(param: Parameter[Any]) -> None:
        grad_agent = await get_param_grad(param.kind)
        async with sem:
            try:
                grad = await parameter_grad(
                    param,
                    agent,
                    prompt,
                    input_value,
                    output_value,
                    g_out,
                    grad_agent,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"backward: parameter_grad failed at "
                    f"{entry.agent_path}.{param.path}: {exc}"
                ) from exc
        param.grad = grad
        await _emit_backward_event(
            entry, phase="param_grad.end", grad=grad, param_path=param.path
        )

    await asyncio.gather(*(_one(p) for p in params))


# ---------------------------------------------------------------------------
# Tape.backward convenience shim
# ---------------------------------------------------------------------------


async def _tape_backward(
    self: Tape,
    loss: TextualGradient,
    *,
    parameters: Iterable[Parameter[Any]] | None = None,
    propagator_factory: Callable[[], BackpropAgent] | None = None,
    parameter_grad_factory: (
        Callable[[ParameterKind], ParameterGradAgent] | None
    ) = None,
    concurrency: int = 4,
) -> None:
    await backward(
        self,
        loss,
        parameters=parameters,
        propagator_factory=propagator_factory,
        parameter_grad_factory=parameter_grad_factory,
        concurrency=concurrency,
    )


Tape.backward = _tape_backward  # type: ignore[attr-defined]


__all__ = [
    "SplitRule",
    "backward",
    "register_backward_rule",
]
