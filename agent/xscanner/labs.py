import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil
from fastapi import HTTPException

from .config import DATA_DIR, ensure_dirs

LAB = DATA_DIR / "labs"
STATE = LAB / "state.json"


def state() -> dict:
    ensure_dirs()
    try:
        return json.loads(STATE.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def save(value: dict) -> None:
    ensure_dirs()
    STATE.write_text(json.dumps(value))
    STATE.chmod(0o600)


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def owned_process(pid: int | None, created: float | None) -> bool:
    if not pid or not alive(pid):
        return False
    try:
        return psutil.Process(pid).create_time() == created
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _spawn(kind: str, path: Path | None = None) -> int:
    args = [sys.executable, "-m", "xscanner.lab_worker", kind]
    if path:
        args.append(str(path))
    with open(os.devnull, "wb") as null:
        proc = subprocess.Popen(args, stdin=null, stdout=null, stderr=null, start_new_session=True)
    return proc.pid


def start(kind: str) -> dict:
    if kind not in {"storage", "process", "network", "strange"}:
        raise HTTPException(400, "Prueba desconocida")
    s = state()
    if kind in s:
        restore(kind)
        s = state()
    if kind == "storage":
        if shutil.disk_usage(LAB).free < 384 * 1024 * 1024:
            raise HTTPException(409, "Se necesitan al menos 384 MiB libres")
        root = LAB / "storage"
        root.mkdir(mode=0o700, exist_ok=True)
        for i in range(4):
            with (root / f"xscanner-prueba-{i + 1}.bin").open("wb") as file:
                block = b"X" * (1024 * 1024)
                for _ in range(32):
                    file.write(block)
        s[kind] = {"path": str(root), "bytes": 128 * 1024 * 1024}
    elif kind == "process":
        pid = _spawn("process")
        s[kind] = {"pid": pid, "created": psutil.Process(pid).create_time(), "expires_seconds": 90}
    elif kind == "network":
        # The stopped service is the controlled fault; the action starts it.
        s[kind] = {"port": 8766, "pid": None}
    else:
        root = LAB / "strange"
        root.mkdir(mode=0o700, exist_ok=True)
        pid = _spawn("strange", root)
        s[kind] = {"path": str(root), "pid": pid, "created": psutil.Process(pid).create_time(), "expires_seconds": 90}
    save(s)
    return s[kind]


def restart_server() -> dict:
    s = state()
    if "network" not in s:
        raise HTTPException(409, "La prueba de red no está activa")
    pid = s["network"].get("pid")
    if owned_process(pid, s["network"].get("created")):
        return s["network"]
    pid = _spawn("network")
    time.sleep(0.2)
    if not alive(pid):
        raise HTTPException(409, "El puerto 8766 está ocupado o no pudo iniciar el servidor")
    s["network"]["pid"] = pid
    s["network"]["created"] = psutil.Process(pid).create_time()
    save(s)
    return s["network"]


def restore(kind: str) -> dict:
    s = state()
    item = s.get(kind)
    if not item:
        return {"restored": False, "reason": "La prueba no estaba activa"}
    before = shutil.disk_usage(LAB).free
    pid = item.get("pid")
    if owned_process(pid, item.get("created")):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            psutil.Process(pid).wait(timeout=2)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied):
            pass
    if kind in {"storage", "strange"}:
        path = Path(item["path"])
        if path.parent == LAB and path.name == kind:
            shutil.rmtree(path, ignore_errors=True)
    s.pop(kind, None)
    save(s)
    after = shutil.disk_usage(LAB).free
    return {"restored": True, "kind": kind, "free_bytes_before": before,
            "free_bytes_after": after, "recovered_bytes": max(0, after - before)}
