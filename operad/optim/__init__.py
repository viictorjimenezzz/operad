"""`operad.optim` — the training / optimization layer.

This package extends the PyTorch analogy with a full optimizer stack
on top of `operad.Agent`: first-class `Parameter` handles over mutable
agent state (role, task, rules, examples, sampling knobs); a
textual-gradient propagation algorithm (`backward()`) that walks the
runtime `AgentGraph`; and a fleet of `Optimizer` subclasses that apply
those gradients via LLM-driven rewrite agents.

The headline surface mirrors `torch.optim`:

    optimizer = TextualGradientDescent(agent.parameters(), lr=1.0)
    scheduler = CosineExplorationLR(optimizer, T_max=10)

    with operad.optim.tape() as tape:
        out = await agent(x)
    loss = await loss_fn(out.response, target)
    await tape.backward(loss)
    await optimizer.step()

See `operad/optim/README.md` for the full design; see
`.context/NEXT_ITERATION.md` for the north-star proposal; see
`.construct/optim/*.md` for the iteration-by-iteration implementation
plan.

Wave 1 slot 1-1 ships the `Parameter` data spine; later waves add
`Agent.parameters()`, losses, backward, optimizers, and the trainer.
"""

from __future__ import annotations

from operad.optim.grad_agent import (
    PARAMETER_GRAD_AGENTS,
    BackpropAgent,
    CategoricalParameterGrad,
    ExampleListParameterGrad,
    FloatParameterGrad,
    ParameterGradAgent,
    ParameterGradInput,
    ParameterGradOutput,
    PropagateInput,
    PropagateOutput,
    RuleListParameterGrad,
    TextParameterGrad,
    parameter_grad,
    parameter_grad_for,
    propagate,
)
from operad.optim.parameter import (
    CategoricalParameter,
    ExampleListParameter,
    FloatParameter,
    ListConstraint,
    NumericConstraint,
    Parameter,
    ParameterConstraint,
    ParameterKind,
    RuleListParameter,
    TextConstraint,
    TextParameter,
    TextualGradient,
    VocabConstraint,
)

__all__ = [
    "PARAMETER_GRAD_AGENTS",
    "BackpropAgent",
    "CategoricalParameter",
    "CategoricalParameterGrad",
    "ExampleListParameter",
    "ExampleListParameterGrad",
    "FloatParameter",
    "FloatParameterGrad",
    "ListConstraint",
    "NumericConstraint",
    "Parameter",
    "ParameterConstraint",
    "ParameterGradAgent",
    "ParameterGradInput",
    "ParameterGradOutput",
    "ParameterKind",
    "PropagateInput",
    "PropagateOutput",
    "RuleListParameter",
    "RuleListParameterGrad",
    "TextConstraint",
    "TextParameter",
    "TextParameterGrad",
    "TextualGradient",
    "VocabConstraint",
    "parameter_grad",
    "parameter_grad_for",
    "propagate",
]
