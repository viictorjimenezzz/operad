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

from operad.optim.ape import APEInput, APEOptimizer, APEOutput, CandidateGenerator
from operad.optim.backward import backward, register_backward_rule
from operad.optim.context import inference_mode, no_grad
from operad.optim.evo import EvoGradient
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
from operad.optim.loss import (
    CompositeLoss,
    CriticLoss,
    JSONShapeLoss,
    Loss,
    LossFromMetric,
)
from operad.optim.momentum import GradSummarizer, MomentumInput, MomentumTextGrad
from operad.optim.opro import (
    OPROAgent,
    OPROHistoryEntry,
    OPROInput,
    OPROOptimizer,
    OPROOutput,
)
from operad.optim.optimizer import Optimizer, ParamGroup
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
from operad.optim.rewrite import (
    REWRITE_AGENTS,
    CategoricalRewriter,
    ExampleListRewriter,
    FloatRewriter,
    RewriteAgent,
    RewriteRequest,
    RewriteResponse,
    RuleListRewriter,
    TextRewriter,
    apply_rewrite,
    rewriter_for,
)
from operad.optim.sgd import TextualGradientDescent
from operad.optim.tape import (
    Tape,
    TapeEntry,
    TapeObserver,
    enabled,
    tape,
)

__all__ = [
    "APEInput",
    "APEOptimizer",
    "APEOutput",
    "PARAMETER_GRAD_AGENTS",
    "REWRITE_AGENTS",
    "BackpropAgent",
    "CandidateGenerator",
    "CategoricalParameter",
    "CategoricalParameterGrad",
    "CategoricalRewriter",
    "CompositeLoss",
    "CriticLoss",
    "EvoGradient",
    "ExampleListParameter",
    "ExampleListParameterGrad",
    "ExampleListRewriter",
    "FloatParameter",
    "FloatParameterGrad",
    "FloatRewriter",
    "GradSummarizer",
    "JSONShapeLoss",
    "ListConstraint",
    "Loss",
    "LossFromMetric",
    "MomentumInput",
    "MomentumTextGrad",
    "NumericConstraint",
    "OPROAgent",
    "OPROHistoryEntry",
    "OPROInput",
    "OPROOptimizer",
    "OPROOutput",
    "Optimizer",
    "ParamGroup",
    "Parameter",
    "ParameterConstraint",
    "ParameterGradAgent",
    "ParameterGradInput",
    "ParameterGradOutput",
    "ParameterKind",
    "PropagateInput",
    "PropagateOutput",
    "RewriteAgent",
    "RewriteRequest",
    "RewriteResponse",
    "RuleListParameter",
    "RuleListParameterGrad",
    "RuleListRewriter",
    "Tape",
    "TapeEntry",
    "TapeObserver",
    "TextConstraint",
    "TextParameter",
    "TextParameterGrad",
    "TextRewriter",
    "TextualGradient",
    "TextualGradientDescent",
    "VocabConstraint",
    "apply_rewrite",
    "backward",
    "enabled",
    "inference_mode",
    "no_grad",
    "parameter_grad",
    "parameter_grad_for",
    "propagate",
    "register_backward_rule",
    "rewriter_for",
    "tape",
]
