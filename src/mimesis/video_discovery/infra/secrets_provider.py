"""Key Vault secrets adapter.

Retrieves secrets at runtime using DefaultAzureCredential (Managed Identity).
No credentials are stored in environment variables or config files (G-ADR-02).
"""

from __future__ import annotations

import logging

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from mimesis.video_discovery.domain.exceptions import SecretsProviderError

logger = logging.getLogger(__name__)


class SecretsProvider:
    """Thin wrapper around Azure Key Vault Secrets SDK."""

    def __init__(self, vault_url: str) -> None:
        credential = DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_url, credential=credential)

    def get_secret(self, name: str) -> str:
        """Retrieve a secret value by name.

        Raises:
            SecretsProviderError: If the secret is missing or the vault is unreachable.
        """
        try:
            secret = self._client.get_secret(name)
            if secret.value is None:
                raise SecretsProviderError(
                    f"Secret '{name}' exists in Key Vault but has a null value."
                )
            logger.debug("Secret retrieved | name=%s", name)
            return secret.value
        except SecretsProviderError:
            raise
        except Exception as exc:
            raise SecretsProviderError(
                f"Failed to retrieve secret '{name}' from Key Vault: {exc}"
            ) from exc
