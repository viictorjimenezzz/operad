#!/usr/bin/env bash
# Compute OTEL_EXPORTER_OTLP_HEADERS from the Langfuse public/secret key
# pair. Reads the keys from .env (or env vars), prints a line you can
# paste back into .env.
#
# Usage:
#   bash scripts/langfuse_otel_header.sh
#
# Or to update .env in place (BSD/GNU sed compatible via temp file):
#   bash scripts/langfuse_otel_header.sh --update

set -euo pipefail

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi

: "${LANGFUSE_INIT_PROJECT_PUBLIC_KEY:?LANGFUSE_INIT_PROJECT_PUBLIC_KEY is unset}"
: "${LANGFUSE_INIT_PROJECT_SECRET_KEY:?LANGFUSE_INIT_PROJECT_SECRET_KEY is unset}"

token=$(printf '%s:%s' \
  "$LANGFUSE_INIT_PROJECT_PUBLIC_KEY" \
  "$LANGFUSE_INIT_PROJECT_SECRET_KEY" | base64 | tr -d '\n')

line="OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic ${token}"

if [[ "${1:-}" == "--update" && -f .env ]]; then
  tmp=$(mktemp)
  awk -v new="$line" '
    /^OTEL_EXPORTER_OTLP_HEADERS=/ { print new; next }
    { print }
  ' .env > "$tmp"
  mv "$tmp" .env
  echo "Updated .env" >&2
else
  echo "$line"
fi
