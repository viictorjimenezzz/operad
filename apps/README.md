# `apps/` — sibling apps that consume operad

Each subfolder is an installable project that depends on `operad` like
any other downstream user. Apps do not modify `operad/` internals — if
a primitive belongs in operad, it lands there in a focused commit
first, then the app consumes it. See `.conductor/wave-4-overview.md`
§1 for the library-vs-apps split.

Current apps:

- `dashboard/` — local-first web dashboard (FastAPI + SSE + htmx +
  Mermaid.js) over the operad event bus.
