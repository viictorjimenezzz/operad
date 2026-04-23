"""Talker: a safeguarded, persona-styled conversational composition.

Wiring::

    Safeguard(Utterance -> SafeguardVerdict) -> dispatch-on-label
        allow -> TurnTaker(Utterance -> TurnChoice) -> Persona(Utterance -> StyledUtterance)
        block -> RefusalLeaf(SafeguardVerdict -> StyledUtterance)

The block path short-circuits: when ``Safeguard`` returns
``label="block"``, the model is never called again — ``RefusalLeaf``
emits a fixed polite template without touching a provider.

**On the dispatch.** The canonical way to branch on a ``Literal`` field
is the ``Switch`` composite (Stream E). It is not merged at the time
of this writing, so ``Talker`` dispatches inside its own ``forward``
and uses the ``_TRACER`` context var to ensure both branches are
visited during ``build()`` (so the captured graph records both edges
and Mermaid renders the block branch too). When ``Switch`` lands, this
becomes ``Switch(selector=self.safeguard, allow=..., block=...)`` and
the ``_TRACER`` escape hatch goes away. TODO(stream-E).

**On the TurnTaker wiring.** ``TurnTaker`` outputs ``TurnChoice`` and
``Persona`` consumes ``Utterance``; they do not compose as a literal
``Pipeline``. In v1 we call ``TurnTaker`` for its observable side
(building-block for subclasses that want to inspect the choice) and
then invoke ``Persona`` on the original utterance. Richer wiring —
e.g. dispatching on ``TurnChoice.action`` — is a Stream-E follow-up.
"""

from __future__ import annotations

from ...core.agent import _TRACER, Agent
from ...core.config import Configuration
from .components import Persona, Safeguard, TurnTaker
from .schemas import SafeguardVerdict, StyledUtterance, Utterance


# --- refusal leaf ------------------------------------------------------------

_REFUSAL_TEMPLATE = (
    "I can't help with that request. If you have a different question, "
    "I'd be glad to try."
)


class RefusalLeaf(Agent[SafeguardVerdict, StyledUtterance]):
    """Returns a fixed polite refusal without calling a model.

    Overrides ``forward`` so ``build()`` does not wire strands for this
    leaf. Accepts ``config=None``.
    """

    input = SafeguardVerdict
    output = StyledUtterance

    def __init__(self) -> None:
        super().__init__(
            config=None, input=SafeguardVerdict, output=StyledUtterance
        )

    async def forward(self, x: SafeguardVerdict) -> StyledUtterance:  # type: ignore[override]
        return StyledUtterance(response=_REFUSAL_TEMPLATE)


# --- composition -------------------------------------------------------------


class Talker(Agent[Utterance, StyledUtterance]):
    """Safeguarded conversational agent: Safeguard → (TurnTaker → Persona | Refusal)."""

    input = Utterance
    output = StyledUtterance

    def __init__(self, *, config: Configuration) -> None:
        super().__init__(config=None, input=Utterance, output=StyledUtterance)
        self.safeguard = Safeguard(config=config)
        self.turn_taker = TurnTaker(config=config)
        self.persona = Persona(config=config)
        self.refusal = RefusalLeaf()

    async def forward(self, x: Utterance) -> StyledUtterance:  # type: ignore[override]
        verdict = (await self.safeguard(x)).response

        # Trace-time: visit every branch so `build()` records both edges
        # and type-checks the block path. This replaces Stream E's Switch.
        if _TRACER.get() is not None:
            await self.turn_taker(x)
            await self.persona(x)
            return (await self.refusal(verdict)).response

        if verdict.label == "block":
            return (await self.refusal(verdict)).response
        await self.turn_taker(x)
        return (await self.persona(x)).response
