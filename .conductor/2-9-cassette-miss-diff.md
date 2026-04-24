# 2 · 9 — Cassette-miss diff: name the differing hash

**Addresses.** O5 (when a cassette lookup misses, print which hash
component changed).

**Depends on.** 1-1-restructure (cassette lives at
`operad/utils/cassette.py` post-move).

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §6.
- `operad/testing/cassette.py` *(pre-1-1)* / `operad/utils/cassette.py`
  *(post-1-1)* — `cassette_context`, `CassetteMiss`, `_compose_key`,
  `_load`, `_append`. The current miss message is a flat hash string.
- `operad/utils/hashing.py` (post-1-1) — `hash_model`, `hash_prompt`,
  `hash_input`. These are the three segments of the cassette key.

---

## Proposal

Today, a cassette miss reads:

```
CassetteMiss: missing cassette key for 3abc12ef...
(model=..., prompt=..., input=...) at tests/cassettes/test_foo.jsonl
```

The user is told what's missing but not *why*. In practice, the cause
is almost always one of:

- the **prompt** changed (role/task/rules/examples edited, schema
  re-rendered, renderer swapped from xml to markdown, …);
- the **input** changed (a test fixture mutation);
- the **model/config** changed (backend swap, temperature tweak, new
  sampling param).

Extend the miss message to identify *which segment differs from the
closest recorded entry*, so the user knows whether to re-record (prompt
changed intentionally) or fix the test (input accidentally drifted).

### Behaviour

When a lookup misses at key `K = compose(h_m, h_p, h_i)`:

1. Collect all entries in the cassette with matching hashes on each
   segment:
   - `by_model = [e for e in entries if e.hash_model == h_m]`
   - `by_prompt = [e for e in entries if e.hash_prompt == h_p]`
   - `by_input = [e for e in entries if e.hash_input == h_i]`
2. Determine which segments are stable and which drifted:
   - Stable segments: non-empty matches.
   - Drifted segments: empty matches.
3. Emit a `CassetteMiss` whose `__str__` includes a diff block:

```
CassetteMiss: no cassette entry for key 3abc12ef
  hash_model  = f1f2f3f4   (✓ 3 entries match)
  hash_prompt = 9a9b9c9d   (✗ not in cassette; closest: 2 entries share hash_model)
  hash_input  = 11223344   (✓ 1 entry matches)

Most likely: prompt drift. If intentional, re-record with
  OPERAD_CASSETTE=record uv run pytest tests/test_foo.py -v
(at tests/cassettes/test_foo.jsonl)
```

### API shape

`CassetteMiss` gains two things:

- a structured payload attribute (for programmatic consumers):

  ```python
  class CassetteMiss(KeyError):
      key: str
      hash_model: str
      hash_prompt: str
      hash_input: str
      matches: dict[str, int]   # {"hash_model": n, "hash_prompt": n, "hash_input": n}
      path: Path
  ```

- a `__str__` override producing the block shown above.

### Implementation sketch

```python
# operad/utils/cassette.py

def _miss_diff(
    entries: dict[str, dict[str, Any]],
    *, h_m: str, h_p: str, h_i: str,
) -> dict[str, int]:
    by_model  = sum(1 for e in entries.values() if e["hash_model"]  == h_m)
    by_prompt = sum(1 for e in entries.values() if e["hash_prompt"] == h_p)
    by_input  = sum(1 for e in entries.values() if e["hash_input"]  == h_i)
    return {"hash_model": by_model, "hash_prompt": by_prompt, "hash_input": by_input}


class CassetteMiss(KeyError):
    def __init__(
        self,
        key: str,
        *,
        hash_model: str,
        hash_prompt: str,
        hash_input: str,
        matches: dict[str, int],
        path: Path,
    ) -> None:
        self.key = key
        self.hash_model = hash_model
        self.hash_prompt = hash_prompt
        self.hash_input = hash_input
        self.matches = matches
        self.path = path
        super().__init__(str(self))

    def __str__(self) -> str: ...
```

The `cassette_context` wrapper at line 99–102 (pre-PR) changes from:

```python
raise CassetteMiss(
    f"missing cassette key for {key} "
    f"(model={h_m}, prompt={h_p}, input={h_i}) at {path}"
)
```

to:

```python
matches = _miss_diff(entries, h_m=h_m, h_p=h_p, h_i=h_i)
raise CassetteMiss(
    key,
    hash_model=h_m, hash_prompt=h_p, hash_input=h_i,
    matches=matches, path=path,
)
```

### Most-likely-cause heuristic

Emitted as a final line in `__str__`:

- `hash_prompt` drifted + others stable → `"Most likely: prompt drift."`
- `hash_input` drifted + others stable → `"Most likely: input drift."`
- `hash_model` drifted + others stable → `"Most likely: config drift."`
- Multiple drifted → `"Most likely: multiple segments drifted; review each."`
- All zero matches (empty cassette) → `"Cassette is empty; record first."`

Append the record command template:
`OPERAD_CASSETTE=record uv run pytest <test_file> -v`.

---

## Required tests

`tests/test_cassette_miss_diff.py` (new):

1. **Prompt-drift miss.** Record a cassette for agent A; mutate A's
   `role` string (changes `hash_prompt`); attempt replay with the same
   input; catch `CassetteMiss`. Assert:
   - `exc.matches["hash_model"] == 1`
   - `exc.matches["hash_input"] == 1`
   - `exc.matches["hash_prompt"] == 0`
   - `str(exc)` contains `"prompt drift"` and the record-command
     template.
2. **Input-drift miss.** Same agent, different input payload;
   `matches["hash_input"] == 0`, others stable; message says
   `"input drift"`.
3. **Config-drift miss.** Swap `Configuration.sampling.temperature`
   from 0.0 to 0.7; `matches["hash_model"] == 0`, others stable;
   message says `"config drift"`.
4. **Multiple-drift miss.** Mutate both role and input; message says
   `"multiple segments drifted"`.
5. **Empty-cassette miss.** Point at a cassette path that doesn't
   exist (or is empty); message says `"Cassette is empty"`.
6. **Programmatic access.** `exc.matches` is a `dict[str, int]`;
   `exc.hash_prompt`, `exc.key`, `exc.path` are readable.

All tests offline; use `FakeLeaf`-style stubs + a `tmp_path`-backed
cassette. No cassette fixture needed — call `cassette_context`
directly.

---

## Scope

**New files.**
- `tests/test_cassette_miss_diff.py`.

**Edited files.**
- `operad/utils/cassette.py` — new `_miss_diff` helper, reshape
  `CassetteMiss` class, update `cassette_context` raise site.

**Must NOT touch.**
- `operad/utils/hashing.py` — consume its helpers; don't change them.
- `operad/core/` — entirely.
- Other runtime, agents, metrics.

---

## Acceptance

- `uv run pytest tests/test_cassette_miss_diff.py` green.
- `uv run pytest tests/` green.
- Cassette-based existing tests still pass (unchanged happy path).
- `CassetteMiss` subclasses `KeyError` still (so `except KeyError`
  catches it).

---

## Watch-outs

- **Subclass of `KeyError`.** `KeyError`'s default `__str__` wraps the
  arg in `repr()`, which inserts quotes. Override `__str__` to return
  the plain block; the test will pin the exact format.
- **Hash segment names must match `hashing.py`.** The segment keys in
  `matches` are literal strings `"hash_model"`, `"hash_prompt"`,
  `"hash_input"` — keep them aligned with the functions in
  `operad/utils/hashing.py` so grep works.
- **Cassette file-level locking.** Not introduced here; miss-diff is
  read-only against the in-memory `entries` dict already loaded at
  context entry. No new I/O.
- **`path` may be relative.** `cassette_context` takes a
  `pathlib.Path` that might be relative (pointing into
  `tests/cassettes/<name>.jsonl`). Preserve it verbatim; don't
  resolve to absolute — tests expect the repo-relative form in the
  message.
- **Fixture compatibility.** `tests/conftest.py` wraps
  `cassette_context` via a `cassette` fixture. The fixture's API
  doesn't change; it still catches `CassetteMiss` via `except
  KeyError` or similar. Confirm the fixture still works by running
  one cassette-backed test unchanged.
- **Record-command template.** Keep it aligned with what
  `CLAUDE.md` documents (the `OPERAD_CASSETTE=record` env var). If
  the CLAUDE doc changes, update this string in lockstep.
