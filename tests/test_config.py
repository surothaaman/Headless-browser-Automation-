import os

from app.config import load_local_env


def test_local_env_loads_same_token_and_overrides_stale_process_value(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# local CSE settings\nCSE_ACCESS_TOKEN='shared-demo-token'\nCSE_API_URL=http://127.0.0.1:8000\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CSE_ACCESS_TOKEN", "stale-placeholder")

    loaded = load_local_env(env_file)

    assert loaded == env_file.resolve()
    assert os.environ["CSE_ACCESS_TOKEN"] == "shared-demo-token"
    assert os.environ["CSE_API_URL"] == "http://127.0.0.1:8000"


def test_missing_env_file_is_safe(tmp_path):
    missing = tmp_path / "missing.env"
    assert load_local_env(missing) == missing.resolve()
