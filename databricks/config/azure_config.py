"""
Azure configuration for the Financial Crime Analytics Platform.

All sensitive values (connection strings, keys) are retrieved at runtime from
Azure Key Vault or environment variables — never stored in source code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class AzureConfig:
    """
    Centralised Azure resource configuration for the FCAP platform.

    Attributes:
        storage_account_name:       Azure Data Lake Storage Gen2 account name.
        container_name:             ADLS Gen2 container (filesystem) name.
        key_vault_name:             Azure Key Vault name for secret retrieval.
        databricks_workspace_url:   Databricks workspace URL (e.g. https://adb-xxx.azuredatabricks.net).
        resource_group:             Azure resource group name.
        subscription_id:            Azure subscription ID.
        location:                   Azure region (e.g. japaneast, eastus).
    """

    storage_account_name: str
    container_name: str
    key_vault_name: str
    databricks_workspace_url: str
    resource_group: Optional[str] = None
    subscription_id: Optional[str] = None
    location: str = "japaneast"

    def get_storage_connection_string(self) -> str:
        """
        Build an Azure Storage connection string using the account key from
        the environment.

        The account key is expected in the environment variable
        ``AZURE_STORAGE_ACCOUNT_KEY``.  In production this value should be
        injected by a Key Vault reference or a managed identity workflow —
        it must **never** be hard-coded.

        Returns:
            Connection string suitable for the Azure Storage SDK.

        Raises:
            EnvironmentError: If the account key environment variable is not set.
        """
        account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        if not account_key:
            raise EnvironmentError(
                "Environment variable AZURE_STORAGE_ACCOUNT_KEY is not set. "
                "Retrieve the key from Azure Key Vault before calling this method."
            )
        return (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={self.storage_account_name};"
            f"AccountKey={account_key};"
            f"EndpointSuffix=core.windows.net"
        )

    def get_abfss_path(self, path: str = "") -> str:
        """
        Return the ABFSS (Azure Blob File System Secure) URI for a given path.

        Args:
            path: Relative path within the container (e.g. "raw/transactions").

        Returns:
            Fully qualified ABFSS URI.
        """
        return (
            f"abfss://{self.container_name}"
            f"@{self.storage_account_name}.dfs.core.windows.net/{path.lstrip('/')}"
        )


def get_databricks_config() -> Dict[str, str]:
    """
    Return Databricks connection configuration sourced from environment variables.

    Expected environment variables:
    - ``DATABRICKS_HOST``        — workspace URL
    - ``DATABRICKS_TOKEN``       — personal access token or service principal token

    Returns:
        Dictionary suitable for use with the Databricks REST API client or SDK.

    Raises:
        EnvironmentError: If required variables are missing.
    """
    host  = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")

    missing = [k for k, v in [("DATABRICKS_HOST", host), ("DATABRICKS_TOKEN", token)] if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required Databricks environment variables: {', '.join(missing)}"
        )

    return {
        "host":  host,
        "token": token,
    }


# ---------------------------------------------------------------------------
# Environment-specific configuration factories
# ---------------------------------------------------------------------------

def get_config(environment: str = "dev") -> AzureConfig:
    """
    Return the AzureConfig for the specified deployment environment.

    Configuration values are read from environment variables so that the same
    code base deploys to dev / staging / prod without modification.

    Args:
        environment: One of "dev", "staging", "prod".

    Returns:
        AzureConfig instance populated from environment variables.
    """
    env_upper = environment.upper()

    return AzureConfig(
        storage_account_name   = os.environ.get(f"FCAP_{env_upper}_STORAGE_ACCOUNT",   f"fcap{environment}adls"),
        container_name         = os.environ.get(f"FCAP_{env_upper}_CONTAINER",          f"fcap-{environment}-data"),
        key_vault_name         = os.environ.get(f"FCAP_{env_upper}_KEY_VAULT",          f"fcap-{environment}-kv"),
        databricks_workspace_url = os.environ.get(
            f"FCAP_{env_upper}_DATABRICKS_URL",
            f"https://adb-placeholder.{environment}.azuredatabricks.net",
        ),
        resource_group         = os.environ.get(f"FCAP_{env_upper}_RESOURCE_GROUP",    f"rg-fcap-{environment}"),
        subscription_id        = os.environ.get("AZURE_SUBSCRIPTION_ID"),
        location               = os.environ.get(f"FCAP_{env_upper}_LOCATION",           "japaneast"),
    )
