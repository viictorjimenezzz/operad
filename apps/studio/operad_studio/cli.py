"""`operad-studio` CLI entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .app import create_app


def main() -> None:
    p = argparse.ArgumentParser(prog="operad-studio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=7870)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--agent-bundle", type=Path, required=False)
    p.add_argument(
        "--dashboard-port",
        type=int,
        default=None,
        help="If set, forward training events to a running operad-dashboard.",
    )
    args = p.parse_args()

    app = create_app(
        data_dir=args.data_dir,
        agent_bundle=args.agent_bundle,
        dashboard_port=args.dashboard_port,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
