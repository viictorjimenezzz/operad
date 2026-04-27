from __future__ import annotations

"""Advisory drift checker for vendored schemas.

Owner: 1-2-vendored-schemas.
"""

import difflib
import importlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SCHEMA_PAIRS = (
    (
        "apps_uthereal.schemas.safeguard",
        "ContextSafeguardResponse",
        "uthereal_workflow.agentic_workflows.chat.selfserve.input.schemas",
        "ContextSafeguardResponse",
    ),
    (
        "apps_uthereal.schemas.retrieval",
        "RetrievalSpecification",
        "uthereal_workflow.agentic_workflows.chat.selfserve.retrieval.schemas",
        "RetrievalSpecification",
    ),
    (
        "apps_uthereal.schemas.retrieval",
        "RetrievalResult",
        "uthereal_workflow.agentic_workflows.chat.selfserve.retrieval.schemas",
        "RetrievalResult",
    ),
    (
        "apps_uthereal.schemas.retrieval",
        "SummarizationResult",
        "uthereal_workflow.agentic_workflows.chat.selfserve.retrieval.schemas",
        "SummarizationResult",
    ),
    (
        "apps_uthereal.schemas.retrieval",
        "ClaimItem",
        "uthereal_workflow.agentic_workflows.chat.selfserve.retrieval.evidence_planning",
        "ClaimItem",
    ),
)


def _load(module_name: str, class_name: str) -> type[Any] | None:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None
    return getattr(module, class_name, None)


def _schema_lines(model: type[Any]) -> list[str]:
    schema = model.model_json_schema()
    text = json.dumps(schema, indent=2, sort_keys=True)
    return [f"{line}\n" for line in text.splitlines()]


def main() -> int:
    """Print unified schema diffs and always exit successfully."""

    diffs: list[str] = []
    for vendored_module, vendored_name, live_module, live_name in SCHEMA_PAIRS:
        vendored = _load(vendored_module, vendored_name)
        live = _load(live_module, live_name)
        if vendored is None or live is None:
            continue

        diff = difflib.unified_diff(
            _schema_lines(live),
            _schema_lines(vendored),
            fromfile=f"{live_module}.{live_name}",
            tofile=f"{vendored_module}.{vendored_name}",
        )
        diffs.extend(diff)

    if diffs:
        sys.stdout.writelines(diffs)
    else:
        print("no drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
