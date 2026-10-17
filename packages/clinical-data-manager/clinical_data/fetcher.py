"""
Safe Atomic Remote and Local Dataset Fetcher with SHA-256 integrity verification,
size limits, Content-Length checks, HTML response rejection, and credential sanitization.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from clinical_data.config import get_auth_token

DEFAULT_MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024  # 500 Megabytes


def sanitize_url_for_logging(url: str) -> str:
    """
    Strips sensitive credentials, tokens, or signatures from query parameters
    and userinfo before recording in manifests, reports, or logs.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
        # Strip user:pass
        netloc = parsed.netloc
        if "@" in netloc:
            netloc = netloc.split("@")[-1]

        # Strip all query parameters to prevent token/signature exposure
        sanitized = urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
        return sanitized
    except Exception:
        return "sanitized_url"


@dataclass
class FetchResult:
    dataset: str
    source_location: str
    staged_file_path: Path
    sha256_checksum: str
    bytes_downloaded: int
    staging_dir: Path

    def cleanup(self):
        """Removes the temporary staging directory and contents."""
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir, ignore_errors=True)


def calculate_sha256(file_path: Path | str) -> str:
    """
    Computes SHA-256 hex digest over the exact file bytes.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


class DatasetFetcher:
    """
    Fetches remote or local clinical datasets into an isolated staging area.
    Supported protocols:
      - HTTP / HTTPS (streamed with timeout, size limit, Content-Length verification, and optional Bearer auth)
      - file:// URI
      - Direct local filesystem path
    """

    def __init__(self, timeout_seconds: int = 30, max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES):
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def fetch(
        self,
        dataset: str,
        location: str,
        expected_sha256: Optional[str] = None,
    ) -> FetchResult:
        """
        Atomically fetches a dataset from location into temporary staging.
        Raises RuntimeError on download, IO, or hash verification errors.
        """
        staging_dir = Path(tempfile.mkdtemp(prefix=f"modawem_stage_{dataset}_"))
        target_filename = f"modawem_{dataset}.csv"
        staged_file = staging_dir / target_filename
        sanitized_location = sanitize_url_for_logging(location)

        try:
            parsed = urllib.parse.urlparse(location)
            scheme = parsed.scheme.lower()

            if scheme in ("http", "https"):
                self._fetch_http(location, staged_file)
            elif scheme == "file":
                local_path = Path(urllib.request.url2pathname(parsed.path))
                self._fetch_local(local_path, staged_file)
            elif scheme == "" or len(scheme) == 1:  # Plain path or Windows drive letter (e.g. C:)
                local_path = Path(location).resolve()
                self._fetch_local(local_path, staged_file)
            else:
                raise ValueError(
                    f"Unsupported protocol scheme '{scheme}' in location '{sanitized_location}'. "
                    "Supported protocols are http://, https://, file://, or standard filesystem paths."
                )

            # Compute SHA-256 over downloaded bytes
            calculated_hash = calculate_sha256(staged_file)
            file_size = staged_file.stat().st_size

            # Check against expected hash if provided
            if expected_sha256:
                expected_clean = expected_sha256.strip().lower()
                if calculated_hash != expected_clean:
                    raise ValueError(
                        f"SHA-256 integrity mismatch for '{sanitized_location}'. "
                        f"Expected: {expected_clean}, Computed: {calculated_hash}. "
                        "Dataset candidate rejected to protect data integrity."
                    )

            return FetchResult(
                dataset=dataset,
                source_location=sanitized_location,
                staged_file_path=staged_file,
                sha256_checksum=calculated_hash,
                bytes_downloaded=file_size,
                staging_dir=staging_dir,
            )

        except Exception as e:
            # Clean up temporary staging on error
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to fetch dataset '{dataset}' from '{sanitized_location}': {str(e)}") from e

    def _fetch_http(self, url: str, destination: Path):
        headers = {
            "User-Agent": "Modawem-Clinical-Data-Fetcher/1.0"
        }
        token = get_auth_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            with requests.get(url, headers=headers, stream=True, timeout=self.timeout_seconds, allow_redirects=True) as response:
                response.raise_for_status()

                headers_dict = getattr(response, "headers", {})
                content_type = ""
                if hasattr(headers_dict, "get"):
                    raw_ct = headers_dict.get("Content-Type")
                    if isinstance(raw_ct, str):
                        content_type = raw_ct.lower()

                if "text/html" in content_type:
                    raise ValueError(
                        f"Remote endpoint returned HTML (Content-Type: '{content_type}') instead of a CSV dataset. "
                        "The URL may be pointing to a web login or error page."
                    )

                # Check Content-Length if present
                headers_dict = getattr(response, "headers", {})
                expected_length = None
                if isinstance(headers_dict, dict) or hasattr(headers_dict, "get"):
                    raw_len = headers_dict.get("Content-Length")
                    if isinstance(raw_len, str) and raw_len.strip().isdigit():
                        expected_length = int(raw_len.strip())

                if expected_length and expected_length > self.max_bytes:
                    raise ValueError(
                        f"Dataset size ({expected_length} bytes) exceeds maximum permitted limit ({self.max_bytes} bytes)."
                    )

                total_downloaded = 0
                with open(destination, "wb") as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            total_downloaded += len(chunk)
                            if total_downloaded > self.max_bytes:
                                raise ValueError(
                                    f"Download exceeded maximum permitted size limit ({self.max_bytes} bytes). Aborting download."
                                )
                            f.write(chunk)

                if token and response.history:
                    init_p = urllib.parse.urlparse(url)
                    fin_p = urllib.parse.urlparse(response.url)
                    if init_p.scheme.lower() == "https" and fin_p.scheme.lower() == "http":
                        raise ValueError("Insecure redirect from HTTPS to HTTP detected with authorization token. Aborting.")
                    if init_p.netloc.lower() != fin_p.netloc.lower():
                        raise ValueError(f"Cross-domain redirect from '{init_p.netloc}' to '{fin_p.netloc}' with authorization token. Aborting.")

                if total_downloaded == 0:
                    raise ValueError("Remote endpoint returned empty dataset payload (0 bytes).")

                # Verify transfer completeness if Content-Length was provided
                if expected_length is not None and total_downloaded != expected_length:
                    raise ConnectionError(
                        f"Incomplete download: received {total_downloaded} bytes, expected {expected_length} bytes."
                    )

        except requests.exceptions.RequestException as re:
            raise ConnectionError(f"HTTP fetch error ({re})") from re

    def _fetch_local(self, source_path: Path, destination: Path):
        if not source_path.exists():
            raise FileNotFoundError(f"Local source file does not exist: {source_path}")
        if not source_path.is_file():
            raise IsADirectoryError(f"Source path is a directory, not a file: {source_path}")

        file_size = source_path.stat().st_size
        if file_size > self.max_bytes:
            raise ValueError(
                f"Local dataset size ({file_size} bytes) exceeds maximum permitted limit ({self.max_bytes} bytes)."
            )

        shutil.copy2(source_path, destination)
