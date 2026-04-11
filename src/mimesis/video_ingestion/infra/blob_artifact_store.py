"""Azure Blob Storage adapter for BC-02 ingestion artifacts."""

from __future__ import annotations

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from mimesis.video_ingestion.domain.exceptions import ArtifactStoreError
from mimesis.video_ingestion.domain.models import ArtifactPaths
from mimesis.video_ingestion.ports.artifact_store_port import ArtifactStorePort


class BlobArtifactStore(ArtifactStorePort):
    """Stores artifacts in Blob Storage containers and checks completeness."""

    def __init__(self, account_url: str) -> None:
        credential = DefaultAzureCredential()
        self._service = BlobServiceClient(account_url=account_url, credential=credential)

    def artifacts_complete(self, paths: ArtifactPaths) -> bool:
        return (
            self._exists(paths.video_path)
            and self._exists(paths.audio_path)
            and self._exists(paths.metadata_path)
        )

    def upload_video(self, path: str, content: bytes) -> str:
        return self._upload(path, content, "video/mp4")

    def upload_audio(self, path: str, content: bytes) -> str:
        return self._upload(path, content, "audio/mpeg")

    def upload_metadata(self, path: str, content: bytes) -> str:
        return self._upload(path, content, "application/json")

    def _upload(self, canonical_path: str, content: bytes, content_type: str) -> str:
        container, blob = _split_path(canonical_path)
        try:
            container_client = self._service.get_container_client(container)
            container_client.create_container()
        except Exception:
            # Ignore create errors because the container may already exist.
            pass

        try:
            blob_client = self._service.get_blob_client(container=container, blob=blob)
            blob_client.upload_blob(content, overwrite=True, content_type=content_type)
            return blob_client.url
        except Exception as exc:
            raise ArtifactStoreError(
                f"Failed to upload artifact at '{canonical_path}': {exc}"
            ) from exc

    def _exists(self, canonical_path: str) -> bool:
        container, blob = _split_path(canonical_path)
        try:
            blob_client = self._service.get_blob_client(container=container, blob=blob)
            return blob_client.exists()
        except Exception as exc:
            raise ArtifactStoreError(
                f"Failed blob existence check for '{canonical_path}': {exc}"
            ) from exc


def _split_path(path: str) -> tuple[str, str]:
    parts = path.split("/", 1)
    if len(parts) != 2:
        raise ArtifactStoreError(f"Invalid canonical path: '{path}'")
    return parts[0], parts[1]
