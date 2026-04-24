# examples/

Every executable in this directory accepts `--offline` so `argparse`
doesn't vary between scripts; the flag is only materially honoured by
examples that can run without an LLM. Network-required examples print
a one-line banner with `backend/host/model`, probe reachability, and
exit cleanly (non-zero with a message, no traceback) if the server is
not up. With `--offline` they exit 0 as a no-op.

`_config.py` centralises the canonical local target; override with
`OPERAD_LLAMACPP_HOST` / `OPERAD_LLAMACPP_MODEL`.

| Script | Needs LLM? | What it shows |
| --- | --- | --- |
| `best_of_n.py` | yes | `BestOfN` algorithm picking the best of 3 Reasoner candidates via a Critic. |
| `custom_agent.py` | no (`--offline`) | Minimal user-defined `Agent[In, Out]` leaf; offline path swaps in a canned stub. |
| `eval_loop.py` | no | `evaluate(agent, dataset, metrics)` over a canned agent and five rows. |
| `evolutionary_demo.py` | no | `Evolutionary` algorithm mutating a seed toward a target rule count. |
| `federated.py` | yes (+ OpenAI) | One graph, two backends, independent slot budgets. |
| `memory_demo.py` | yes | `BeliefExtractor` populating a typed `MemoryStore[Belief]`. |
| `mermaid_export.py` | no | Build a small composite and print its Mermaid graph. |
| `observer_demo.py` | no | Two-stage Pipeline with JSONL + trace observers. |
| `parallel.py` | yes | Fan four specialised Reasoners out over a `Parallel` root. |
| `pipeline.py` | yes | Three-stage `Pipeline` (extract -> plan -> evaluate). |
| `pr_reviewer.py` | yes | `PRReviewer` composite against a synthetic diff. |
| `react.py` | yes | Standalone `ReAct` (reason -> act -> observe -> evaluate). |
| `router_switch.py` | yes | `Router` + `Switch` dispatching to typed branches. |
| `sandbox_add_tool.py` | no | Helper module exposing `AddTool` for the sandbox examples. |
| `sandbox_pool_demo.py` | no | Concurrent tool calls through a reusable `SandboxPool`. |
| `sandbox_tooluser.py` | no | Wrap a `Tool` in `SandboxedTool` and call it. |
| `sweep_demo.py` | no | `Sweep` running a 2x2 parameter grid in parallel. |
| `talker.py` | yes | End-to-end `Talker`: safeguard -> turn-taker -> persona or refusal. |

Run the offline surface in one shot:

```bash
bash scripts/verify.sh
```
