import os
import tempfile
from pathlib import Path
import pytest

TEST_ROOT = tempfile.TemporaryDirectory(prefix="contentforge-tests-")
os.environ.update(
    DATABASE_URL="sqlite:///" + str(Path(TEST_ROOT.name) / "test.db"),
    DATA_DIR=TEST_ROOT.name,
    DEMO_STEP_DELAY="0.02",
    REDIS_URL="",
    CHECKPOINT_URL="",
    DEMO_AUTH="true",
    REGISTRATION_ENABLED="true",
    WORKFLOW_DAILY_LIMIT="50",
    WORKFLOW_CONCURRENCY_LIMIT="2",
)
from fastapi.testclient import TestClient
from app.db import Base, engine
from app.main import app
from app.rate_limit import local_limiter
from app.workflow import execute
import app.main as main


@pytest.fixture
def client(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    local_limiter.clear()
    monkeypatch.setattr(main, "enqueue", lambda run_id, action="start": execute(run_id, action))
    with TestClient(app) as client:
        assert client.post("/api/auth/demo").status_code == 200
        yield client


@pytest.fixture
def campaign(client):
    result = client.post(
        "/api/workflows",
        json={"prompt": "Create a researched content campaign about electric vehicles in India.", "mode": "demo"},
    )
    assert result.status_code == 201, result.text
    run = client.get("/api/workflows/" + result.json()["id"]).json()
    assert run["status"] == "awaiting_approval", run.get("error")
    return run
