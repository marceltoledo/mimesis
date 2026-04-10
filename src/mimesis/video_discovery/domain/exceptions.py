"""Domain exceptions for the Video Discovery bounded context."""


class VideoDiscoveryError(Exception):
    """Base class for all Video Discovery errors."""


class QuotaExceededException(VideoDiscoveryError):
    """Raised when the YouTube Data API v3 quota is exhausted (HTTP 403 quotaExceeded).

    The SearchJob is marked FAILED; events already emitted for that job remain
    on the queue (AC-05).
    """


class DiscoveryLedgerError(VideoDiscoveryError):
    """Raised when the Discovery Ledger (Azure Table Storage) is unreachable or returns
    an unexpected error."""


class EventPublisherError(VideoDiscoveryError):
    """Raised when the Service Bus publisher fails to send a VideoDiscovered event."""


class YouTubeApiError(VideoDiscoveryError):
    """Raised for non-quota YouTube API errors (e.g. invalid key, network failure)."""


class SecretsProviderError(VideoDiscoveryError):
    """Raised when the Key Vault secret cannot be retrieved."""
