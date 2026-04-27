## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Codebase Invariants

**Preserve the architecture unless the task explicitly changes it.**

- Components are `Agent[In, Out]`; algorithms stay as plain orchestration loops under `operad/algorithms`.
- Agent contracts live on class attributes such as `input`, `output`, `role`, `task`, `rules`, and `examples`.
- Call `build()` before invocation; constructors should not touch providers.
- Composite agents route; payload-value decisions belong in leaves or routers.
- Offline tests should use `FakeLeaf`; live provider tests belong under `tests/integration` and stay gated by `OPERAD_INTEGRATION`.

## 6. Verification

**Run checks that match the risk of the change.**

- Run the narrow relevant tests first.
- Run `uv run pytest tests/` before PRs when practical.
- Run `uv run python -c "import operad"` after changes to exports, package layout, or public APIs.

## 7. Documentation

**Keep docs close to their source of truth.**

- Prefer linking to the authoritative doc or code location instead of copying long explanations into prompt files.
- Update nearby docs when behavior, imports, or public APIs change.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
