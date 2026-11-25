from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import load_local_env
from app.security.jwe_handler import decrypt_sensitive_payload
from app.security.sensitive_store import sensitive_store

load_local_env()

router = APIRouter()


class EncryptedSensitiveDataRequest(BaseModel):
    encrypted_jwe: str = Field(min_length=20, max_length=100_000)
    order_id: str | None = Field(default=None, max_length=100)


def _authorize(authorization: str | None) -> None:
    expected = (os.getenv("CSE_ACCESS_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Sensitive-data service is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    supplied = authorization[7:].strip()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


@router.post("/", status_code=201)
def store_encrypted_sensitive_data(
    request: EncryptedSensitiveDataRequest,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    record_id, ttl = sensitive_store.put(request.encrypted_jwe, request.order_id)
    return {
        "record_id": record_id,
        "order_id": request.order_id,
        "expires_in_seconds": ttl,
        "message": "Encrypted sensitive data accepted",
    }


@router.get("/{record_id}")
def retrieve_sensitive_data(
    record_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorize(authorization)
    encrypted_jwe = sensitive_store.consume(record_id)
    if encrypted_jwe is None:
        raise HTTPException(
            status_code=410,
            detail="Sensitive-data record expired, unavailable, or already consumed",
        )
    try:
        plaintext = decrypt_sensitive_payload(encrypted_jwe)
    except Exception:
        raise HTTPException(status_code=400, detail="Encrypted payload could not be validated")
    return {"record_id": record_id, "sensitive_data": plaintext}
