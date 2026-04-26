"""Shared helpers for interactive examples."""

from __future__ import annotations

import socket
from urllib.parse import urlparse

try:
    from rich.console import Console
    from rich.panel import Panel

    _RICH = True
except ImportError:
    _RICH = False


def rich_available() -> bool:
    return _RICH


def print_rule(title: str) -> None:
    if _RICH:
        Console(width=120).rule(f"[bold cyan]{title}")
    else:
        bar = "═" * (len(title) + 6)
        print(f"\n{bar}\n   {title}\n{bar}")


def print_panel(title: str, body: str) -> None:
    if _RICH:
        Console(width=120).print(Panel(body, title=title, border_style="cyan"))
    else:
        bar = "─" * 60
        print(f"\n{bar}\n{title}\n{bar}\n{body}\n{bar}")


def parse_dashboard_target(
    value: str | None,
    *,
    default: str = "127.0.0.1:7860",
) -> tuple[str, int]:
    raw = value or default
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 7860
    return host, port


def server_up(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def attach_dashboard(
    target: str,
    *,
    open_browser: bool = True,
    default: str = "127.0.0.1:7860",
) -> bool:
    host, port = parse_dashboard_target(target, default=default)
    if not server_up(host, port):
        print(
            f"[dashboard] no server at {host}:{port} — "
            "start one with `operad-dashboard --port 7860` then re-run with --dashboard"
        )
        return False
    from operad.dashboard import attach

    attach(host=host, port=port)
    url = f"http://{host}:{port}"
    print(f"[dashboard] attached → {url}")
    if open_browser:
        try:
            import webbrowser

            webbrowser.open_new_tab(url)
        except Exception:
            pass
    return True
