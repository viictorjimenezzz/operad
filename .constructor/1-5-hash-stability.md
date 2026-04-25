# Make `hash_*` fingerprints environment-independent

## Goal
`OperadOutput.hash_*` fields are sold (INVENTORY §20) as content-addressable identities — identical inputs hash identically across machines. They don't, because `operad/utils/hashing.py:hash_json` uses `json.dumps(..., default=str)` and `str(datetime(...))` / `str(Path(...))` / `str(UUID(...))` embed timezone, locale, and platform-specific representations. The cassette-replay determinism story breaks downstream from this.

## Context
- `operad/utils/hashing.py` — central hash utilities used by `OperadOutput`, the cassette layer, the `Sweep` cell ID, and `freeze`/`thaw`.
- The fix isn't "always be deterministic" — it's "be deterministic for the things the doc promises are deterministic." Rendered prompts, configs, schemas, inputs.

## Scope

**In scope:**
- `operad/utils/hashing.py` — replace the `default=str` fallback with a typed canonicalizer that produces stable representations for the common non-JSON-native types (datetime → ISO8601 UTC, Path → POSIX, UUID → str, Decimal → str, bytes → base64, set → sorted list, BaseModel → `model_dump(mode="json")`). Reject types that have no deterministic representation with a clear error rather than silent `default=str`.
- Audit every hash producer in the repo (grep `hash_json`, `hash_content`, `hash_prompt`, `hash_config`, `hash_input`, `hash_output_schema`, `hash_graph`) and confirm they use the new canonicalizer.
- Tests under `tests/utils/` that hash a struct containing each special-cased type from two fake "machines" with different locale/timezone settings and assert equality.

**Out of scope:**
- Hashing inside `freeze`/`thaw` artifact format — only the digest, not the file format.
- Recomputing existing cassette IDs (cassettes are content-keyed; old cassettes will need regeneration but that's user-facing; flag it in the task summary).
- Changing what fields are hashed (that's a contract; only fix how they're serialized).

**Owned by sibling iter-1 tasks — do not modify:**
- `operad/optim/*`, `operad/train/*`, `operad/runtime/*`, `operad/data/*`, `operad/core/agent.py`, `examples/`.

## Implementation hints
- Pydantic's `model_dump(mode="json")` produces deterministic JSON; lean on it.
- `json.dumps(sort_keys=True, separators=(",", ":"))` is the right baseline.
- Document in the docstring exactly which types are stable and which raise.
- If a previously-hashable type now raises, `RewriteAgent`-style: include the type name in the error so users can register a custom canonicalizer.

## Acceptance
- Cross-environment determinism test passes (mock `time.tzname`, `locale.getdefaultlocale()`).
- Existing tests pass; cassette-replay tests still work for the in-tree fixtures.
- Note in the PR description that any *recorded* cassettes outside the repo will need re-recording.
