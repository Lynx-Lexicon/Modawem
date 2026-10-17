"""
Configuration and Environment Settings for Modawem Clinical Data Manager.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def find_workspace_root() -> Path:
    """
    Locates the Modawem workspace root directory by walking up from the current
    working directory or the file location looking for .git or known markers.
    """
    env_root = os.environ.get("MODAWEM_WORKSPACE_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        if p.exists():
            return p

    # Try current working directory first
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists() or (parent / "CODEOWNERS").exists():
            return parent

    # Fallback to module hierarchy
    module_dir = Path(__file__).resolve().parent
    for parent in [module_dir, *module_dir.parents]:
        if (parent / ".git").exists() or (parent / "CODEOWNERS").exists():
            return parent

    return cwd


def get_cache_dir() -> Path:
    """
    Returns the resolved local data cache directory.
    Configured via MODAWEM_DATA_CACHE_DIR, defaulting to data/cache/clinical_data
    relative to workspace root.
    """
    custom = os.environ.get("MODAWEM_DATA_CACHE_DIR")
    if custom:
        path = Path(custom).resolve()
    else:
        path = find_workspace_root() / "data" / "cache" / "clinical_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_reports_dir() -> Path:
    """
    Returns the resolved directory for differential and clinical review reports.
    Configured via MODAWEM_REPORTS_DIR, defaulting to reports/refresh-reports.
    """
    custom = os.environ.get("MODAWEM_REPORTS_DIR")
    if custom:
        path = Path(custom).resolve()
    else:
        path = find_workspace_root() / "reports" / "refresh-reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_dataset_location(dataset: str) -> str:
    """
    Retrieves the configured remote or local source location for a dataset.
    Raises ValueError with actionable message if not set.
    """
    dataset_normalized = dataset.lower().strip()
    if dataset_normalized in ("ddi", "drug_drug_interaction", "drug-drug-interaction"):
        env_var = "MODAWEM_DDI_DATA_LOCATION"
        val = os.environ.get(env_var)
        if not val:
            raise ValueError(
                f"Missing required environment variable '{env_var}'. "
                f"Please set '{env_var}' in your .env or environment to a valid URL or local file path "
                f"(e.g. 'https://clinical-data.modawem.internal/ddi/versions/latest/modawem_ddi.csv' or 'file:///path/to/modawem_ddi.csv')."
            )
        return val

    elif dataset_normalized in ("allergy", "drug_allergen", "drug-allergen"):
        env_var = "MODAWEM_ALLERGY_DATA_LOCATION"
        val = os.environ.get(env_var)
        if not val:
            raise ValueError(
                f"Missing required environment variable '{env_var}'. "
                f"Please set '{env_var}' in your .env or environment to a valid URL or local file path "
                f"(e.g. 'https://clinical-data.modawem.internal/allergy/versions/latest/modawem_allergy.csv' or 'file:///path/to/modawem_allergy.csv')."
            )
        return val
    else:
        raise ValueError(
            f"Unsupported dataset '{dataset}'. Supported datasets are 'ddi' and 'allergy'."
        )


def get_schema_path(dataset: str) -> Path:
    """
    Locates the JSON schema file for the requested dataset.
    """
    dataset_key = "ddi" if dataset.lower().strip() in ("ddi", "drug_drug_interaction") else "allergy"
    root = find_workspace_root()
    candidate = root / "data" / "interactions-allergies" / dataset_key / "schema.json"
    if candidate.exists():
        return candidate

    # Search in relative directory
    fallback = Path(__file__).resolve().parent.parent.parent.parent / "data" / "interactions-allergies" / dataset_key / "schema.json"
    if fallback.exists():
        return fallback

    raise FileNotFoundError(f"Could not locate schema.json for dataset '{dataset_key}' at expected path {candidate}")


def get_auth_token() -> Optional[str]:
    """
    Optional Bearer/access token for remote dataset transport.
    """
    return os.environ.get("MODAWEM_REMOTE_AUTH_TOKEN")
