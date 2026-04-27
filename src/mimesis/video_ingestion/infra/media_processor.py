"""Media processing adapter using yt-dlp and pydub."""

from __future__ import annotations

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import yt_dlp
from pydub import AudioSegment

from mimesis.video_ingestion.domain.exceptions import MediaProcessingError
from mimesis.video_ingestion.ports.media_processor_port import MediaProcessorPort

logger = logging.getLogger(__name__)

_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

# tv_embedded bypasses SABR streaming restriction and n-challenge JS requirement
# when downloading without cookies, which is necessary from cloud server IPs.
_NO_COOKIES_EXTRACTOR_ARGS: dict[str, object] = {
    "youtube": {"player_client": ["tv_embedded"]}
}


class YtDlpMediaProcessor(MediaProcessorPort):
    """Downloads source video and extracts MP3 audio using yt-dlp."""

    def __init__(self, cookies: str | None = None) -> None:
        self._cookies = cookies

    def download_source_video(self, youtube_url: str) -> bytes:
        if self._cookies:
            try:
                return self._download(youtube_url, cookies=self._cookies)
            except MediaProcessingError as exc:
                logger.warning(
                    "Download with cookies failed (%s) — retrying without cookies", exc
                )
        return self._download(youtube_url, cookies=None)

    def _download(self, youtube_url: str, cookies: str | None) -> bytes:
        try:
            with TemporaryDirectory() as tmpdir:
                ydl_opts: dict[str, object] = {
                    "format": _FORMAT,
                    "outtmpl": str(Path(tmpdir) / "source.%(ext)s"),
                    "quiet": True,
                    "no_warnings": True,
                    "merge_output_format": "mp4",
                }

                if cookies:
                    cookie_path = Path(tmpdir) / "cookies.txt"
                    cookie_path.write_text(cookies)
                    ydl_opts["cookiefile"] = str(cookie_path)
                else:
                    ydl_opts["extractor_args"] = _NO_COOKIES_EXTRACTOR_ARGS

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])

                result_path = Path(tmpdir) / "source.mp4"
                if not result_path.exists():
                    raise MediaProcessingError("yt-dlp did not produce an output file.")
                return result_path.read_bytes()
        except MediaProcessingError:
            raise
        except Exception as exc:
            raise MediaProcessingError(f"Failed to download source video: {exc}") from exc

    def extract_audio_mp3(self, source_video_bytes: bytes) -> bytes:
        try:
            with TemporaryDirectory() as tmpdir:
                video_path = Path(tmpdir) / "source.mp4"
                audio_path = Path(tmpdir) / "audio.mp3"
                video_path.write_bytes(source_video_bytes)

                audio = AudioSegment.from_file(video_path, format="mp4")
                audio.export(audio_path, format="mp3")
                return audio_path.read_bytes()
        except Exception as exc:
            raise MediaProcessingError(f"Failed to extract mp3 audio: {exc}") from exc
