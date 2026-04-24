"""Memory-domain demo: extract beliefs from an assistant utterance
and store them in a typed ``MemoryStore[BeliefItem]``.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

    uv run python examples/memory_demo.py
"""

from __future__ import annotations

import asyncio

from operad.core.config import Sampling
from operad.agents import (
    BeliefItem,
    Beliefs,
    BeliefsInput,
    MemoryStore,
)

from _config import local_config


async def _main() -> None:
    cfg = local_config(sampling=Sampling(temperature=0.0, max_tokens=512))

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
    asyncio.run(_main())
