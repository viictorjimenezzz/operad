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

This module is intentionally empty until the §1 tasks land — it is a
placeholder so the import path exists and downstream tooling
(ImportPath resolution, cassettes, docs) can reference it.
"""

from __future__ import annotations

__all__: list[str] = []
