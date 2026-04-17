"""Media processing adapter using yt-dlp and pydub."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import yt_dlp
from pydub import AudioSegment

from mimesis.video_ingestion.domain.exceptions import MediaProcessingError
from mimesis.video_ingestion.ports.media_processor_port import MediaProcessorPort


class YtDlpMediaProcessor(MediaProcessorPort):
    """Downloads source video and extracts MP3 audio using yt-dlp."""

    def __init__(self, cookies: str | None = None) -> None:
        self._cookies = cookies

    def download_source_video(self, youtube_url: str) -> bytes:
        try:
            with TemporaryDirectory() as tmpdir:
                ydl_opts: dict[str, object] = {
                    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "outtmpl": str(Path(tmpdir) / "source.%(ext)s"),
                    "quiet": True,
                    "no_warnings": True,
                    "merge_output_format": "mp4",
                }

                if self._cookies:
                    cookie_path = Path(tmpdir) / "cookies.txt"
                    cookie_path.write_text(self._cookies)
                    ydl_opts["cookiefile"] = str(cookie_path)

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
