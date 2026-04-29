"""Tests for model serialization."""

from datetime import datetime, UTC

from pylar_admin.serializer import _to_json_value


class TestToJsonValue:
    def test_none(self) -> None:
        assert _to_json_value(None) is None

    def test_string(self) -> None:
        assert _to_json_value("hello") == "hello"

    def test_int(self) -> None:
        assert _to_json_value(42) == 42

    def test_bool(self) -> None:
        assert _to_json_value(True) is True

    def test_datetime(self) -> None:
        dt = datetime(2026, 1, 15, 12, 30, 0, tzinfo=UTC)
        result = _to_json_value(dt)
        assert "2026-01-15" in result
        assert isinstance(result, str)

    def test_bytes_excluded(self) -> None:
        assert _to_json_value(b"binary") is None

    def test_dict(self) -> None:
        result = _to_json_value({"key": 42})
        assert result == {"key": 42}

    def test_list(self) -> None:
        result = _to_json_value([1, "two", None])
        assert result == [1, "two", None]
