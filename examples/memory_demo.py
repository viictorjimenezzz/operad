"""Memory-domain demo: extract beliefs from a two-turn conversation
and store them in a typed ``MemoryStore[Belief]``.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

    uv run python examples/memory_demo.py
"""

from __future__ import annotations

import asyncio

from operad.agents import (
    Belief,
    BeliefExtractor,
    Conversation,
    MemoryStore,
    Turn,
)

from _config import local_config


async def _main() -> None:
    cfg = local_config(temperature=0.0, max_tokens=512)

    extractor = BeliefExtractor(config=cfg)
    await extractor.abuild()

    conversation = Conversation(
        turns=[
            Turn(speaker="user", text="I live in Berlin and I work as an ML researcher."),
            Turn(speaker="user", text="I usually prefer tea over coffee."),
        ]
    )

    beliefs = (await extractor(conversation)).response

    store: MemoryStore[Belief] = MemoryStore(schema=Belief)
    for b in beliefs.items:
        store.add(b)

    print(f"extracted {len(store.all())} beliefs:")
    for b in store.all():
        print(f"  - ({b.subject}, {b.predicate}, {b.object})  conf={b.confidence:.2f}")

    high_conf = store.filter(lambda b: b.confidence > 0.7)
    print(f"\n{len(high_conf)} with confidence > 0.7:")
    for b in high_conf:
        print(f"  - ({b.subject}, {b.predicate}, {b.object})")


if __name__ == "__main__":
    asyncio.run(_main())
