import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security.key_manager import generate_key_pair
from app.security.jwe_handler import encrypt_sensitive_payload
from app.security.sensitive_store import InMemoryEncryptedStore


def test_store_is_one_time_and_expires():
    store = InMemoryEncryptedStore(ttl_seconds=1)
    record_id, _ = store.put("ciphertext")
    assert store.consume(record_id) == "ciphertext"
    assert store.consume(record_id) is None

    expired_id, _ = store.put("ciphertext")
    time.sleep(1.05)
    assert store.consume(expired_id) is None


def test_jwe_round_trip(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwcrypto import jwk, jwe

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public_path.write_bytes(private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))

    from app.security.jwe_handler import encrypt_sensitive_payload, decrypt_sensitive_payload
    payload = {"ssn": "000-00-0000", "dob": "1990-01-01"}
    compact = encrypt_sensitive_payload(payload, str(public_path))
    assert decrypt_sensitive_payload(compact, str(private_path)) == payload


def test_api_auth_and_one_time_flow(monkeypatch, tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from app.security.jwe_handler import encrypt_sensitive_payload
    from app.security import jwe_handler

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public_path.write_bytes(private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    monkeypatch.setenv("CSE_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("CSE_PRIVATE_KEY_PATH", str(private_path))
    monkeypatch.setattr(jwe_handler, "_load_private_jwk", lambda path=None: __import__(
        "jwcrypto"
    ).jwk.JWK.from_pem(private_path.read_bytes()))

    client = TestClient(app)
    compact = encrypt_sensitive_payload({"ssn": "000-00-0000"}, str(public_path))
    upload = client.post(
        "/api/sensitive-data/",
        json={"encrypted_jwe": compact},
        headers={"Authorization": "Bearer test-token"},
    )
    assert upload.status_code == 201
    record_id = upload.json()["record_id"]

    first = client.get(
        f"/api/sensitive-data/{record_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert first.status_code == 200
    assert first.json()["sensitive_data"]["ssn"] == "000-00-0000"

    second = client.get(
        f"/api/sensitive-data/{record_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert second.status_code == 410

    denied = client.get(
        f"/api/sensitive-data/{record_id}",
        headers={"Authorization": "Bearer wrong"},
    )
    assert denied.status_code == 401
