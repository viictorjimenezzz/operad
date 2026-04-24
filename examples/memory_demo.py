"""Memory-domain demo: extract beliefs from an assistant utterance
and store them in a typed ``MemoryStore[BeliefItem]``.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

Run:
    uv run python examples/memory_demo.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from operad.core.config import Sampling
from operad.agents import (
    BeliefItem,
    Beliefs,
    BeliefsInput,
    MemoryStore,
)

from _config import local_config, server_reachable

_SCRIPT = "memory_demo.py"


async def main(offline: bool = False) -> None:
    cfg = local_config(sampling=Sampling(temperature=0.0, max_tokens=2048))
    print(f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}")
    if offline:
        print(f"[{_SCRIPT}] --offline not supported for this example (needs a real model); exiting 0 as no-op.")
        return
    if not server_reachable(cfg.host):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} — start llama-server or pass --offline",
            file=sys.stderr,
        )
        raise SystemExit(1)

    extractor = Beliefs(config=cfg)
    await extractor.abuild()

    utterance = (
        "Climate change significantly impacts marine biodiversity. "
        "Rising sea temperatures drive coral bleaching and shifting fish "
        "migration routes."
    )

    result = (
        await extractor(
            BeliefsInput(
                current_beliefs_json="[]",
                current_beliefs_summary="",
                turn_id=1,
                utterance=utterance,
            )
        )
    ).response

    store: MemoryStore[BeliefItem] = MemoryStore(schema=BeliefItem)
    for op in result.operations:
        if op.op == "add" and op.item is not None:
            store.add(op.item)

    print(f"extracted {len(store.all())} beliefs:")
    for b in store.all():
        print(f"  - [{b.topic_key}] {b.claim_text}  salience={b.salience_score:.2f}")

    high_salience = store.filter(lambda b: b.salience_score > 0.7)
    print(f"\n{len(high_salience)} with salience > 0.7:")
    for b in high_salience:
        print(f"  - [{b.topic_key}] {b.claim_text}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
