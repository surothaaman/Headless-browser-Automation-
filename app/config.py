"""Small, dependency-free loader for the project's local .env configuration.

For this local demo, the project-root .env file is the shared source of truth
for the API process and command-line tools. Values in that file intentionally
replace stale PowerShell environment values so both processes authenticate
with the same token after a restart.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def load_local_env(env_file: str | Path | None = None) -> Path:
    """Load KEY=VALUE lines from .env, overriding stale process values.

    Supports blank lines, comments, optional ``export ``, and matching single
    or double quotes. Does not perform shell expansion or interpolate values.
    """
    path = Path(env_file).expanduser().resolve() if env_file else ENV_FILE
    if not path.is_file():
        return path

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"Invalid .env entry at line {line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            raise ValueError(f"Invalid .env key at line {line_number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[key] = value.strip()
    return path
