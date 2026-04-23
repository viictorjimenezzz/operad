# Polish · small fixes: config hash, leaf-root init, sandbox test warning

**Addresses.** E-5 + E-6 + E-10 (ISSUES.md) +
`TODO_CONFIG_HASH_AUTH` + `TODO_LEAF_ROOT_INIT_SEMANTICS` +
`TODO_SANDBOX_TIMEOUT_WARNING` in `missing.py`.

Three small, unrelated fixes rolled into one PR because each is too
small for its own brief, and they touch different files with zero
merge conflict risk.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-5, §E-6, §E-10.
- `operad/core/output.py`, `operad/core/build.py`,
  `tests/test_sandbox.py`.

---

## Part 1 — strip auth from `hash_config`

`hash_config` today excludes `api_key` but hashes `host` verbatim.
Hosts can carry credentials (`user:pass@host:port`).

### Change

```python
# operad/core/output.py
def hash_config(config: Configuration | None) -> str:
    if config is None:
        return ""
    dumped = config.model_dump(mode="json", exclude={"api_key"})
    host = dumped.get("host")
    if isinstance(host, str) and "@" in host:
        dumped["host"] = host.rsplit("@", 1)[-1]   # strip user:pass@
    return hash_json(dumped)
```

Test: `hash_config(Configuration(..., host="u:p@127.0.0.1:9000"))`
equals `hash_config(Configuration(..., host="127.0.0.1:9000"))`.

---

## Part 2 — Leaf-root output-type validation at build()

`abuild_agent` (operad/core/build.py:343) skips `_trace` when the root
is a default-forward leaf with no children. Correct for graph capture,
but it means the declared `output` type is never verified at build
time — the first `invoke` is where a mismatch would surface.

### Change

When skipping `_trace` for a leaf root, perform a cheap sentinel-output
validation:

```python
# operad/core/build.py, inside abuild_agent
if root._children or not _is_default_forward(root):
    # ... existing trace path ...
else:
    # Leaf root: no trace, but confirm output class is a Pydantic model
    # we can round-trip. No LLM contact; no strands init yet.
    try:
        _ = root.output.model_construct()
    except Exception as e:
        raise BuildError(
            "output_mismatch",
            f"leaf root {type(root).__name__}.output ({root.output.__name__}) "
            f"is not a usable Pydantic model: {e}",
            agent=type(root).__name__,
        ) from e
```

Test: a leaf root with a malformed output class fails `build()` at
build time, not at first invoke.

---

## Part 3 — fix AsyncMock warning in `test_sandbox.py`

`tests/test_sandbox.py::test_timeout_kills_process` runs but emits:

```
RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
```

Find the AsyncMock site, ensure the coroutine is consumed (await it,
`.assert_awaited()`, or structure the test so the mocked call is
actually awaited inside the code under test). Silence the warning
legitimately — do NOT add a `filterwarnings` ignore.

---

## Scope

- Edit: `operad/core/output.py` (Part 1).
- Edit: `operad/core/build.py` (Part 2).
- Edit: `tests/test_sandbox.py` (Part 3).
- New or edited tests:
  - `tests/test_operad_output.py` — auth-stripping test (Part 1).
  - `tests/test_build.py` — leaf-root build validation (Part 2).

Do NOT:
- Expand scope. Each part is a tight fix. If you find a fourth thing
  while in the file, note it in `ISSUES.md` and move on.

---

## Acceptance

- `uv run pytest tests/` green — and the previous RuntimeWarning is
  gone (check with `-W error::RuntimeWarning`).
- Part 1 test passes: hosts with and without auth hash identically.
- Part 2 test passes: malformed leaf-root output fails at build time.

---

## Watch-outs

- Part 1: host formats vary. `user:pass@host:port` is the common one;
  also handle `scheme://user:pass@host/path`. Don't try to parse
  URLs yourself — for v1, just strip the `user:pass@` prefix pattern.
  Documents the limitation.
- Part 2: `model_construct()` on a Pydantic model with required
  fields that default to `None` usually works. Don't over-validate
  — the goal is a cheap smoke test, not full schema verification.
- Part 3: don't suppress the warning — fix the root cause. If the
  mock is genuinely needed in a way that leaves a coroutine unawaited,
  switch to `MagicMock` with a `return_value=Future()`.
