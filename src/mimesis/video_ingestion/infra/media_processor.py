"""Media processing adapter using pytubefix and pydub."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from pydub import AudioSegment
from pytubefix import YouTube

from mimesis.video_ingestion.domain.exceptions import MediaProcessingError
from mimesis.video_ingestion.ports.media_processor_port import MediaProcessorPort


class PytubefixMediaProcessor(MediaProcessorPort):
    """Downloads source video and extracts MP3 audio."""

    def download_source_video(self, youtube_url: str) -> bytes:
        try:
            with TemporaryDirectory() as tmpdir:
                yt = YouTube(youtube_url)
                stream = (
                    yt.streams.filter(progressive=True, file_extension="mp4")
                    .order_by("resolution")
                    .desc()
                    .first()
                )
                if stream is None:
                    raise MediaProcessingError("No progressive mp4 stream available.")

                output_path = Path(tmpdir)
                downloaded = stream.download(output_path=str(output_path), filename="source.mp4")
                return Path(downloaded).read_bytes()
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
