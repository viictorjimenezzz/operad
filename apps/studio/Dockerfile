# Build context is the operad repo root (not apps/studio/).
#
# We build the React SPA (apps/frontend/) in a Node stage and copy the
# studio bundle into operad_studio/web/ before installing the Python
# wheel — the [tool.hatch.build.targets.wheel.force-include] in
# apps/studio/pyproject.toml then ships web/ inside the package.

FROM node:22-alpine AS frontend
WORKDIR /workspace
COPY apps/frontend/package.json apps/frontend/pnpm-lock.yaml apps/frontend/.npmrc* ./apps/frontend/
RUN corepack enable && cd apps/frontend && corepack prepare pnpm@10.30.2 --activate \
    && pnpm install --frozen-lockfile
COPY apps/frontend ./apps/frontend
RUN cd apps/frontend && pnpm build:studio


FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY pyproject.toml README.md LICENSE.txt ./
COPY operad ./operad

COPY apps/studio /workspace/apps/studio
COPY --from=frontend /workspace/apps/frontend/dist-studio \
    /workspace/apps/studio/operad_studio/web

WORKDIR /workspace/apps/studio

RUN uv pip install --system -e . \
 && uv pip install --system "operad[otel] @ /workspace"

EXPOSE 7870

ENTRYPOINT ["operad-studio"]
CMD ["--host", "0.0.0.0", "--port", "7870", "--data-dir", "/data"]
