import pytest
from fastapi.testclient import TestClient
from app.db import Session, Project, ContentRequest, WorkflowRun
from app.main import app


def seed(client, titles, statuses=None):
    workspace = client.get("/api/me").json()["workspace_id"]
    ids = []
    with Session.begin() as db:
        for index, title in enumerate(titles):
            project = Project(workspace_id=workspace, name=title)
            db.add(project)
            db.flush()
            request = ContentRequest(project_id=project.id, brief={})
            db.add(request)
            db.flush()
            run = WorkflowRun(
                project_id=project.id,
                request_id=request.id,
                status=statuses[index] if statuses else "completed",
                created_at="2026-10-22T00:00:00+00:00",
            )
            db.add(run)
            db.flush()
            ids.append(run.id)
    return ids


def test_library_pages_beyond_legacy_limit_with_stable_order(client):
    ids = seed(client, [f"Archive campaign {index:03}" for index in range(125)])
    pages = [client.get("/api/campaigns", params={"page": page, "page_size": 50}).json() for page in (1, 2, 3)]
    assert [len(page["items"]) for page in pages] == [50, 50, 25]
    assert all(page["total"] == 125 and page["pages"] == 3 for page in pages)
    ordered = [run["id"] for page in pages for run in page["items"]]
    assert ordered == sorted(ids, reverse=True) and len(set(ordered)) == 125
    assert client.get("/api/campaigns", params={"page": 4, "page_size": 50}).json()["items"] == []
    oldest = client.get("/api/campaigns", params={"sort": "oldest", "page_size": 50}).json()
    assert [run["id"] for run in oldest["items"]] == sorted(ids)[:50]
    assert len(client.get("/api/workflows").json()) == 100  # Existing picker contract remains an array.


def test_library_title_search_is_literal_and_case_insensitive(client):
    seed(client, ["Solar ENERGY report", "Budget 100%_complete", "Budget 100XXcomplete", "Quoted ' idea"])
    assert client.get("/api/campaigns", params={"q": " energy "}).json()["total"] == 1
    literal = client.get("/api/campaigns", params={"q": "%_"}).json()
    assert [run["title"] for run in literal["items"]] == ["Budget 100%_complete"]
    assert client.get("/api/campaigns", params={"q": "' OR 1=1 --"}).json()["total"] == 0
    assert client.get("/api/campaigns", params={"q": "missing"}).json()["pages"] == 0


def test_library_status_groups_combine_with_search(client):
    statuses = ["queued", "running", "awaiting_approval", "completed", "failed", "interrupted", "cancelled", "rejected"]
    seed(client, [f"Solar {status}" for status in statuses] + ["Wind completed"], statuses + ["completed"])
    expected = {
        "all": statuses,
        "active": ["queued", "running"],
        "attention": ["failed", "interrupted"],
        "awaiting_approval": ["awaiting_approval"],
        "completed": ["completed"],
        "cancelled": ["cancelled"],
        "rejected": ["rejected"],
    }
    for status, matches in expected.items():
        result = client.get("/api/campaigns", params={"q": "solar", "status": status, "page_size": 50}).json()
        assert result["total"] == len(matches)
        assert {item["status"] for item in result["items"]} == set(matches)


def test_library_counts_and_results_are_workspace_scoped(client):
    seed(client, ["Private owner campaign"])
    with TestClient(app) as other:
        assert other.get("/api/campaigns").status_code == 401
        assert other.post("/api/auth/demo").status_code == 200
        seed(other, ["Other workspace campaign"])
        assert other.get("/api/campaigns", params={"q": "Private"}).json()["total"] == 0
        assert other.get("/api/campaigns").json()["total"] == 1
    own = client.get("/api/campaigns").json()
    assert own["total"] == 1 and own["items"][0]["title"] == "Private owner campaign"


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": 1.5},
        {"page": 1000001},
        {"page_size": 51},
        {"page_size": 0},
        {"q": "x" * 181},
        {"status": "invalid"},
        {"sort": "invalid"},
    ],
)
def test_library_rejects_invalid_query_parameters(client, params):
    assert client.get("/api/campaigns", params=params).status_code == 422
