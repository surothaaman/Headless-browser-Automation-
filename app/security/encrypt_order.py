from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from app.config import load_local_env
from app.security.jwe_handler import encrypt_sensitive_payload

load_local_env()


CREDIT_FIELDS = {"ssn", "dob"}
PAYMENT_FIELDS = {
    "card_number", "expiry_month", "expiry_year", "expiry",
    "cvv", "cvc", "cardholder_name", "card_type",
}
ALLOWED_FIELDS = CREDIT_FIELDS | PAYMENT_FIELDS


def load_and_encrypt(input_path: str, public_key_path: str | None = None) -> tuple[str, str | None]:
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input JSON root must be an object")

    sensitive = data.get("sensitive_data")
    if not isinstance(sensitive, dict) or not sensitive:
        raise ValueError("JSON must contain a non-empty 'sensitive_data' object")

    unexpected = set(sensitive) - ALLOWED_FIELDS
    if unexpected:
        raise ValueError(f"Unsupported sensitive fields: {', '.join(sorted(unexpected))}")

    # Each record is consumed once. Keep credit credentials and payment
    # credentials in separate uploads so the credit workflow cannot consume
    # the payment record (or vice versa).
    has_credit = bool(set(sensitive) & CREDIT_FIELDS)
    has_payment = bool(set(sensitive) & PAYMENT_FIELDS)
    if has_credit and has_payment:
        raise ValueError(
            "Use separate encrypted uploads for credit credentials and payment credentials"
        )
    if not has_credit and not has_payment:
        raise ValueError("Sensitive JSON must contain credit or payment fields")

    if "ssn" in sensitive and not re.fullmatch(r"\d{9}", str(sensitive["ssn"])):
        raise ValueError("SSN format is invalid")
        raise ValueError("SSN cannot be empty")
    if "dob" in sensitive and not re.fullmatch(r"\d{8}", str(sensitive["dob"])):
        raise ValueError("DOB format must be MMDDYYYY")

    # Payment details are encrypted as separate fields in the same one-time
    # record. Never print their values or include them in exception messages.
    if "card_number" in sensitive:
        digits = re.sub(r"\D", "", str(sensitive["card_number"]))
        if not 12 <= len(digits) <= 19:
            raise ValueError("Card number format is invalid")
    if "cvv" in sensitive or "cvc" in sensitive:
        cvv_value = sensitive.get("cvv", sensitive.get("cvc"))
        if not re.fullmatch(r"\d{3,4}", str(cvv_value)):
            raise ValueError("Card security code format is invalid")
    if "expiry_month" in sensitive:
        try:
            month = int(sensitive["expiry_month"])
        except (TypeError, ValueError):
            raise ValueError("Card expiry month is invalid") from None
        if not 1 <= month <= 12:
            raise ValueError("Card expiry month is invalid")
    if "expiry_year" in sensitive and not re.fullmatch(r"\d{2}|\d{4}", str(sensitive["expiry_year"])):
        raise ValueError("Card expiry year is invalid")

    encrypted = encrypt_sensitive_payload(sensitive, public_key_path)
    # Keep only non-sensitive order identifier as metadata.
    order_id = data.get("order_id")
    return encrypted, str(order_id) if order_id else None


def upload_jwe(encrypted_jwe: str, order_id: str | None, api_url: str, token: str) -> dict:
    body = json.dumps({"encrypted_jwe": encrypted_jwe, "order_id": order_id}).encode("utf-8")
    request = urllib.request.Request(
        api_url.rstrip("/") + "/api/sensitive-data/",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Sensitive-data upload failed (HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot reach FastAPI: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Encrypt sensitive fields locally and upload JWE")
    parser.add_argument("json_file")
    parser.add_argument("--api-url", default=os.getenv("CSE_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--public-key", default=os.getenv("CSE_PUBLIC_KEY_PATH", "keys/server_public.pem"))
    args = parser.parse_args()

    token = (os.getenv("CSE_ACCESS_TOKEN") or "").strip()
    if not token:
        print("ERROR: Set CSE_ACCESS_TOKEN in this PowerShell session.", file=sys.stderr)
        return 2

    try:
        encrypted_jwe, order_id = load_and_encrypt(args.json_file, args.public_key)
        result = upload_jwe(encrypted_jwe, order_id, args.api_url, token)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Never print the sensitive payload or compact JWE.
    print("Encrypted sensitive data uploaded successfully.")
    print("Record ID:", result["record_id"])
    print("Expires in:", result["expires_in_seconds"], "seconds")
    print("Use this record ID in the automation runner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
