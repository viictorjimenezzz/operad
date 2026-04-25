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

.PHONY: help \
        up down restart rebuild logs ps clean \
        env header \
        dashboard studio demo \
        test test-otel test-dashboard \
        verify \
        cassettes-refresh cassettes-check

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
	@echo
	@echo "Stack starting. Watch progress: make logs SVC=langfuse-web"
	@echo "Dashboard: http://localhost:$(DASHBOARD_PORT)"
	@echo "Studio:    http://localhost:$(STUDIO_PORT)"
	@echo "Langfuse:  $(LANGFUSE_PUBLIC_URL)  (first boot ~2-3 min for migrations)"

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

dashboard:
	@$(ENV_LOAD); \
	uv run --extra observers operad-dashboard \
		--host 127.0.0.1 \
		--port $(DASHBOARD_PORT)

studio:
	@$(ENV_LOAD); \
	mkdir -p .studio-data; \
	uv run operad-studio \
		--host 127.0.0.1 \
		--port $(STUDIO_PORT) \
		--data-dir ./.studio-data \
		--dashboard-port $(DASHBOARD_PORT)

# ------------------------------------------------------------------
# Demo: end-to-end with dashboard attach + Langfuse OTel export.
# Assumes the stack is up (or at least Langfuse on $(LANGFUSE_PUBLIC_URL)).
# OPERAD_OTEL=1 makes operad.tracing auto-register OtelObserver at import.
# ------------------------------------------------------------------

demo:
	@$(ENV_LOAD); \
	OPERAD_OTEL=1 \
	OTEL_EXPORTER_OTLP_ENDPOINT="$${OTEL_EXPORTER_OTLP_ENDPOINT:-$(LANGFUSE_PUBLIC_URL)/api/public/otel}" \
	uv run --extra otel python apps/demos/agent_evolution/run.py --offline --dashboard

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
