# Build context is the operad repo root (not apps/studio/).

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

WORKDIR /workspace/apps/studio

RUN uv pip install --system -e . \
 && uv pip install --system "operad[otel] @ /workspace"

EXPOSE 7870

ENTRYPOINT ["operad-studio"]
CMD ["--host", "0.0.0.0", "--port", "7870", "--data-dir", "/data"]
