# Add a postcard-sized hello-world example

## Goal
A newcomer's first contact with the library today is `examples/01_composition_research_analyst.py` — Pydantic models, `Parallel({...})`, `combine=lambda`, asyncio boilerplate. That's a fine third example, not a first one. Add `examples/00_hello.py`: 15-25 lines, one leaf, one invocation, no `Configuration` ceremony, no `Parallel`, no tape, no Trainer. Call it from `scripts/verify.sh` so it stays alive.

## Context
- `examples/` currently has four scripts (`01_..` through `04_..`) per the recent commit history.
- The README's two-minute tour already shows a `Parallel` setup — that's the medium difficulty. We want a step below it.

## Scope

**In scope:**
- `examples/00_hello.py` — single-leaf agent, single `await agent(x)` call, prints the response. Ideally runs against `llamacpp` by default but supports `--offline` (use a `FakeLeaf` or `RubricCritic`-style fake) so `verify.sh` can exercise it.
- `examples/README.md` — add a one-line entry pointing to it as the recommended starting point. Reorder so 00 is first.
- `scripts/verify.sh` — invoke the offline mode of the new example.

**Out of scope:**
- Modifying any of the existing 01-04 examples.
- Adding a Trainer/optimizer example (the benchmark task in iteration 4 covers that).
- Changing the top-level `README.md` (do that in iteration 4 once we have the benchmark to point at too).

**Owned by sibling iter-1 tasks — do not modify:**
- `operad/**`, `apps/**`, `tests/**`.

## Implementation hints
- 15 lines is the upper bound. Use `Reasoner` or a fresh `Agent` subclass with three-line `input`/`output`/`role`.
- The offline path can use `FakeLeaf` or override `forward()` to return a canned `Out` so the script demonstrates shape without a server.
- Comment density: zero. The names should carry the meaning.
- End with `print(out.response)` — no metadata noise on first contact.

## Acceptance
- `python examples/00_hello.py --offline` exits 0.
- `bash scripts/verify.sh` includes the new example and still passes.
- No more than ~25 lines including blank lines and the two model classes.
