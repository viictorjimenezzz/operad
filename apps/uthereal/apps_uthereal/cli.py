from __future__ import annotations

"""Argparse dispatcher for the `apps-uthereal` command.

Owner: 1-1-skeleton.
"""

import argparse
import asyncio
import importlib
import inspect
import logging
import pkgutil
import sys
from types import ModuleType
from typing import Any

from apps_uthereal import commands
from apps_uthereal.commands import _stub


logger = logging.getLogger("apps_uthereal")

_COMMAND_ORDER: tuple[str, ...] = (
    "run",
    "show",
    "feedback",
    "blame",
    "fix",
    "verify",
)
_COMMAND_OWNER: dict[str, str] = {
    "run": "4-1",
    "show": "4-1",
    "feedback": "4-1",
    "blame": "4-3",
    "fix": "4-2",
    "verify": "5-1",
}


def main(argv: list[str] | None = None) -> int:
    """Entry point exposed via `apps-uthereal` script."""

    logging.basicConfig(level=logging.WARNING)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return _exit_code(exc.code)

    func = getattr(args, "func", None)
    if func is None:
        parser.print_help(sys.stderr)
        return 2

    try:
        result = func(args)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        return int(result or 0)
    except NotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apps-uthereal")
    subparsers = parser.add_subparsers(dest="command")
    modules = _load_command_modules()
    for name in _COMMAND_ORDER:
        module = modules.get(name)
        if module is not None and hasattr(module, "add_parser"):
            module.add_parser(subparsers)
            continue
        subparser = subparsers.add_parser(name)
        _add_arguments(name, subparser)
        func = getattr(module, "run", None) if module is not None else None
        subparser.set_defaults(
            func=func or _stub.run(owner=_COMMAND_OWNER[name])
        )
    return parser


def _load_command_modules() -> dict[str, ModuleType]:
    modules: dict[str, ModuleType] = {}
    for module_info in pkgutil.iter_modules(commands.__path__):
        name = module_info.name
        if name.startswith("_"):
            continue
        if name not in _COMMAND_ORDER:
            logger.debug("Ignoring unknown command module %s", name)
            continue
        modules[name] = importlib.import_module(f"{commands.__name__}.{name}")
    return modules


def _add_arguments(name: str, parser: argparse.ArgumentParser) -> None:
    if name == "run":
        parser.add_argument("--entry", required=True)
    elif name in {"show", "feedback", "verify"}:
        parser.add_argument("--trace-id", required=True)
    elif name == "blame":
        parser.add_argument("--trace-id", required=True)
        parser.add_argument("--feedback")
    elif name == "fix":
        parser.add_argument("--trace-id", required=True)
        parser.add_argument("--target")
        parser.add_argument("--dry-run", action="store_true")


def _exit_code(code: Any) -> int:
    if isinstance(code, int):
        return code
    if code is None:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
