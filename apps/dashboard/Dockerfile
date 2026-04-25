# Build context is the operad repo root (not apps/dashboard/).
# The dashboard depends on operad as an editable install via uv source,
# so we copy the whole operad/ tree alongside the app's own source.

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

WORKDIR /workspace/apps/dashboard

# 3. Sync deps. Includes operad (editable) + the [otel] extra so the
#    dashboard process emits OTel spans to Langfuse.
RUN uv pip install --system -e . \
 && uv pip install --system "operad[otel] @ /workspace"

EXPOSE 7860

ENTRYPOINT ["operad-dashboard"]
CMD ["--host", "0.0.0.0", "--port", "7860"]
