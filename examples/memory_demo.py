"""Memory-domain demo: extract beliefs from a two-turn conversation
and store them in a typed ``MemoryStore[Belief]``.

    OPERAD_LLAMACPP_HOST=127.0.0.1:8080 \\
    OPERAD_LLAMACPP_MODEL=qwen2.5-7b-instruct \\
    uv run python examples/memory_demo.py

Matches the ``examples/parallel.py`` style: reads llama-server endpoint
and model from environment variables; no offline fallback.
"""

from __future__ import annotations

import asyncio
import os

from operad import (
    Belief,
    BeliefExtractor,
    Configuration,
    Conversation,
    MemoryStore,
    Turn,
)


def _cfg(model: str) -> Configuration:
    return Configuration(
        backend="llamacpp",
        host=os.environ.get("OPERAD_LLAMACPP_HOST", "127.0.0.1:8080"),
        model=model,
        temperature=0.0,
        max_tokens=512,
    )


async def _main() -> None:
    model = os.environ.get("OPERAD_LLAMACPP_MODEL", "default")
    cfg = _cfg(model)

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
