import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_providers_list():
    r = client.get("/api/providers")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) > 0


def test_models_list():
    r = client.get("/api/models")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_overview():
    r = client.get("/api/overview")
    assert r.status_code == 200
    assert "tasks" in r.json()


def test_optimize_short():
    r = client.post("/api/optimize", json={"prompt": "fix bug", "mode": "balanced"})
    assert r.status_code == 200
    assert "optimized" in r.json()


def test_route():
    r = client.post("/api/route", json={"task": "Fix a small bug in Python"})
    assert r.status_code == 200
    assert r.json()["selected_model"] is not None


def test_task_create_and_list():
    r = client.post("/api/tasks", json={"title": "t", "objective": "do something", "auto_route": True})
    assert r.status_code == 200
    tid = r.json()["id"]
    r2 = client.get("/api/tasks")
    assert any(t["id"] == tid for t in r2.json())


def test_usage_summary():
    r = client.get("/api/usage/summary")
    assert r.status_code == 200
    assert "total_input_tokens" in r.json()
