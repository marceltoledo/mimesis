"""Integration-style unit tests for YtDlpMediaProcessor."""

from __future__ import annotations

import pytest

from mimesis.video_ingestion.infra.media_processor import YtDlpMediaProcessor


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
