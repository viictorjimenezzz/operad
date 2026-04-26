"""operad-dashboard: local-first web UI for operad event streams."""

from .app import create_app
from .observer import WebDashboardObserver, serialize_event
from .persistence import SQLiteRunArchive
from .replay import load_records, record_to_envelope, replay_file
from .runs import RunInfo, RunRegistry

__all__ = [
    "RunInfo",
    "RunRegistry",
    "SQLiteRunArchive",
    "WebDashboardObserver",
    "create_app",
    "load_records",
    "record_to_envelope",
    "replay_file",
    "serialize_event",
]
