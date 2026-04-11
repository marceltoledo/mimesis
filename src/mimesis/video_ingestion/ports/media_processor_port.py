"""Port interface for source download and audio extraction."""

from abc import ABC, abstractmethod


class MediaProcessorPort(ABC):
    @abstractmethod
    def download_source_video(self, youtube_url: str) -> bytes:
        """Download source MP4 bytes from YouTube."""

    @abstractmethod
    def extract_audio_mp3(self, source_video_bytes: bytes) -> bytes:
        """Extract MP3 bytes from source MP4 bytes."""
