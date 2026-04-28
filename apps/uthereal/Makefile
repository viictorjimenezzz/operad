.PHONY: demo clean-runs schemas-check cassettes-check

# DEMO_ENTRY can be overridden, e.g. `make demo DEMO_ENTRY=./fixtures/entries/other.json`.
DEMO_ENTRY ?= fixtures/entries/demo_entry.json
DEMO_ID_FILE := .uthereal-runs/.demo_id
# Targeting conv_talker keeps the demo on the DIRECT_ANSWER path; no live RAG
# service is required.
DEMO_TARGET ?= conv_talker

demo:
	uv run apps-uthereal run --entry $(DEMO_ENTRY) --cassette-mode record-missing | tee /tmp/apps-uthereal-demo.log
	@grep -oE 'entry_id=[0-9a-f]+' /tmp/apps-uthereal-demo.log | head -1 | cut -d= -f2 > $(DEMO_ID_FILE)
	uv run apps-uthereal show --trace-id $$(cat $(DEMO_ID_FILE))
	uv run apps-uthereal feedback --trace-id $$(cat $(DEMO_ID_FILE)) --no-editor
	uv run apps-uthereal blame --trace-id $$(cat $(DEMO_ID_FILE)) --target $(DEMO_TARGET) --no-confirm
	uv run apps-uthereal fix --trace-id $$(cat $(DEMO_ID_FILE)) --dry-run
	uv run apps-uthereal fix --trace-id $$(cat $(DEMO_ID_FILE))
	uv run apps-uthereal verify --trace-id $$(cat $(DEMO_ID_FILE))

clean-runs:
	rm -rf .uthereal-runs

schemas-check:
	PYTHONPATH=. uv run python scripts/schemas_check.py

cassettes-check:
	@if [ -d .uthereal-runs ]; then \
		find .uthereal-runs -name 'calls.jsonl' -size 0 -print -exec false {} +; \
	fi
