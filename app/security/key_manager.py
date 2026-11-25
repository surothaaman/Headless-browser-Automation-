from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_key_pair(output_dir: str = "keys") -> tuple[Path, Path]:
    """Generate an RSA-3072 key pair. Keep the private key off source control."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    private_path = directory / "server_private.pem"
    public_path = directory / "server_public.pem"

    if private_path.exists() or public_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing key material in {directory.resolve()}"
        )

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path.write_bytes(private_bytes)
    public_path.write_bytes(public_bytes)

    try:
        private_path.chmod(0o600)
    except OSError:
        pass  # Windows ACLs should be used to restrict access on Windows.

    return private_path, public_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="keys")
    args = parser.parse_args()
    private_path, public_path = generate_key_pair(args.output_dir)
    print(f"Private key created: {private_path}")
    print(f"Public key created:  {public_path}")
    print("Keep the private key secret; distribute only the public key.")
