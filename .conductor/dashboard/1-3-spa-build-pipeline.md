# 1-3 — SPA build pipeline + CI

> **Iteration**: 1 of 4. **Parallel slot**: 3.
> **Owns**: Dockerfiles, Makefile build targets, CI workflow files.
> **Forbidden**: any source code in `operad/`, `apps/dashboard/operad_dashboard/`,
> `apps/frontend/src/`.

## Problem

The React 19 SPA from PR #127 (`5395b36 apps: ship React 19 SPA
dashboard + studio`) was added to `apps/frontend/` but **never built**.

Evidence:

- `apps/dashboard/operad_dashboard/web/` does not exist in source or
  in the running Docker container at `/app/operad_dashboard/web/`.
- `apps/frontend/dist-dashboard/` does not exist either.
- The hatch wheel manifest at `apps/dashboard/pyproject.toml`
  force-includes `operad_dashboard/web` — but the directory is empty
  at build time, so the include silently does nothing.
- The `Makefile` has a `build-frontend` target that runs `pnpm build`
  + `rsync` into both apps' `web/` dirs, but it's not invoked by the
  Docker build.

Result: every user sees the legacy server-rendered HTML in `app.py`,
and PR #127's per-algorithm JSON layouts are dead code.

## Scope

### Owned files

- `apps/dashboard/Dockerfile`
- `apps/studio/Dockerfile`
- `Makefile` (the `build-frontend` target only — its semantics, not
  the help text or anything else)
- `.github/workflows/*.yml` (or whatever CI exists; create one if
  missing — small, focused on the SPA build)
- `apps/frontend/scripts/*.sh` if you need a build helper.
- `apps/frontend/package.json` (only if build scripts need new
  entries; don't touch dependencies).
- `apps/frontend/.gitignore` (if needed for `dist-*`).

### Forbidden files

- All TS/TSX/CSS/JSON source under `apps/frontend/src/`.
- `apps/dashboard/operad_dashboard/*.py`.
- `operad/`.

## Direction

### Multi-stage Dockerfile

Both apps' Dockerfiles should:

1. **Node stage**: install pnpm, run `pnpm install --frozen-lockfile`,
   then `pnpm build:dashboard` (or `:studio`) which produces
   `apps/frontend/dist-dashboard/` (or `dist-studio/`).
2. **Python stage**: copy that dist directory into
   `apps/<app>/operad_<app>/web/` before running `uv pip install`.
3. The hatch wheel's `force-include` then ships the SPA inside the
   wheel.

The two apps can share a base Node stage if you want; alternatively,
build them independently for parallelism. Pick the cleaner approach.

### Local `make build-frontend`

The `Makefile` already has the right shape. Verify it works after a
clean checkout:

```bash
rm -rf apps/dashboard/operad_dashboard/web/ apps/studio/operad_studio/web/
make build-frontend
ls apps/dashboard/operad_dashboard/web/index.dashboard.html  # exists
ls apps/studio/operad_studio/web/index.studio.html           # exists
```

If `pnpm build` doesn't currently produce `dist-dashboard/` and
`dist-studio/`, look at `apps/frontend/vite.config.ts` and the
`package.json` build scripts. Vite produces one bundle per entry; you
likely need either two `vite build` invocations with different configs
or a single config that produces both.

### CI

Add a workflow (or a job in an existing one) that on PR:

1. Sets up pnpm + node.
2. Runs `make frontend-typecheck` (already in Makefile).
3. Runs `make frontend-test` (already in Makefile).
4. Runs `make build-frontend` and asserts both `web/` dirs are
   populated.
5. Optionally builds the dashboard Docker image and runs a 5-second
   smoke test against `/api/manifest`.

The repo may not have an existing GitHub Actions workflow — check
`.github/workflows/` first. If absent, create a minimal one;
otherwise extend the existing one.

### Failure modes

- If `dist-dashboard/` is empty, `make build-frontend` should `exit
  1` with a clear message.
- If the Dockerfile's Python stage runs without the SPA, the wheel
  build should fail (because `operad_dashboard/web/` won't exist;
  hatch's `force-include` is a no-op when the source is missing — so
  add an explicit `RUN test -f operad_dashboard/web/index.dashboard.html`
  step before `pip install`).

### Coordinate with 1-2

Task 1-2 will make `web/` mandatory at runtime (fail-fast on missing
SPA bundle). After 1-2 + 1-3 both land, the failure modes are:

- **Build time**: missing SPA → docker build fails.
- **Runtime**: missing SPA → dashboard exits with clear error.

Both should point users at `make build-frontend`.

## Acceptance criteria

1. `docker compose build operad-dashboard operad-studio` succeeds and
   the resulting images contain `/app/operad_dashboard/web/index.dashboard.html`
   (verify with `docker run --rm <image> ls /app/operad_dashboard/web/`).
2. `make build-frontend` succeeds locally and populates both `web/`
   dirs.
3. `make build-frontend` followed by `cd apps/dashboard && uv pip
   install -e .` produces a wheel that includes `web/`.
4. CI workflow runs frontend typecheck + tests + build on PRs.
5. `apps/frontend/.gitignore` keeps `dist-*` ignored.

## Dependencies & contracts

### Depends on

- Nothing.

### Exposes

- A built dashboard image always has the SPA at
  `/app/operad_dashboard/web/`.
- `make build-frontend` is a reliable, idempotent local entry point.

## Risks / non-goals

- Don't change `pnpm-lock.yaml` (commit it as-is).
- Don't bump any frontend dependency versions.
- Don't add a separate `dist/` watch step for `make demo` — devs
  already use `make dev-frontend` for HMR.
- Don't introduce a separate Node version manager file (`.nvmrc`) if
  one isn't already there; just match what `package.json` engines
  declares.

## Verification checklist

- [ ] Fresh `docker compose build` from clean checkout succeeds.
- [ ] Built images contain SPA at the expected paths.
- [ ] `make build-frontend` works without docker.
- [ ] CI workflow exists and passes on the branch.
- [ ] No source code outside the owned scope was touched.
