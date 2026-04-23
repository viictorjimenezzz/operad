"""Subprocess worker for ``SandboxedTool``.

Invoked as:

    python -m operad.runtime.launchers.sandbox_worker --tool=module:Class

Reads a single JSON object (the tool args) from stdin, instantiates the
named class with zero arguments, awaits ``tool.call(args)``, and writes
``{"result": <json>}`` to stdout. Exits 0 on success, 1 on any error
(traceback goes to stderr).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
import traceback


def _parse_tool_arg(spec: str) -> tuple[str, str]:
    module, _, classname = spec.partition(":")
    if not module or not classname:
        raise ValueError(f"--tool must be 'module:Class', got {spec!r}")
    return module, classname


async def _run(module: str, classname: str, args: dict) -> object:
    mod = importlib.import_module(module)
    cls = getattr(mod, classname)
    tool = cls()
    return await tool.call(args)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", required=True)
    ns = parser.parse_args()
    try:
        module, classname = _parse_tool_arg(ns.tool)
        raw = sys.stdin.read()
        args = json.loads(raw) if raw else {}
        result = asyncio.run(_run(module, classname, args))
        sys.stdout.write(json.dumps({"result": result}))
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
