"""Integration-style unit tests for YtDlpMediaProcessor."""

from __future__ import annotations

from pathlib import Path

import pytest

from mimesis.video_ingestion.infra.media_processor import YtDlpMediaProcessor

DOWNLOADS_DIR = Path(__file__).parent.parent / "downloads"


@pytest.fixture(autouse=True, scope="module")
def clean_downloads_dir() -> None:
    """Remove and recreate tests/downloads/ before the test module runs."""
    import shutil
    if DOWNLOADS_DIR.exists():
        shutil.rmtree(DOWNLOADS_DIR)
    DOWNLOADS_DIR.mkdir()


def _save_and_assert(video_bytes: bytes, video_id: str) -> Path:
    """Save video bytes to tests/downloads/<video_id>.mp4 and assert file exists with content."""
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    out_path = DOWNLOADS_DIR / f"{video_id}.mp4"
    out_path.write_bytes(video_bytes)
    assert out_path.exists(), f"Downloaded file not found on disk: {out_path}"
    assert out_path.stat().st_size > 0, f"Downloaded file is empty on disk: {out_path}"
    print(f"\nSaved: {out_path.resolve()} ({out_path.stat().st_size:,} bytes)")
    return out_path


@pytest.mark.integration
def test_download_source_video_real_video() -> None:
    """Downloads a real YouTube video to verify the yt-dlp format selector works.

    Target video from issue #46 message payload:
    {"search_job_id": "eea8e017-089b-4004-92e8-766a82d09d33", "video_id": "agvQadGZkqQ",
     "occurred_at": "2026-04-22T20:10:07.889288+00:00",
     "metadata": {"title": "GIL G@MES CONTA 4 RELATOS INIMAGINÁVEIS",
                  "channel_id": "UC4u2dhrqvnNN-52UfODLYlQ",
                  "channel_title": "O INESQUECÍVEL REPÓRTER CONTA... "}}
    """
    processor = YtDlpMediaProcessor()
    result = processor.download_source_video("https://youtu.be/agvQadGZkqQ")
    assert isinstance(result, bytes)
    assert len(result) > 0
    _save_and_assert(result, "agvQadGZkqQ")


@pytest.mark.integration
def test_download_source_video_real_video_j_qfkyusj_0() -> None:
    """Downloads a real YouTube video to verify the yt-dlp format selector works.

    Target video from issue #46 message payload:
    {"search_job_id": "d4ee9c78-80c4-41d3-9283-1ba45a6ae030", "video_id": "J-QfkYusj-0",
     "occurred_at": "2026-04-22T21:27:29.466355+00:00",
     "metadata": {"title": "Gil Gomes 4 - Histórias Inéditas!",
                  "channel_id": "UCLE6H-xQnEx4U4PBsjht_SA",
                  "channel_title": "peri lobo"}}
    """
    processor = YtDlpMediaProcessor()
    result = processor.download_source_video("https://www.youtube.com/watch?v=J-QfkYusj-0")
    assert isinstance(result, bytes)
    assert len(result) > 0
    _save_and_assert(result, "J-QfkYusj-0")
