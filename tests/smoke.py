"""Run against docker compose: python3 tests/smoke.py."""
import json
import os
import time
import urllib.request

BASE = os.environ.get("HYRO_BASE_URL", "http://localhost:3000")


def call(method, path, body=None):
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def main():
    project = call("POST", "/projects", {"role_title": "Senior Python Engineer"})
    project_path = f"/projects/{project['id']}"
    jd = call("POST", project_path + "/jds", {"content": "We need a Python SQL AWS engineer with 4 years experience."})
    criteria = call("POST", project_path + f"/jds/{jd['id']}/criteria")
    call("POST", project_path + f"/criteria/{criteria['id']}/approve")
    run = call("POST", project_path + "/runs", {"criteria_id": criteria["id"]})
    for _ in range(60):
        time.sleep(0.5)
        state = call("GET", project_path + f"/runs/{run['id']}")
        if state["status"] in ("completed", "failed"):
            break
    assert state["status"] == "completed", state
    results = call("GET", project_path + f"/runs/{run['id']}/results")
    assert results["total"] >= 3, results
    assert results["items"][0]["full_name"] == "Asha Rao", results
    candidate = results["items"][0]
    detail = call("GET", project_path + f"/candidates/{candidate['candidate_id']}")
    assert detail["profiles"]
    decision = call("PUT", project_path + f"/candidates/{candidate['candidate_id']}/decision", {"decision": "saved", "notes": "Strong match"})
    assert decision["decision"] == "saved"
    decisions = call("GET", project_path + "/decisions")
    assert any(item["candidate_id"] == candidate["candidate_id"] and item["decision"] == "saved" for item in decisions)
    print(json.dumps({"run": run["id"], "total": results["total"], "top": candidate["full_name"]}))


if __name__ == "__main__":
    main()
