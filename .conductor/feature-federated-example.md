# Feature · Federated multi-backend example

A worked example showing a single agent graph whose leaves point at
different backends — a cheap local model for classification, a
higher-capacity hosted model for synthesis. Demonstrates idiomatic
use of `Parallel` / `Pipeline` with heterogeneous `Configuration`s
and shows that the slot registry isolates endpoints correctly.

**Covers Part-3 item.** #8, as an example rather than a new
abstraction.

---

## Required reading

`METAPROMPT.md`, `README.md`, `examples/parallel.py` (the only
existing example), and:
- `operad/runtime/slots.py` — confirm that two configs with
  different `(backend, host)` produce independent semaphores.
- `.conductor/2-K-docs-examples.md` — example-writing conventions
  (env-var banner, offline smoke-test, comments style).

---

## Proposal sketch

### `examples/federated.py`

Build a `Parallel` where each child targets a different endpoint.
A reasonable, self-contained scenario: two cheap local classifiers
running against `llamacpp`, one expensive synthesiser running
against `openai`. Combine their outputs into a final `Report`.

Sketch:

```python
local = Configuration(
    backend="llamacpp",
    host=os.environ["OPERAD_LLAMACPP_HOST"],
    model=os.environ["OPERAD_LLAMACPP_MODEL"],
    temperature=0.0,
)
hosted = Configuration(
    backend="openai",
    model=os.environ.get("OPERAD_OPENAI_MODEL", "gpt-4o-mini"),
    api_key=os.environ["OPENAI_API_KEY"],
    temperature=0.3,
)

# Different slot budgets per endpoint
set_limit(backend="llamacpp", host=local.host, limit=8)
set_limit(backend="openai", limit=2)

root = Parallel(
    {
        "sentiment": Classifier(config=local, input=Post, output=Sentiment),
        "topics": Classifier(config=local, input=Post, output=Topics),
        "summary": Reasoner(config=hosted, input=Post, output=Summary),
    },
    input=Post,
    output=Report,
    combine=_combine,
)
```

Banner at the top: required env vars and a warning that running it
costs money on the OpenAI side.

### Bonus

If `.conductor/2-C-observers.md` has landed, attach a `JsonlObserver`
so the output log shows both backends firing; it's a compelling
visualisation of federated execution.

---

## Research directions

- **Slot-isolation behaviour.** Verify by running the example that
  two `(backend, host)` pairs get independent semaphores (read
  `operad/runtime/slots.py:68-74`). Write a 3-line note in the
  example's docstring.
- **Pydantic output shapes.** Keep the output types small
  (`Sentiment.label`, `Topics.items`, `Summary.headline`) so the
  file stays under 80 lines.
- **Offline fallback.** Stream K's `tests/test_examples.py`
  smoke-imports every example. Ensure this one imports cleanly
  without hitting the network (all the provider calls are inside
  `main()`).

---

## Integration & compatibility requirements

- **File location.** `examples/federated.py`. One file, ~80 lines.
- **No new source files under `operad/`.** This is an example, not
  a new abstraction.
- **No new dependencies.** Uses only what's already installed.
- **Env-var banner at top.** Match the style of
  `examples/parallel.py`.
- **`tests/test_examples.py`** (Stream K) smoke-imports this file;
  make sure top-level imports do not hit the network.

---

## Acceptance

- `uv run python examples/federated.py` runs against both backends
  when env is configured; fails with a clear message otherwise.
- Mermaid export (if you add a line to print it) shows the three
  children with distinct paths.
- Observer output (if enabled) shows interleaved events from both
  backends.
- `README.md` has a one-line pointer to the example under its
  "Examples" section.

---

## Watch-outs

- Do NOT hard-code API keys. Env vars only.
- Do NOT use a huge model — `gpt-4o-mini` is the upper bound for
  examples (cost and trust).
- Keep the `Post`/`Sentiment`/`Topics`/`Summary` schemas minimal.
  The example teaches federation, not schema design.
- Mention in the docstring that `set_limit` must be called *before*
  `build()` because semaphores cache after first use.
