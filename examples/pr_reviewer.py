"""Synthetic PR review against a local llama.cpp endpoint.

    OPERAD_LLAMACPP_HOST=127.0.0.1:8080 \\
    OPERAD_LLAMACPP_MODEL=<model> \\
    uv run python examples/pr_reviewer.py

Without ``OPERAD_LLAMACPP_MODEL`` set, the script prints a hint and
exits cleanly — so it is safe to run as a smoke check.
"""

from __future__ import annotations

import asyncio
import os

from operad import Configuration, DiffChunk, PRDiff, PRReviewer, set_limit


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


def _cfg(model: str) -> Configuration:
    return Configuration(
        backend="llamacpp",
        host=os.environ.get("OPERAD_LLAMACPP_HOST", "127.0.0.1:8080"),
        model=model,
        temperature=0.2,
        max_tokens=1024,
    )


async def _main() -> None:
    model = os.environ.get("OPERAD_LLAMACPP_MODEL")
    if not model:
        print("Set OPERAD_LLAMACPP_MODEL to run this example.")
        return

    cfg = _cfg(model)
    set_limit(backend="llamacpp", host=cfg.host, limit=2)

    reviewer = PRReviewer(config=cfg, read_file=_fake_read)
    await reviewer.abuild()
    report = await reviewer(SYNTHETIC)

    print(f"\nsummary: {report.summary}")
    for c in report.comments:
        print(f"  [{c.severity}] {c.path}:{c.line} — {c.comment}")


if __name__ == "__main__":
    asyncio.run(_main())
