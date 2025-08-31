# backend/tests/conftest.py
import os
import time
import pathlib
import pytest

# unique DB per session (Windows-friendly)
DB_NAME = f"test_{int(time.time())}.db"
os.environ["DATABASE_URL"] = f"sqlite:///./{DB_NAME}"
os.environ["DISABLE_CANDLES"] = "1"

TEST_DB = pathlib.Path(DB_NAME)

@pytest.fixture(scope="session", autouse=True)
def _ensure_clean_db():
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except Exception:
            pass
    yield
    try:
        if TEST_DB.exists():
            TEST_DB.unlink()
    except Exception:
        pass

@pytest.fixture
def client(monkeypatch):
    # stub scheduler
    monkeypatch.setattr("app.tasks.scheduler.start_scheduler", lambda: None, raising=False)
    monkeypatch.setattr("app.tasks.scheduler.shutdown_scheduler", lambda: None, raising=False)

    # force FinBERT off (use keyword fallback)
    try:
        from app.nlp import finbert
        monkeypatch.setattr(finbert.FinBERT, "is_available", classmethod(lambda cls: False), raising=False)
    except Exception:
        pass

    # import AFTER patches
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.session import init_db

    # ensure tables exist before first request
    init_db()

    # IMPORTANT: use context manager so startup/shutdown events run properly
    with TestClient(app) as c:
        yield c
