"""Domain exceptions for BC-02 Video Ingestion."""


class VideoIngestionError(Exception):
    """Base class for all BC-02 ingestion errors."""


class InvalidVideoDiscoveredEventError(VideoIngestionError):
    """Raised when the incoming VideoDiscovered payload is malformed."""


class IngestionLedgerError(VideoIngestionError):
    """Raised when ingestion ledger operations fail."""


class ArtifactStoreError(VideoIngestionError):
    """Raised when artifact upload/read checks fail."""


class MediaProcessingError(VideoIngestionError):
    """Raised when media download or audio extraction fails."""


class IngestedEventPublisherError(VideoIngestionError):
    """Raised when publishing VideoIngested to Service Bus fails."""
