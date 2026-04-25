# Build context is the operad repo root (not apps/dashboard/).
# The dashboard depends on operad as an editable install via uv source,
# so we copy the whole operad/ tree alongside the app's own source.
#
# We build the React SPA (apps/frontend/) in a Node stage and copy the
# dashboard bundle into operad_dashboard/web/ before installing the
# Python wheel — the [tool.hatch.build.targets.wheel.force-include]
# directive in apps/dashboard/pyproject.toml then ships web/ inside
# the package.

FROM node:22-alpine AS frontend
WORKDIR /workspace
COPY apps/frontend/package.json apps/frontend/pnpm-lock.yaml apps/frontend/.npmrc* ./apps/frontend/
RUN corepack enable && cd apps/frontend && corepack prepare pnpm@10.30.2 --activate \
    && pnpm install --frozen-lockfile
COPY apps/frontend ./apps/frontend
RUN cd apps/frontend && pnpm build:dashboard


FROM python:3.12-slim AS base

# uv is the canonical install path; pin a known version for reproducibility.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

# 1. Copy operad core + utility files needed by the editable install.
COPY pyproject.toml README.md LICENSE.txt ./
COPY operad ./operad

# 2. Copy the dashboard package.
COPY apps/dashboard /workspace/apps/dashboard

# 3. Drop the freshly built SPA into the dashboard package so it ships
#    inside the wheel (force-include in pyproject.toml).
COPY --from=frontend /workspace/apps/frontend/dist-dashboard \
    /workspace/apps/dashboard/operad_dashboard/web

WORKDIR /workspace/apps/dashboard

# 4. Guard: fail fast if the SPA bundle was not produced by the Node stage.
RUN test -f operad_dashboard/web/index.html \
    || { echo "ERROR: SPA bundle missing — run 'make build-frontend'"; exit 1; }

# 5. Sync deps. Includes operad (editable) + the [otel] extra so the
#    dashboard process emits OTel spans to Langfuse.
RUN uv pip install --system -e . \
 && uv pip install --system "operad[otel] @ /workspace"

EXPOSE 7860

ENTRYPOINT ["operad-dashboard"]
CMD ["--host", "0.0.0.0", "--port", "7860"]
