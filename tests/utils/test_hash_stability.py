"""Tests that hash_json produces environment-independent digests."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path, PurePosixPath
from uuid import UUID

import pytest
from pydantic import BaseModel

from operad.utils.hashing import hash_json


def test_key_order_independence():
    assert hash_json({"a": 1, "b": 2}) == hash_json({"b": 2, "a": 1})


def test_datetime_utc_aware_stability():
    dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert hash_json({"ts": dt}) == hash_json({"ts": dt})


def test_datetime_timezone_independence():
    """Same moment expressed in UTC and in a named offset should hash equally."""
    from datetime import timedelta

    utc = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    eastern = datetime(2024, 6, 1, 6, 0, 0, tzinfo=timezone(timedelta(hours=-4)))
    assert hash_json({"ts": utc}) == hash_json({"ts": eastern})


def test_datetime_naive_treated_as_utc():
    naive = datetime(2024, 1, 15, 12, 0, 0)
    aware_utc = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert hash_json({"ts": naive}) == hash_json({"ts": aware_utc})


def test_date_stability():
    d = date(2024, 3, 20)
    assert hash_json({"d": d}) == hash_json({"d": d})


def test_path_posix_stability():
    p = Path("foo/bar/baz.txt")
    assert hash_json({"p": p}) == hash_json({"p": p})


def test_path_posix_equivalent():
    # PurePosixPath and Path with forward slashes should produce the same hash
    assert hash_json({"p": Path("foo/bar")}) == hash_json({"p": PurePosixPath("foo/bar")})


def test_uuid_stability():
    u = UUID("12345678-1234-5678-1234-567812345678")
    assert hash_json({"id": u}) == hash_json({"id": str(u)})


def test_decimal_stability():
    d = Decimal("1.5")
    assert hash_json({"v": d}) == hash_json({"v": d})


def test_bytes_stability():
    b = b"\x00\xff\xab"
    assert hash_json({"data": b}) == hash_json({"data": b})


def test_set_stability():
    s1 = {3, 1, 2}
    s2 = {2, 3, 1}
    assert hash_json({"s": s1}) == hash_json({"s": s2})


def test_frozenset_stability():
    fs1 = frozenset([3, 1, 2])
    fs2 = frozenset([1, 2, 3])
    assert hash_json({"s": fs1}) == hash_json({"s": fs2})


def test_basemodel_stability():
    class M(BaseModel):
        ts: datetime
        name: str

    m = M(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), name="test")
    assert hash_json(m) == hash_json(m)


def test_basemodel_datetime_tz_independence():
    from datetime import timedelta

    class M(BaseModel):
        ts: datetime

    utc = M(ts=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    offset = M(ts=datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone(timedelta(hours=2))))
    assert hash_json(utc) == hash_json(offset)


def test_unknown_type_raises():
    with pytest.raises(TypeError, match="object"):
        hash_json({"x": object()})


def test_unknown_type_error_includes_type_name():
    class Custom:
        pass

    with pytest.raises(TypeError, match="Custom"):
        hash_json({"x": Custom()})
