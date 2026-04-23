"""Synthetic PR review against a local llama.cpp endpoint.

Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.

    uv run python examples/pr_reviewer.py
"""

from __future__ import annotations

import asyncio

from operad import DiffChunk, PRDiff, PRReviewer, set_limit

from _config import local_config


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


async def _main() -> None:
    cfg = local_config(temperature=0.2, max_tokens=1024)
    set_limit(backend="llamacpp", host=cfg.host, limit=2)

    reviewer = PRReviewer(config=cfg, read_file=_fake_read)
    await reviewer.abuild()
    report = await reviewer(SYNTHETIC)

    print(f"\nsummary: {report.summary}")
    for c in report.comments:
        print(f"  [{c.severity}] {c.path}:{c.line} — {c.comment}")


if __name__ == "__main__":
    asyncio.run(_main())
