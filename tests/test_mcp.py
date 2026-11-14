from datetime import datetime, timezone

import pytest

from backend.config import Settings
from backend.mcp_server import _downsample, _journal_command, _parse_time


def test_parse_time_accepts_iso_and_epoch():
    assert _parse_time("2026-01-02T03:04:05Z", "start") == datetime(
        2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc
    ).timestamp()
    assert _parse_time("1767323045", "end") == 1767323045.0


def test_parse_time_rejects_garbage():
    with pytest.raises(ValueError):
        _parse_time("yesterday", "start")


def test_downsample_keeps_first_and_last():
    points = [{"timestamp": i} for i in range(300)]

    sampled, downsampled = _downsample(points, 60)

    assert downsampled is True
    assert len(sampled) == 60
    assert sampled[0] == points[0]
    assert sampled[-1] == points[-1]


def test_downsample_noop_for_small_series():
    points = [{"timestamp": i} for i in range(10)]

    sampled, downsampled = _downsample(points, 60)

    assert downsampled is False
    assert sampled == points


def test_journal_command_uses_mounted_dirs(tmp_path):
    settings = Settings(
        HOST_JOURNAL_DIR=str(tmp_path / "persistent"),
        HOST_RUN_JOURNAL_DIR=str(tmp_path / "volatile"),
    )
    (tmp_path / "persistent").mkdir()
    (tmp_path / "volatile").mkdir()

    command = _journal_command(settings, 50, "docker")

    assert command[:4] == ["journalctl", "--no-pager", "--output=short-iso", "--lines"]
    assert "--directory" in command
    assert str(tmp_path / "persistent") in command
    assert command[-2:] == ["--unit", "docker"]
