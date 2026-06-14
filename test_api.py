"""
End-to-end test of the FastAPI service + web UI using the in-process TestClient.
No network or running server required.

Run:  python test_api.py   (inside the venv)
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def main():
    # 1) UI loads
    r = client.get("/")
    assert r.status_code == 200 and "AI Multi-Agent Content Pipeline" in r.text
    print("UI            : served (", len(r.text), "bytes )")

    # 2) health reports provider
    h = client.get("/health").json()
    print("HEALTH        :", h)
    assert h["status"] == "ok" and "provider" in h and "model" in h

    # 3) synchronous generate
    r = client.post("/generate", json={"topic": "Building AI agent workflows with n8n", "words": 600})
    assert r.status_code == 200, r.text
    data = r.json()
    print("GENERATE      : run", data["run_id"], "| live:", data["live"])
    assert data["final_markdown"].startswith("#")
    assert [s["name"] for s in data["stages"]] == ["research", "writer", "editor", "seo", "publish"]

    # 4) fetch stored run + 404 + validation
    assert client.get(f"/runs/{data['run_id']}").status_code == 200
    assert client.get("/runs/nope").status_code == 404
    assert client.post("/generate", json={"topic": "x"}).status_code == 422

    # 5) SSE stream emits start -> 5 stages -> done
    with client.stream("GET", "/stream?topic=RAG+for+SaaS&words=500") as resp:
        assert resp.status_code == 200
        kinds = []
        for line in resp.iter_lines():
            if line.startswith("event:"):
                kinds.append(line.split(":", 1)[1].strip())
            if "done" in kinds:
                break
    print("STREAM events :", kinds)
    assert kinds[0] == "start"
    assert kinds.count("stage") == 5
    assert kinds[-1] == "done"

    print("\nALL TESTS PASSED ✅  (UI + health + generate + runs + validation + SSE stream)")


if __name__ == "__main__":
    main()
