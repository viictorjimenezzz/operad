from __future__ import annotations

"""Tests for the apps-uthereal CLI dispatcher.

Owner: 1-1-skeleton.
"""

from apps_uthereal.cli import main


def test_cli_help_contains_all_subcommands(capsys) -> None:
    rc = main(["--help"])

    captured = capsys.readouterr()
    assert rc == 0
    for command in ("run", "show", "feedback", "blame", "fix", "verify"):
        assert command in captured.out


def test_cli_run_missing_entry_returns_2(capsys) -> None:
    rc = main(["run", "--entry", "/tmp/x"])

    captured = capsys.readouterr()
    assert rc == 2
    assert "entry not found: /tmp/x" in captured.err


def test_cli_show_with_no_args_returns_2(capsys) -> None:
    rc = main(["show"])

    captured = capsys.readouterr()
    assert rc == 2
    assert "--trace-id" in captured.err
