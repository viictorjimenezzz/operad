# Phase 2 · Stream F — Algorithms: VerifierLoop, SelfRefine, Debate, Evolutionary

**Goal.** Ship the iterative algorithms named in VISION §7. Each is a
plain class in `operad/algorithms/`, not an Agent.

**Owner.** One agent (may split into F-1 = VerifierLoop + SelfRefine,
F-2 = Debate + Evolutionary if scope warrants).
**Depends on.** Stream B (Evolutionary needs `Agent.state()` / `clone()`);
`.conductor/feature-mutation-ops.md` (Evolutionary imports Ops from
`operad/utils/ops.py`).
**Addresses:** C-2, C-3.

> **Note — mutations relocated.** The originally planned
> `operad/algorithms/mutations.py` has been superseded by
> `.conductor/feature-mutation-ops.md`, which houses Ops in
> `operad/utils/ops.py`. Do NOT create `algorithms/mutations.py`;
> import from `operad.utils.ops` instead.

---

## Scope

### Files you will create
- `operad/algorithms/verifier_loop.py`
- `operad/algorithms/self_refine.py`
- `operad/algorithms/debate.py`
- `operad/algorithms/evolutionary.py`
- `tests/test_verifier_loop.py`, `test_self_refine.py`,
  `test_debate.py`, `test_evolutionary.py`.
- `examples/evolutionary_demo.py`.

### Files you do NOT create (relocated)
- ~~`operad/algorithms/mutations.py`~~ — see
  `.conductor/feature-mutation-ops.md`. Ops live in
  `operad/utils/ops.py`.

### Files you will edit
- `operad/algorithms/__init__.py` — re-exports.
- `operad/__init__.py` — re-exports.

### Files to leave alone
- `operad/core/`. Algorithms never reach into core.
- `operad/agents/`. Compose existing leaves; don't add new ones here
  (Stream E owns that).

---

## Design direction

### `VerifierLoop`

```python
class VerifierLoop(Generic[In, Out]):
    def __init__(
        self,
        generator: Agent[In, Out],
        critic: Agent[Candidate[In, Out], Score],
        *,
        threshold: float = 0.8,
        max_iter: int = 3,
    ) -> None: ...

    async def run(self, x: In) -> Out:
        last = None
        for _ in range(self.max_iter):
            last = await self.generator(x)
            score = await self.critic(Candidate(input=x, output=last))
            if score.score >= self.threshold:
                return last
        return last
```

Plain, no randomisation (temperature on the generator does that).

### `SelfRefine`

```python
class SelfRefine(Generic[In, Out]):
    def __init__(
        self,
        generator: Agent[In, Out],
        reflector: Agent[ReflectionInput, Reflection],
        refiner: Agent[RefinementInput, Out],
        *,
        max_iter: int = 2,
    ) -> None: ...

    async def run(self, x: In) -> Out:
        current = await self.generator(x)
        for _ in range(self.max_iter):
            r = await self.reflector(ReflectionInput(
                original_request=str(x), candidate_answer=str(current)))
            if not r.needs_revision:
                return current
            current = await self.refiner(RefinementInput(
                request=str(x), prior=current, critique=r))
        return current
```

Reuses `Reflection` from Stream E.

### `Debate`

N proposers, one or more critique rounds, a synthesiser. Keep it
minimal:

```python
class Debate(Generic[In, Out]):
    def __init__(
        self,
        proposers: list[Agent[In, Proposal]],
        critic: Agent[DebateTurn, Critique],
        synthesizer: Agent[DebateRecord, Out],
        *,
        rounds: int = 1,
    ) -> None: ...

    async def run(self, x: In) -> Out:
        proposals = await asyncio.gather(*(p(x) for p in self.proposers))
        record = DebateRecord(request=x, proposals=proposals, critiques=[])
        for _ in range(self.rounds):
            critiques = await asyncio.gather(
                *(self.critic(DebateTurn(record=record, focus=p)) for p in proposals)
            )
            record.critiques.extend(critiques)
        return await self.synthesizer(record)
```

Types (`Proposal`, `DebateTurn`, `Critique`, `DebateRecord`) live in
`debate.py` as Pydantic models.

### `Evolutionary`

North-star. Depends on Stream B.

```python
class Evolutionary(Generic[In, Out]):
    def __init__(
        self,
        seed: Agent[In, Out],
        mutations: list[Mutation],
        metric: Metric,
        dataset: list[tuple[In, Out]],
        *,
        population_size: int = 8,
        generations: int = 4,
    ) -> None: ...

    async def run(self) -> Agent[In, Out]:
        population = [self._mutate(self.seed.clone()) for _ in range(self.population_size)]
        for gen in range(self.generations):
            await asyncio.gather(*(a.abuild() for a in population))
            reports = await asyncio.gather(
                *(evaluate(a, self.dataset, [self.metric]) for a in population)
            )
            scored = sorted(
                zip(reports, population),
                key=lambda pr: -pr[0].summary[self.metric.name],
            )
            survivors = [a for _, a in scored[: self.population_size // 2]]
            population = survivors + [self._mutate(a.clone()) for a in survivors]
        return population[0]
```

`_mutate` picks a random mutation from `self.mutations` and applies
it.

### Mutation ops

Ops are defined in `operad/utils/ops.py` — see
`.conductor/feature-mutation-ops.md`. Evolutionary imports from there:

```python
from operad.utils.ops import Op, AppendRule, SetTemperature, ...
```

Do NOT redefine Ops or the dotted-path resolver here.

---

## Tests

- `VerifierLoop`: FakeLeaf generator improving each call + FakeLeaf
  critic with scripted scores. Loop exits early on threshold.
- `SelfRefine`: terminates on `needs_revision=False`.
- `Debate`: N proposers run; critiques propagate; synthesiser sees all.
- `Evolutionary`: with trivial mutations (from
  `operad.utils.ops`) and a toy deterministic metric over a 3-row
  dataset, the seed evolves offline (FakeLeaf-backed).

---

## Acceptance

- `uv run pytest tests/` green.
- `examples/evolutionary_demo.py` shows a seed agent being evolved
  against a 5-row dataset with deterministic metrics (offline-only).

---

## Watch-outs

- Keep algorithm APIs distinct. Don't force `Evolutionary.run()` to
  take an input `x` — its output is a new Agent, not an `Out`.
- Bound concurrency via the slot registry, not hand-rolled semaphores
  inside algorithms.
- Mutations must not break class-attribute contracts. A mutation that
  turns `rules` into a non-list should be impossible by construction.
- `SelfRefine`'s reuse of Stream E types means you rebase after E.
