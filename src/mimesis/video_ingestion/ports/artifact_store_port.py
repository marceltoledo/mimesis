"""Port interface for artifact persistence and existence checks."""

from abc import ABC, abstractmethod

from mimesis.video_ingestion.domain.models import ArtifactPaths


class ArtifactStorePort(ABC):
    @abstractmethod
    def artifacts_complete(self, paths: ArtifactPaths) -> bool:
        """Return True when video/audio/metadata artifacts all exist."""

    @abstractmethod
    def upload_video(self, path: str, content: bytes) -> str:
        """Upload source video bytes and return blob URL."""

    @abstractmethod
    def upload_audio(self, path: str, content: bytes) -> str:
        """Upload audio bytes and return blob URL."""

    @abstractmethod
    def upload_metadata(self, path: str, content: bytes) -> str:
        """Upload metadata JSON bytes and return blob URL."""
