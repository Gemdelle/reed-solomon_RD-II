import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def tmp_storage(tmp_path: Path) -> str:
    p = tmp_path / "storage"
    p.mkdir()
    return str(p)


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch, tmp_path):
    """Ensure each test gets a fresh settings instance with isolated storage."""
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    from config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
