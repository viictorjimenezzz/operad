# Feature · Cassette-based test replay

VCR-style recording and playback for LLM calls so tests can run
deterministically offline after a one-time recording pass. Huge win
for multi-agent development, CI stability, and incremental prompt
tuning.

**Covers Part-3 item.** #3 (cassette-based test replay).

---

## Required reading

`METAPROMPT.md`, `ISSUES.md`, `VISION.md` §6, and:
- `tests/conftest.py` — existing `FakeLeaf` pattern; cassettes are
  the missing middle between FakeLeaf (hand-written) and live
  integration tests.
- `.conductor/feature-operad-output.md` — cassettes key off the
  hash fields.

---

## Proposal sketch

### What a cassette is

A JSONL file keyed by a deterministic tuple:

```
key = (hash_model, hash_prompt, hash_input)
```

Each line:

```json
{
  "key": "<16-char hex>",
  "hash_model": "...",
  "hash_prompt": "...",
  "hash_input": "...",
  "response_json": "...",
  "recorded_at": 1713984000.0
}
```

Cassettes live alongside tests: `tests/cassettes/<test_name>.jsonl`.

### Recording vs. replaying

A pytest fixture controls the mode:

```python
@pytest.fixture
def cassette(request):
    """Use .jsonl cassettes to fake LLM calls.

    Set OPERAD_CASSETTE=record to re-record (one-time, against a
    real backend). Default is replay; a missing key raises.
    """
    mode = os.environ.get("OPERAD_CASSETTE", "replay")
    path = Path(request.fspath).parent / "cassettes" / f"{request.node.name}.jsonl"
    with cassette_context(path, mode=mode):
        yield
```

Under the hood, `cassette_context` patches the default leaf
`forward` (or the strands model resolution, whichever is cleaner —
investigate) to check the cassette before hitting the network. On
cache miss in replay mode, raise loudly. On record mode, execute,
store, and return.

### Patch point

Two candidates — investigate which is cleaner:

1. **At `Agent.forward`.** Wrap the default leaf `forward` to
   intercept calls. Doesn't touch strands internals; simple.
2. **At `operad.models.resolve_model`.** Return a cassette-backed
   model object. Cleaner separation of concerns; more work.

Start with Option 1. Move to Option 2 only if needed.

---

## Research directions

- **Hash keys.** Use the same `hash_*` fields from
  `feature-operad-output.md`. Cassettes become portable across
  refactors as long as the prompt rendering is stable.
- **Non-determinism.** LLMs with temperature > 0 are not reproducible
  even against the same prompt. Cassette recordings are therefore
  *snapshots*, not ground truth. Document this.
- **Expiry.** Should cassettes expire? Suggest `recorded_at` +
  `OPERAD_CASSETTE_TTL_DAYS` env var. For the first version: no
  expiry; manual re-record.
- **Secret-leakage.** Cassettes may contain model outputs with
  echoed prompt content — which may contain API keys if users embed
  them. Never include the rendered `hash_prompt` preimage in the
  file; only the hash.
- **Multi-backend keys.** If `hash_model` differs, cassettes from
  openai and llamacpp don't collide even for the same prompt. Good.

---

## Integration & compatibility requirements

- **Respect existing `FakeLeaf`.** Cassettes and FakeLeaf coexist;
  neither replaces the other. FakeLeaf is for "no LLM involved at
  all" unit tests; cassettes are for "this test should behave
  deterministically after recording a real LLM response once".
- **Do not modify production code paths.** The cassette layer is
  pytest-side only. Production `Agent.forward` stays as-is.
- **Use `hash_*` fields from `feature-operad-output.md`.** If that
  feature hasn't merged, define a temporary shared hashing helper in
  `operad/testing/hashing.py` and migrate when OperadOutput lands.
- **Opt-in per test.** A fixture is better than a global
  monkeypatch. Tests that don't use `cassette` are unaffected.
- **CI stays offline.** Recording is a dev-only operation. In CI,
  `OPERAD_CASSETTE=replay` (the default) is enforced; missing keys
  fail the test.

---

## Acceptance

- `uv run pytest tests/` green.
- `OPERAD_CASSETTE=record OPERAD_INTEGRATION=llamacpp uv run pytest tests/test_cassette_demo.py`
  (against a real model) populates a cassette file.
- Re-running without either env var (replay default) passes using
  the cassette, no network involved.
- Deleting a cassette line and re-running in replay mode fails
  loudly with "missing cassette key for <hash>".
- A documented recipe in `CLAUDE.md` explains the workflow.

---

## Watch-outs

- Do NOT attempt to intercept inside `strands.Agent.invoke_async`
  from the outside — it is a moving target. Patch at
  `operad.core.agent.Agent.forward` instead.
- Do NOT auto-record on cache miss in CI. Replay mode must fail.
- Cassette files are commits — check that they don't contain
  secrets before committing (add a `pre-commit` hint in
  `CLAUDE.md`).
- Keep cassette files small; one per test keeps diffs readable.
