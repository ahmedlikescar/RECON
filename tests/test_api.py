import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from recon.api.app import create_app
from recon.config import Settings
from recon.service import Service, identifier
from recon.storage.database import Binary, Job


def wait_job(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["state"] not in {"queued", "running"}:
            return job
        time.sleep(0.05)
    pytest.fail("Background job did not finish within 20 seconds")


def import_fixture(client: TestClient, fixtures: Path, opt: str = "O0") -> dict:
    path = fixtures / f"demo-{opt}.elf"
    response = client.post("/api/v1/binaries", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 202, response.text
    result = response.json()
    assert wait_job(client, result["job_id"])["state"] == "completed"
    return result


def test_end_to_end_real_comparison_export_and_delete(fixtures, tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        assert client.get("/api/v1/health").json()["local_only"]
        capabilities = client.get("/api/v1/capabilities").json()
        assert capabilities["formats"] == ["ELF"]
        assert not capabilities["neural"]["available"]
        first, second = import_fixture(client, fixtures), import_fixture(client, fixtures, "O2")
        a, b = first["binary"]["id"], second["binary"]["id"]
        functions = client.get(f"/api/v1/binaries/{a}/functions?search=checksum").json()
        assert functions["total"] == 1
        query = functions["items"][0]
        detail = client.get(f"/api/v1/functions/{query['id']}").json()
        assert detail["instructions"][0]["address"] == query["address"]
        assert client.get(f"/api/v1/functions/{query['id']}/cfg").json()["blocks"]
        response = client.post(
            "/api/v1/comparisons",
            json={
                "source_binary_id": a,
                "target_binary_id": b,
                "query_function_id": query["id"],
                "method": "hybrid",
                "threshold": 1.0,
            },
        )
        assert response.status_code == 202, response.text
        comparison_id = response.json()["comparison"]["id"]
        job = wait_job(client, response.json()["job_id"])
        assert job["state"] == "completed", job
        result = client.get(f"/api/v1/comparisons/{comparison_id}").json()["result"]
        assert result["results"][0]["state"] == "unknown"
        assert result["source_binary"]["sha256"] == first["binary"]["sha256"]
        assert result["model_version"] == "baseline-hybrid-1"
        assert result["results"][0]["matches"][0]["name"] == "checksum_bytes"
        for format in ["json", "csv"]:
            response = client.get(f"/api/v1/reports/{comparison_id}/export?format={format}")
            assert response.status_code == 200
            assert "attachment" in response.headers["content-disposition"]
            assert "similarity" in response.text
        # Repeated comparisons reuse the persisted index; they do not retrain anything.
        assert (tmp_path / f"indexes/{b}.json").exists()
        assert client.delete(f"/api/v1/binaries/{a}").status_code == 204
        assert client.get(f"/api/v1/comparisons/{comparison_id}").status_code == 404
        assert client.get(f"/api/v1/functions/{query['id']}").status_code == 404
        assert not (tmp_path / "binaries" / first["binary"]["sha256"]).exists()


def test_duplicate_cache_and_restart(fixtures, tmp_path):
    settings = Settings(data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        first = import_fixture(client, fixtures)
        response = client.post(
            "/api/v1/binaries",
            files={"file": ("renamed.elf", (fixtures / "demo-O0.elf").read_bytes())},
        )
        assert response.json()["cached"]
        assert response.json()["binary"]["id"] == first["binary"]["id"]
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/binaries").json()["total"] == 1
        assert (
            client.get(f"/api/v1/binaries/{first['binary']['id']}/functions").json()["total"] == 9
        )
        assert client.get(f"/api/v1/jobs/{first['job_id']}").json()["state"] == "completed"


def test_validation_errors_and_local_boundary(fixtures, tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        response = client.post("/api/v1/binaries", files={"file": ("bad.exe", b"MZinvalid")})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"
        response = client.post("/api/v1/binaries", files={"file": ("../bad.elf", b"invalid")})
        assert response.json()["error"]["code"] == "UNSAFE_FILENAME"
        assert client.get("/api/v1/binaries/nonsense").status_code == 404
        assert client.get("/api/v1/binaries?limit=100000").status_code == 422
        assert client.get("/api/v1/health", headers={"Host": "attacker.example"}).status_code == 400
        assert (
            client.post("/api/v1/demo", headers={"Origin": "https://attacker.example"}).status_code
            == 403
        )
        assert (
            client.get("/api/v1/health", headers={"Origin": "http://127.0.0.1:5173"}).status_code
            == 200
        )
        response = client.post("/api/v1/demo")
        assert (
            response.status_code == 409 and response.json()["error"]["code"] == "DEMO_NOT_INSTALLED"
        )


def test_integrity_errors_do_not_return_changed_artifacts(fixtures, tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        first = import_fixture(client, fixtures)
        binary_id = first["binary"]["id"]
        functions = client.get(f"/api/v1/binaries/{binary_id}/functions").json()["items"]
        (tmp_path / f"analysis/{binary_id}.json").write_text("{}")
        response = client.get(f"/api/v1/functions/{functions[0]['id']}")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ARTIFACT_INTEGRITY"


def test_missing_weights_and_rea_do_not_break_native_analysis(fixtures, tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        first = import_fixture(client, fixtures)
        binary_id = first["binary"]["id"]
        function = client.get(f"/api/v1/binaries/{binary_id}/functions").json()["items"][0]
        assert (
            client.post(
                f"/api/v1/functions/{function['id']}/investigate", json={"consent": False}
            ).status_code
            == 409
        )
        result = client.post(
            f"/api/v1/functions/{function['id']}/investigate", json={"consent": True}
        )
        assert result.status_code == 200
        assert result.json()["fallback"] and result.json()["assembly"]
        response = client.post(
            "/api/v1/comparisons",
            json={"source_binary_id": binary_id, "target_binary_id": binary_id, "method": "neural"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"


def test_interrupted_jobs_persist_as_failed_and_queued_jobs_can_cancel(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = Service(settings)
    resource_id, running_id, queued_id = identifier(), identifier(), identifier()
    with service.sessions.begin() as db:
        db.add(Binary(id=resource_id, filename="x", sha256="a" * 64, size=100, status="running"))
        db.add(Job(id=running_id, resource_id=resource_id, kind="analysis", state="running"))
        db.add(Job(id=queued_id, resource_id=resource_id, kind="analysis", state="queued"))
    service.close()
    restarted = Service(settings)
    assert restarted.get(Job, running_id)["error_code"] == "INTERRUPTED"
    assert restarted.cancel(queued_id)["state"] == "cancelled"
    restarted.close()
