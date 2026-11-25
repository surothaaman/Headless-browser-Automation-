from __future__ import annotations

import json
import os
from pathlib import Path

from jwcrypto import jwe, jwk


ALGORITHM = "RSA-OAEP-256"
ENCRYPTION = "A256GCM"


def _load_public_jwk(path: str | None = None) -> jwk.JWK:
    key_path = Path(path or os.getenv("CSE_PUBLIC_KEY_PATH", "keys/server_public.pem"))
    if not key_path.is_file():
        raise FileNotFoundError(f"Public key not found: {key_path}")
    return jwk.JWK.from_pem(key_path.read_bytes())


def _load_private_jwk(path: str | None = None) -> jwk.JWK:
    key_path = Path(path or os.getenv("CSE_PRIVATE_KEY_PATH", "keys/server_private.pem"))
    if not key_path.is_file():
        raise FileNotFoundError(f"Private key not found: {key_path}")
    return jwk.JWK.from_pem(key_path.read_bytes())


def encrypt_sensitive_payload(payload: dict, public_key_path: str | None = None) -> str:
    """Create compact JWE using RSA-OAEP-256 + AES-256-GCM."""
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Sensitive payload must be a non-empty JSON object")

    protected = {"alg": ALGORITHM, "enc": ENCRYPTION, "typ": "JWE"}
    token = jwe.JWE(
        plaintext=json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        protected=protected,
    )
    token.add_recipient(_load_public_jwk(public_key_path))
    return token.serialize(compact=True)


def decrypt_sensitive_payload(compact_jwe: str, private_key_path: str | None = None) -> dict:
    """Authenticate and decrypt a compact JWE. Never log the returned plaintext."""
    if not compact_jwe or len(compact_jwe) > 100_000:
        raise ValueError("Invalid encrypted payload size")

    token = jwe.JWE()
    token.deserialize(compact_jwe)
    header = token.jose_header or {}

    if header.get("alg") != ALGORITHM or header.get("enc") != ENCRYPTION:
        raise ValueError("Unsupported JWE algorithms")

    token.decrypt(_load_private_jwk(private_key_path))
    result = json.loads(token.payload.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Decrypted payload must be a JSON object")
    return result
