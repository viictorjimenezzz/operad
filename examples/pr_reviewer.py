"""Synthetic PR review against a local llama.cpp endpoint.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

Run:
    uv run python examples/pr_reviewer.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from operad.agents import DiffChunk, PRDiff, PRReviewer
from operad.runtime import set_limit

from _config import local_config, server_reachable

_SCRIPT = "pr_reviewer.py"


SYNTHETIC = PRDiff(
    chunks=[
        DiffChunk(
            path="svc/auth.py",
            old="return user.token",
            new="return user.token or ''",
        ),
        DiffChunk(
            path="tests/test_auth.py",
            old="",
            new="def test_empty_token():\n    assert get_token(User()) == ''",
        ),
    ]
)


async def _fake_read(path: str) -> str:
    # Stand-in for a real filesystem reader.
    return f"# {path}\n# (synthetic file body)\n"


async def main(offline: bool = False) -> None:
    cfg = local_config(temperature=0.2, max_tokens=1024)
    print(f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}")
    if offline:
        print(f"[{_SCRIPT}] --offline not supported for this example (needs a real model); exiting 0 as no-op.")
        return
    if not server_reachable(cfg.host):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} — start llama-server or pass --offline",
            file=sys.stderr,
        )
        raise SystemExit(1)
    set_limit(backend="llamacpp", host=cfg.host, concurrency=2)

    reviewer = PRReviewer(config=cfg, read_file=_fake_read)
    await reviewer.abuild()
    report = await reviewer(SYNTHETIC)

    print(f"\nsummary: {report.summary}")
    for c in report.comments:
        print(f"  [{c.severity}] {c.path}:{c.line} — {c.comment}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
