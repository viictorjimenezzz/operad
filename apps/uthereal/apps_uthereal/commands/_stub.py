from __future__ import annotations

"""Not-yet-implemented command helpers.

Owner: 1-1-skeleton.
"""

import argparse
from collections.abc import Awaitable, Callable


class NotImplementedStub:
    """Async command callable that identifies the task owning the body."""

    def __init__(self, owner: str) -> None:
        self.owner = owner

    async def __call__(self, args: argparse.Namespace) -> int:
        raise NotImplementedError(f"Owner: {self.owner}")


def run(*, owner: str) -> Callable[[argparse.Namespace], Awaitable[int]]:
    """Return an async command stub for `owner`."""

    return NotImplementedStub(owner)
