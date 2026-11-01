import os
import socket
import time

import pytest
from fastapi.testclient import TestClient

from xscanner.actions import Actions
from xscanner.main import create_app


ORIGIN = {"Origin": "https://test.example"}


@pytest.fixture
def client():
    return TestClient(create_app())


def paired(client):
    code = client.app.state.security.pair_code
    response = client.post("/api/v1/pair", json={"code": code}, headers=ORIGIN)
    assert response.status_code == 200
    return {**ORIGIN, "Authorization": "Bearer " + response.json()["token"]}


def complete(client, task_id, headers):
    for _ in range(400):
        task = client.get(f"/api/v1/tasks/{task_id}", headers=headers).json()
        if task["status"] in {"complete", "failed", "cancelled"}:
            return task
        time.sleep(0.05)
    pytest.fail("Task never completed")


def test_origin_auth_and_pairing(client):
    code = client.app.state.security.pair_code
    assert client.post("/api/v1/pair", json={"code": code}, headers={"Origin": "https://other.example"}).status_code == 403
    assert client.get("/api/v1/capabilities", headers=ORIGIN).status_code == 401
    headers = paired(client)
    assert client.post("/api/v1/pair", json={"code": code}, headers=ORIGIN).status_code == 401
    assert client.get("/api/v1/capabilities", headers={**headers, "Origin": "https://other.example"}).status_code == 403
    assert client.post("/api/v1/tasks", json={"kind": "run-command", "params": {"command": "id"}}, headers=headers).status_code == 400


def test_search_report_and_file_access(client, tmp_path):
    target = tmp_path / "foto con espacios ñ.txt"
    target.write_text("contenido de prueba")
    headers = paired(client)
    response = client.post("/api/v1/tasks", json={"kind": "storage-file", "params": {"root": str(tmp_path), "name": "espacios"}}, headers=headers)
    task = complete(client, response.json()["id"], headers)
    assert task["status"] == "complete"
    assert task["result"]["evidence"][0]["path"] == str(target)
    assert client.get(f"/api/v1/tasks/{task['id']}/report", headers=headers).status_code == 200
    assert client.get(f"/api/v1/tasks/{task['id']}/file", params={"path": str(target)}, headers=headers).content == target.read_bytes()
    assert client.get(f"/api/v1/tasks/{task['id']}/file", params={"path": "/etc/passwd"}, headers=headers).status_code == 403


def test_photo_capture_date_and_thumbnail(client, tmp_path):
    from PIL import Image
    path = tmp_path / "foto.jpg"
    image = Image.new("RGB", (800, 600), "#27a88d")
    exif = image.getexif()
    exif[36867] = "2025:08:12 10:20:30"
    image.save(path, exif=exif)
    headers = paired(client)
    response = client.post("/api/v1/tasks", json={"kind": "storage-photo", "params": {"root": str(tmp_path), "month": "2025-08"}}, headers=headers)
    task = complete(client, response.json()["id"], headers)
    assert task["result"]["evidence"][0]["captured"].startswith("2025-08-12")
    thumb = client.get(f"/api/v1/tasks/{task['id']}/thumbnail", params={"path": str(path)}, headers=headers)
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/v1/tasks/{task['id']}/thumbnail", params={"path": "/etc/passwd"}, headers=headers).status_code == 403


def test_duplicate_search_excludes_hardlinks(client, tmp_path, monkeypatch):
    from xscanner import diagnostics
    monkeypatch.setattr(diagnostics, "HOME", tmp_path)
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    linked = tmp_path / "linked.txt"
    first.write_bytes(b"same content")
    second.write_bytes(b"same content")
    os.link(first, linked)
    headers = paired(client)
    response = client.post("/api/v1/tasks", json={"kind": "storage-space", "params": {"duplicates": True}}, headers=headers)
    task = complete(client, response.json()["id"], headers)
    groups = next(x["duplicate_groups"] for x in task["result"]["evidence"] if "duplicate_groups" in x)
    assert any(str(second) in group and (str(first) in group or str(linked) in group) for group in groups)
    assert all(not (str(first) in group and str(linked) in group) for group in groups)


def test_stale_file_and_protected_process(tmp_path):
    target = tmp_path / "archivo.txt"
    target.write_text("old")
    actions = Actions()
    task = {"id": "test-task", "status": "complete", "result": {"actions": [{"kind": "trash-file"}], "evidence": [{"path": str(target)}]}}
    confirmation = actions.prepare("trash-file", str(target), task)
    target.write_text("new contents")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as changed:
        actions.execute(confirmation["token"])
    assert changed.value.status_code == 409
    with pytest.raises(HTTPException) as protected:
        actions._target("terminate-process", str(os.getpid()))
    assert protected.value.status_code == 403


def test_storage_lab_has_exact_size_and_restores(client, monkeypatch):
    headers = paired(client)
    response = client.post("/api/v1/labs/storage/start", headers=headers)
    assert response.status_code == 200
    from xscanner.config import DATA_DIR
    folder = DATA_DIR / "labs" / "storage"
    assert sum(p.stat().st_size for p in folder.iterdir()) == 128 * 1024 * 1024
    from xscanner import diagnostics
    monkeypatch.setattr(diagnostics, "HOME", DATA_DIR / "labs")
    diagnosis = client.post("/api/v1/tasks", json={"kind": "storage-space", "params": {}}, headers=headers)
    result = complete(client, diagnosis.json()["id"], headers)
    assert result["status"] == "complete"
    assert len([x for x in result["result"]["evidence"] if "xscanner-prueba" in x.get("path", "")]) == 4
    assert client.post("/api/v1/labs/storage/restore", headers=headers).status_code == 200
    assert not folder.exists()


def test_network_and_strange_labs(client):
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", 8766))
        except OSError:
            pytest.skip("El puerto de laboratorio está ocupado")
    headers = paired(client)
    client.post("/api/v1/labs/network/start", headers=headers).raise_for_status()
    try:
        initial = client.post("/api/v1/tasks", json={"kind": "network-page", "params": {"url": "http://127.0.0.1:8766/"}}, headers=headers)
        failed_page = complete(client, initial.json()["id"], headers)
        assert "restart-lab-server" in [x["kind"] for x in failed_page["result"]["actions"]]
        prepared = client.post("/api/v1/actions/prepare", json={"task_id": failed_page["id"], "kind": "restart-lab-server"}, headers=headers)
        prepared.raise_for_status()
        client.post("/api/v1/actions/execute", json={"token": prepared.json()["token"]}, headers=headers).raise_for_status()
        again = client.post("/api/v1/tasks", json={"kind": "network-page", "params": {"url": "http://127.0.0.1:8766/"}}, headers=headers)
        restored = complete(client, again.json()["id"], headers)
        assert "HTTP 200" in restored["result"]["summary"]
    finally:
        client.post("/api/v1/labs/network/restore", headers=headers)

    client.post("/api/v1/labs/strange/start", headers=headers).raise_for_status()
    try:
        time.sleep(0.2)
        task = client.post("/api/v1/tasks", json={"kind": "strange-case", "params": {}}, headers=headers)
        diagnosed = complete(client, task.json()["id"], headers)
        assert diagnosed["result"]["evidence"]
        assert diagnosed["result"]["actions"] == []
    finally:
        client.post("/api/v1/labs/strange/restore", headers=headers)


def test_process_lab_detect_and_stop(client):
    headers = paired(client)
    started = client.post("/api/v1/labs/process/start", headers=headers)
    started.raise_for_status()
    pid = started.json()["pid"]
    try:
        response = client.post("/api/v1/tasks", json={"kind": "process-slow", "params": {}}, headers=headers)
        task = complete(client, response.json()["id"], headers)
        assert task["status"] == "complete"
        process = next(x for x in task["result"]["evidence"] if x["pid"] == pid)
        assert process["cpu_percent_sample"] > 0
        prepared = client.post("/api/v1/actions/prepare", json={"task_id": task["id"], "kind": "terminate-process", "target": str(pid)}, headers=headers)
        prepared.raise_for_status()
        stopped = client.post("/api/v1/actions/execute", json={"token": prepared.json()["token"]}, headers=headers)
        stopped.raise_for_status()
        assert stopped.json()["stopped"]
    finally:
        client.post("/api/v1/labs/process/restore", headers=headers)


def test_cancelled_task_has_report(client):
    headers = paired(client)
    response = client.post("/api/v1/tasks", json={"kind": "process-slow", "params": {}}, headers=headers)
    task_id = response.json()["id"]
    client.post(f"/api/v1/tasks/{task_id}/cancel", headers=headers).raise_for_status()
    cancelled = complete(client, task_id, headers)
    assert cancelled["status"] == "cancelled"
    text = client.get(f"/api/v1/tasks/{task_id}/report", headers=headers).text
    assert "cancelled" in text
    assert "Resultado incompleto" in text


def test_technician_password_and_user_script(client):
    headers = paired(client)
    assert client.get("/api/v1/technician/scripts", headers=headers).status_code == 403
    password = "local-tech-password-123"
    assert client.post("/api/v1/technician/password", json={"password": password}, headers=headers).status_code == 200
    assert client.post("/api/v1/technician/unlock", json={"password": password}, headers=headers).status_code == 200
    source = "import os\nprint(os.getuid())\n"
    saved = client.post("/api/v1/technician/scripts", json={"name": "uid_check", "source": source}, headers=headers)
    saved.raise_for_status()
    run = client.post("/api/v1/technician/scripts/uid_check/run", headers=headers)
    run.raise_for_status()
    assert run.json()["stdout"].strip() == str(os.getuid())
