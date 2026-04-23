# Phase 2 · Stream L — Integration tests for more backends + offline edge cases

**Goal.** Add opt-in integration tests for OpenAI, Ollama, and LM
Studio (matching the existing llamacpp one). Add offline edge-case
tests that the current suite misses.

**Owner.** One agent.
**Depends on.** Stream A (error-path tests benefit from the new
`BuildReason` literals).
**Addresses:** D-3.

---

## Scope

### Files you will create
- `tests/integration/test_openai.py`
- `tests/integration/test_ollama.py`
- `tests/integration/test_lmstudio.py`
- `tests/test_errors.py` — offline error-path coverage.
- `tests/test_deep_nesting.py` — 10+ level composite tree builds and
  exports.

### Files you will edit
- `tests/conftest.py` — only if a shared helper genuinely helps.
- `README.md` — document all `OPERAD_INTEGRATION=<name>` options and
  required env vars per backend.

### Files to leave alone
- Source files. This stream is read-only against `operad/`.

---

## Design direction

### Integration test pattern

Mirror `tests/integration/test_llamacpp.py`. Each test:

1. Skips unless the correct `OPERAD_INTEGRATION` env var is set.
2. Reads backend-specific env vars (`OPENAI_API_KEY`,
   `OPERAD_OLLAMA_HOST`, `OPERAD_LMSTUDIO_HOST`, etc.).
3. Builds a small typed Agent (a single `Reasoner` with tiny `Question`
   / `Answer` schema).
4. Runs one structured-output call.
5. Asserts on type and non-empty fields — never on content.

Example skeleton:

```python
pytestmark = pytest.mark.integration

@pytest.mark.skipif(
    os.environ.get("OPERAD_INTEGRATION") != "openai",
    reason="set OPERAD_INTEGRATION=openai to enable",
)
async def test_openai_structured_output():
    api_key = os.environ["OPENAI_API_KEY"]   # let KeyError surface if absent
    cfg = Configuration(
        backend="openai",
        model=os.environ.get("OPERAD_OPENAI_MODEL", "gpt-4o-mini"),
        api_key=api_key,
    )
    agent = Reasoner(config=cfg, input=Question, output=Answer)
    await agent.abuild()
    out = await agent(Question(text="What is 2 + 2?"))
    assert isinstance(out, Answer)
    assert out.answer.strip()
```

### Offline edge-case tests

`tests/test_errors.py`:
- Leaf raises mid-`forward` — `Parallel` surfaces the first error.
- `Parallel` with one failing child cancels siblings (or the observable
  behaviour today, document what it is).
- `Pipeline` stage-2 raises — stage-3 is not called.
- `Pipeline` with a type mismatch between stages fails `build()` with
  `input_mismatch`.
- `Agent.invoke` before `build()` raises `BuildError("not_built", ...)`.

`tests/test_deep_nesting.py`:
- Programmatically build a 10-level nested composite (e.g. a
  `Pipeline` of `Pipeline`s). Confirm `build()` succeeds and Mermaid
  export produces a valid graph.
- A shared child across two parents emits one `warnings.warn` (after
  Stream A).

---

## Tests

This stream is the tests — the acceptance criteria is that each new
test behaves as expected offline, and that the integration tests
only run when their env var is set.

---

## Acceptance

- `uv run pytest tests/` green (offline suite).
- `OPERAD_INTEGRATION=openai OPENAI_API_KEY=... uv run pytest tests/integration -v`
  runs the openai test successfully (when env is provided).
- Same for `ollama` and `lmstudio`.
- `README.md` lists every `OPERAD_INTEGRATION` option with required
  env vars.

---

## Watch-outs

- Never commit real API keys. Tests read from env only.
- Keep integration tests tiny — one happy path each. Don't test edge
  cases against real models; that's what offline tests are for.
- If an SDK is missing, skip with `pytest.importorskip` (ollama may
  not be installed in dev).
- Integration tests must NOT run in CI by default. The opt-in env var
  is the gate; don't add a marker that flips default-on.
