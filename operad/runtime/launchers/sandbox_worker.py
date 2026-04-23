"""Subprocess worker for ``SandboxedTool`` and ``SandboxPool``.

Two modes:

- Single-shot (``--tool=module:Class``): reads one JSON args object from
  stdin, calls the tool, writes ``{"result": ...}`` to stdout, exits.
  Used by ``SandboxedTool``.
- Pool (``--pool``): long-lived loop reading JSON-lines requests
  ``{"id", "tool", "args"}`` from stdin and writing JSON-lines responses
  ``{"id", "ok", "result"|"error"}`` to stdout. Used by ``SandboxPool``.
  Exits cleanly on stdin EOF.
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


async def _pool_loop() -> int:
    loop = asyncio.get_running_loop()
    cache: dict[str, object] = {}

    def _get_tool(spec: str) -> object:
        tool = cache.get(spec)
        if tool is None:
            module, classname = _parse_tool_arg(spec)
            mod = importlib.import_module(module)
            tool = getattr(mod, classname)()
            cache[spec] = tool
        return tool

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return 0
        line = line.strip()
        if not line:
            continue
        req_id = None
        try:
            req = json.loads(line)
            req_id = req["id"]
            tool = _get_tool(req["tool"])
            result = await tool.call(req["args"])
            resp = {"id": req_id, "ok": True, "result": result}
        except Exception as e:
            resp = {"id": req_id, "ok": False, "error": str(e)}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool")
    parser.add_argument("--pool", action="store_true")
    ns = parser.parse_args()

    if ns.pool:
        return asyncio.run(_pool_loop())

    if not ns.tool:
        parser.error("either --tool or --pool is required")
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
