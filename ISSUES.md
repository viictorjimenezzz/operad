# ISSUES — Known risks, footguns, and gaps

Catalogue of problems identified in the codebase. Each issue carries a
severity tag and a strategy pointer; full implementation direction
lives in the per-stream briefs under `.conductor/`.

**Status log.**
- **2026-04-23** — All remaining issues have been fixed.

Severity key:
- **High** — silent correctness risk; user sees wrong behaviour without warning.
- **Med** — honest failure modes but rough DX, dead knobs, or inconsistencies.
- **Low** — polish, docs, or test coverage.

---

## How to use this file

- When you open a PR, cite the issue numbers you address in the
  description.
- If you find a new issue while working, add it here in the matching
  section (most likely §E or a new §F) and include the update in
  your PR.
- If a fix is out of scope for your stream, leave a one-line note in
  `.conductor/notes/` (create the folder if needed) and keep moving.
- When every active issue is resolved, mark the §E entries "RESOLVED"
  with a commit hash and append a new section for the next round.
