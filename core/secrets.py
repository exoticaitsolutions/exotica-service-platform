"""Secrets management via environment or AWS Secrets Manager.

Secrets are never logged or included in responses. Values returned by this
module must be treated as sensitive throughout the codebase.
"""

import os
from typing import Protocol

from core.config import get_settings


class SecretsProvider(Protocol):
    """Protocol for getting secrets."""

    async def get_secret(self, key: str) -> str:
        """Get a secret value.

        Args:
            key: Secret key/name/ARN.

        Returns:
            The secret value.

        Raises:
            KeyError: If the secret is not found.
            Exception: If fetching the secret fails.
        """
        ...


class EnvSecretsProvider:
    """Secrets provider that reads from environment variables.

    Used for local development. The key is treated as an environment
    variable name.
    """

    async def get_secret(self, key: str) -> str:
        """Get a secret from environment variables.

        Args:
            key: Environment variable name.

        Returns:
            The environment variable value.

        Raises:
            KeyError: If the environment variable is not set.
        """
        if key not in os.environ:
            raise KeyError(f"Environment variable {key} not found")
        return os.environ[key]


class AwsSecretsManagerProvider:
    """Secrets provider using AWS Secrets Manager.

    The key is treated as a Secrets Manager ARN or secret name.
    Wraps boto3's sync client via asyncio.to_thread.
    """

    async def get_secret(self, key: str) -> str:
        """Get a secret from AWS Secrets Manager.

        Args:
            key: Secret name or ARN in Secrets Manager.

        Returns:
            The secret value.

        Raises:
            Exception: If fetching the secret fails.
        """
        import asyncio

        try:
            import boto3
        except ImportError as err:
            raise RuntimeError(
                "boto3 is required for AwsSecretsManagerProvider but not installed"
            ) from err

        settings = get_settings()
        if not settings.aws_region:
            raise ValueError("AWS_REGION must be set when using AwsSecretsManagerProvider")

        client = boto3.client("secretsmanager", region_name=settings.aws_region)

        def _get_secret_sync() -> str:
            """Sync wrapper for boto3 call."""
            response = client.get_secret_value(SecretId=key)
            if "SecretString" in response:
                return str(response["SecretString"])
            raise ValueError(f"Secret {key} is not a string secret")

        return await asyncio.to_thread(_get_secret_sync)


def get_secrets_provider() -> SecretsProvider:
    """Factory function to get the configured secrets provider.

    Returns:
        An instance of the configured SecretsProvider.
    """
    settings = get_settings()

    if settings.secrets_provider == "aws":
        return AwsSecretsManagerProvider()
    return EnvSecretsProvider()
