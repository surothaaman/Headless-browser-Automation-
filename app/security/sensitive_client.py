from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from app.config import load_local_env

load_local_env()


def retrieve_sensitive_data(record_id: str, api_url: str | None = None) -> dict:
    """Retrieve a one-time encrypted record; never log or persist its plaintext."""
    token = (os.getenv("CSE_ACCESS_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("CSE_ACCESS_TOKEN is not configured")
    base_url = (api_url or os.getenv("CSE_API_URL", "http://127.0.0.1:8000")).rstrip("/")
    request = urllib.request.Request(
        f"{base_url}/api/sensitive-data/{record_id}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Sensitive-data retrieval failed (HTTP {exc.code})") from None
    except urllib.error.URLError:
        raise RuntimeError("Cannot reach sensitive-data API") from None
    sensitive = result.get("sensitive_data")
    if not isinstance(sensitive, dict):
        raise RuntimeError("Sensitive-data response has an invalid shape")
    return sensitive
