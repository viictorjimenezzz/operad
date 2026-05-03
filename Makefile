# operad — common workflows.
#
# Shorthand for the everyday tasks: bring up the docker stack, run the
# apps locally, run the demo with observability wired, run tests.
# Most targets read `.env` if present so secrets and Langfuse keys
# stay out of the shell.

SHELL := /usr/bin/env bash

# .env is sourced for every target that depends on it. Targets that
# don't need it skip the source to keep CI / fresh-clone runs fast.
ENV_FILE  := .env
ENV_LOAD  := if [ -f $(ENV_FILE) ]; then set -a; . ./$(ENV_FILE); set +a; fi

# Browser-facing defaults match docker-compose. Override at the CLI:
#   make demo LANGFUSE_PUBLIC_URL=http://my-host:3000
LANGFUSE_PUBLIC_URL ?= http://localhost:3000
DASHBOARD_PORT      ?= 7860
STUDIO_PORT         ?= 7870
DASHBOARD_HOST      ?= 127.0.0.1

.PHONY: help \
        up down restart rebuild logs ps clean \
        env header \
        ensure-docker-dashboard \
        dashboard studio demo demo-script demo-triage example-observed \
        test test-otel test-dashboard \
        verify \
        cassettes-refresh cassettes-check \
        frontend-install frontend-typecheck frontend-test frontend-build \
        build-frontend dev-frontend dev-studio-frontend \
        ensure-bundles

# ------------------------------------------------------------------
# Help (default target)
# ------------------------------------------------------------------

help:
	@printf '\noperad — common workflows\n\n'
	@printf '  Stack (docker compose):\n'
	@printf '    make up           Bring up Langfuse + dashboard + studio (background)\n'
	@printf '    make down         Stop the stack (keeps volumes)\n'
	@printf '    make restart      Down + up\n'
	@printf '    make rebuild      Rebuild app images and bring up\n'
	@printf '    make logs         Tail logs (use SVC=name to filter, e.g. SVC=langfuse-web)\n'
	@printf '    make ps           List services\n'
	@printf '    make clean        Down AND wipe volumes (destroys Langfuse data!)\n\n'
	@printf '  First-time setup:\n'
	@printf '    make env          Copy .env.example to .env if .env is missing\n'
	@printf '    make header       Regenerate OTEL_EXPORTER_OTLP_HEADERS in .env from project keys\n\n'
	@printf '  Run apps directly on host (no docker):\n'
	@printf '    make dashboard    operad-dashboard on :$(DASHBOARD_PORT) (--langfuse-url from .env)\n'
	@printf '    make studio       operad-studio on :$(STUDIO_PORT) (data-dir=./.studio-data)\n\n'
	@printf '  Demos:\n'
	@printf '    make demo         agent_evolution offline + dashboard attach + Langfuse OTel\n\n'
	@printf '    make demo-script  demo.py live run + dashboard attach + Langfuse OTel\n'
	@printf '    make demo-triage  triage_reply demo + dashboard attach + Langfuse OTel\n'
	@printf '    make example-observed EXAMPLE=01_agent.py  run one examples/* script with dashboard attach + Langfuse OTel\n\n'
	@printf '  Frontend (apps/frontend/):\n'
	@printf '    make build-frontend     Build dashboard + studio bundles, copy into both apps\n'
	@printf '    make dev-frontend       Vite dev server for dashboard (:5173, proxies to :$(DASHBOARD_PORT))\n'
	@printf '    make dev-studio-frontend Vite dev server for studio (:5174, proxies to :$(STUDIO_PORT))\n'
	@printf '    make frontend-test      pnpm vitest in apps/frontend/\n'
	@printf '    make frontend-typecheck pnpm tsc --noEmit in apps/frontend/\n\n'
	@printf '  Tests:\n'
	@printf '    make test               Full offline suite\n'
	@printf '    make test-otel          Just the OtelObserver tests\n'
	@printf '    make test-dashboard     Just the dashboard tests\n'
	@printf '    make verify             scripts/verify.sh — tests + every offline example + demo.py --offline\n'
	@printf '    make cassettes-refresh  Re-record all offline cassettes (needs a live backend)\n'
	@printf '    make cassettes-check    Report cassettes older than their agent source files\n\n'

# ------------------------------------------------------------------
# Stack
# ------------------------------------------------------------------

up:
	docker compose up -d
	@$(ENV_LOAD); \
	echo; \
	echo "Stack starting. Watch progress: make logs SVC=langfuse-web"; \
	echo "Dashboard: http://localhost:$(DASHBOARD_PORT)"; \
	echo "Studio:    http://localhost:$(STUDIO_PORT)"; \
	echo "Langfuse:  $${LANGFUSE_PUBLIC_URL:-$(LANGFUSE_PUBLIC_URL)}  (first boot ~2-3 min for migrations)"

down:
	docker compose down

restart: down up

rebuild:
	docker compose up -d --build

logs:
	docker compose logs -f $(SVC)

ps:
	docker compose ps

clean:
	docker compose down -v

# ------------------------------------------------------------------
# First-time setup helpers
# ------------------------------------------------------------------

env:
	@if [ -f $(ENV_FILE) ]; then \
		echo "$(ENV_FILE) already exists — leaving it alone."; \
	else \
		cp .env.example $(ENV_FILE); \
		echo "Wrote $(ENV_FILE). Edit it to set:"; \
		echo "  - LANGFUSE_INIT_PROJECT_PUBLIC_KEY"; \
		echo "  - LANGFUSE_INIT_PROJECT_SECRET_KEY"; \
		echo "  - LANGFUSE_INIT_USER_PASSWORD"; \
		echo "Then run: make header"; \
	fi

header:
	@bash scripts/langfuse_otel_header.sh --update

# ------------------------------------------------------------------
# Host-mode app launchers (no docker)
# ------------------------------------------------------------------

DASHBOARD_BUNDLE := apps/dashboard/operad_dashboard/web/index.html
STUDIO_BUNDLE    := apps/studio/operad_studio/web/index.html

# The dashboard and studio Python packages force-include their `web/`
# directories at wheel-build time. A fresh clone has no bundle, so the
# editable install fails. `ensure-bundles` builds them on demand the
# first time anyone runs the apps locally.
ensure-bundles:
	@if [ ! -f $(DASHBOARD_BUNDLE) ] || [ ! -f $(STUDIO_BUNDLE) ]; then \
		echo "==> ensure-bundles: missing frontend bundle(s); running build-frontend"; \
		$(MAKE) build-frontend; \
	fi

dashboard: ensure-bundles
	@$(ENV_LOAD); \
	uv run --extra dashboard --extra observers operad-dashboard \
		--host 127.0.0.1 \
		--port $(DASHBOARD_PORT)

studio: ensure-bundles
	@$(ENV_LOAD); \
	mkdir -p .studio-data; \
	uv run operad-studio \
		--host 127.0.0.1 \
		--port $(STUDIO_PORT) \
		--data-dir ./.studio-data \
		--dashboard-port $(DASHBOARD_PORT)

# ------------------------------------------------------------------
# Demo: end-to-end with dashboard attach + Langfuse OTel export.
# docker-first: always rebuild/start dashboard service before running.
# OPERAD_OTEL=1 makes operad.tracing auto-register OtelObserver at import.
# ------------------------------------------------------------------

ensure-docker-dashboard:
	docker compose up -d operad-dashboard

demo: ensure-docker-dashboard
	@$(ENV_LOAD); \
	bash scripts/check_dashboard_contract.sh "$(DASHBOARD_HOST)" "$(DASHBOARD_PORT)" && \
	OPERAD_OTEL=1 \
	OTEL_EXPORTER_OTLP_ENDPOINT="$${OTEL_EXPORTER_OTLP_ENDPOINT:-$${LANGFUSE_PUBLIC_URL:-$(LANGFUSE_PUBLIC_URL)}/api/public/otel}" \
	uv run --extra otel python apps/demos/agent_evolution/run.py --offline --dashboard

demo-script: ensure-docker-dashboard
	@$(ENV_LOAD); \
	bash scripts/check_dashboard_contract.sh "$(DASHBOARD_HOST)" "$(DASHBOARD_PORT)" && \
	OPERAD_OTEL=1 \
	OTEL_EXPORTER_OTLP_ENDPOINT="$${OTEL_EXPORTER_OTLP_ENDPOINT:-$${LANGFUSE_PUBLIC_URL:-$(LANGFUSE_PUBLIC_URL)}/api/public/otel}" \
	uv run --extra observers --extra otel python demo.py --dashboard

demo-triage: ensure-docker-dashboard
	@$(ENV_LOAD); \
	bash scripts/check_dashboard_contract.sh "$(DASHBOARD_HOST)" "$(DASHBOARD_PORT)" && \
	OPERAD_OTEL=1 \
	OTEL_EXPORTER_OTLP_ENDPOINT="$${OTEL_EXPORTER_OTLP_ENDPOINT:-$${LANGFUSE_PUBLIC_URL:-$(LANGFUSE_PUBLIC_URL)}/api/public/otel}" \
	uv run --extra otel python apps/demos/triage_reply/run.py --dashboard

EXAMPLE ?= 01_agent.py
example-observed: ensure-bundles ensure-docker-dashboard
	@$(ENV_LOAD); \
	bash scripts/check_dashboard_contract.sh "$(DASHBOARD_HOST)" "$(DASHBOARD_PORT)" && \
	OPERAD_OTEL=1 \
	OTEL_EXPORTER_OTLP_ENDPOINT="$${OTEL_EXPORTER_OTLP_ENDPOINT:-$${LANGFUSE_PUBLIC_URL:-$(LANGFUSE_PUBLIC_URL)}/api/public/otel}" \
	uv run --extra gemini --extra otel python "examples/$(EXAMPLE)" --dashboard

# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

test:
	uv run pytest tests/ -q

test-otel:
	uv run pytest tests/runtime/test_observer_otel.py -v

test-dashboard:
	cd apps/dashboard && uv run pytest tests/ -q

verify:
	bash scripts/verify.sh

cassettes-refresh:
	OPERAD_CASSETTE=record uv run pytest tests/ -v -k "cassette"

cassettes-check:
	uv run python scripts/cassettes_check.py

# ------------------------------------------------------------------
# Frontend (apps/frontend/) — pnpm-driven React 19 SPA
# ------------------------------------------------------------------

frontend-install:
	cd apps/frontend && pnpm install --frozen-lockfile

frontend-typecheck: frontend-install
	cd apps/frontend && pnpm typecheck

frontend-test: frontend-install
	cd apps/frontend && pnpm test

# Build both bundles (dashboard, studio) and copy into the FastAPI
# packages so `operad-dashboard` / `operad-studio` serve them from /web.
build-frontend: frontend-install
	cd apps/frontend && pnpm build
	@test -f apps/frontend/dist-dashboard/index.html \
	    || { echo "ERROR: dist-dashboard/index.html missing after pnpm build"; exit 1; }
	@test -f apps/frontend/dist-studio/index.html \
	    || { echo "ERROR: dist-studio/index.html missing after pnpm build"; exit 1; }
	rsync -a --delete apps/frontend/dist-dashboard/ apps/dashboard/operad_dashboard/web/
	rsync -a --delete apps/frontend/dist-studio/    apps/studio/operad_studio/web/
	@echo "build-frontend: dashboard + studio bundles deployed."

dev-frontend:
	cd apps/frontend && pnpm dev:dashboard

dev-studio-frontend:
	cd apps/frontend && pnpm dev:studio
