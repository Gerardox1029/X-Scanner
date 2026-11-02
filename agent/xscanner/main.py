import json
import io
import os
import platform
import re
import socket
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from . import __version__, diagnostics, labs
from .actions import Actions
from .config import CONFIG_DIR, DATA_DIR, allowed_origins, ensure_dirs, save_settings, settings
from .report import save_report
from .security import Security, password_hash, verify_password


class PairInput(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class DiagnoseInput(BaseModel):
    kind: str
    params: dict = Field(default_factory=dict)


class PrepareInput(BaseModel):
    task_id: str
    kind: str
    target: str | None = None


class ExecuteInput(BaseModel):
    token: str


class PasswordInput(BaseModel):
    password: str = Field(min_length=10, max_length=200)


class ScriptInput(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    source: str = Field(min_length=1, max_length=20_000)


class TaskStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.tasks: dict[str, dict] = {}
        self.cancel: dict[str, threading.Event] = {}
        self.history_path = DATA_DIR / "history.json"
        try:
            loaded = json.loads(self.history_path.read_text())
            self.tasks = {t["id"]: t for t in loaded if isinstance(t, dict) and "id" in t}
        except (FileNotFoundError, ValueError):
            pass

    def persist(self):
        ensure_dirs()
        recent = list(self.tasks.values())[-100:]
        tmp = self.history_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(recent, ensure_ascii=False))
        tmp.chmod(0o600)
        tmp.replace(self.history_path)

    def create(self, kind: str, params: dict) -> dict:
        task = {"id": str(uuid.uuid4()), "kind": kind, "params": params,
                "status": "queued", "progress": 0, "result": None, "error": None,
                "created": datetime.now().astimezone().isoformat()}
        with self.lock:
            self.tasks[task["id"]] = task
            event = threading.Event()
            self.cancel[task["id"]] = event
        thread = threading.Thread(target=self.run, args=(task["id"], event), daemon=True)
        thread.start()
        return task.copy()

    def run(self, task_id: str, event: threading.Event):
        with self.lock:
            task = self.tasks[task_id]
            task["status"] = "running"
            task["progress"] = 10
        try:
            outcome = diagnostics.diagnose(task["kind"], task["params"], event)
            with self.lock:
                task["result"] = outcome
                task["status"] = "cancelled" if event.is_set() else "complete"
                task["progress"] = 100
        except InterruptedError as exc:
            with self.lock:
                task["status"] = "cancelled"
                task["error"] = str(exc)
                task["result"] = {"summary": "Diagnóstico cancelado", "limitations": ["Resultado incompleto"]}
        except Exception as exc:
            with self.lock:
                task["status"] = "failed"
                task["error"] = f"{type(exc).__name__}: {exc}"
                task["result"] = {"summary": "Diagnóstico incompleto", "limitations": ["La tarea falló; revisa el error"]}
        finally:
            with self.lock:
                task["finished"] = datetime.now().astimezone().isoformat()
                save_report(task)
                self.persist()
                self.cancel.pop(task_id, None)

    def get(self, task_id: str) -> dict:
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                raise HTTPException(404, "Tarea no encontrada")
            return json.loads(json.dumps(task))

    def stop(self, task_id: str) -> dict:
        with self.lock:
            event = self.cancel.get(task_id)
            if not event:
                raise HTTPException(409, "La tarea ya terminó")
            event.set()
        return {"cancel_requested": True}


def create_app() -> FastAPI:
    ensure_dirs()
    app = FastAPI(title="X-Scanner local API", version=__version__, docs_url=None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=list(allowed_origins()),
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
    security = Security()
    tasks = TaskStore()
    actions = Actions()
    app.state.security = security
    app.state.tasks = tasks

    def auth(request: Request):
        return security.require(request)

    def tech(request: Request):
        return security.require_tech(request)

    @app.get("/api/v1/health")
    def health():
        return {"service": "xscanner-local-agent", "api_version": 1,
                "agent_version": __version__, "paired_available": bool(security.pair_code)}

    @app.post("/api/v1/pair")
    def pair(body: PairInput, request: Request):
        security.check_origin(request)
        return {"token": security.pair(body.code), "api_version": 1}

    @app.get("/api/v1/capabilities", dependencies=[Depends(auth)])
    def capabilities():
        release = platform.freedesktop_os_release()
        distro = release.get("ID", "desconocida")
        distro_version = release.get("VERSION_ID", "")
        supported_distro = (distro == "linuxmint" and distro_version.startswith("22")) or (distro == "ubuntu" and distro_version.startswith("24.04"))
        systemd_available = Path("/run/systemd/system").is_dir()
        network_manager_available = bool(__import__("shutil").which("nmcli"))
        supported = supported_distro and systemd_available and network_manager_available
        return {"platform": platform.platform(), "python": platform.python_version(),
                "distribution": distro, "distribution_version": distro_version,
                "initially_supported": supported,
                "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "desconocido"),
                "systemd_available": systemd_available,
                "network_manager_available": network_manager_available,
                "helper_installed": Path("/usr/lib/xscanner/privileged.py").is_file(),
                "net_hogs_available": bool(__import__("shutil").which("nethogs")),
                "origin": next(iter(allowed_origins())), "kinds": sorted(diagnostics.KINDS)}

    @app.post("/api/v1/tasks", dependencies=[Depends(auth)])
    def start(body: DiagnoseInput):
        if body.kind not in diagnostics.KINDS:
            raise HTTPException(400, "Diagnóstico desconocido")
        if len(json.dumps(body.params)) > 4000:
            raise HTTPException(413, "Parámetros demasiado grandes")
        return tasks.create(body.kind, body.params)

    @app.get("/api/v1/tasks", dependencies=[Depends(auth)])
    def history():
        with tasks.lock:
            return list(reversed([{"id": t["id"], "kind": t["kind"], "status": t["status"],
                                    "created": t["created"], "summary": (t.get("result") or {}).get("summary")}
                                  for t in tasks.tasks.values()]))[:100]

    @app.get("/api/v1/tasks/{task_id}", dependencies=[Depends(auth)])
    def get_task(task_id: str):
        return tasks.get(task_id)

    @app.post("/api/v1/tasks/{task_id}/cancel", dependencies=[Depends(auth)])
    def cancel_task(task_id: str):
        return tasks.stop(task_id)

    @app.get("/api/v1/tasks/{task_id}/report", dependencies=[Depends(auth)])
    def report(task_id: str):
        tasks.get(task_id)
        path = DATA_DIR / "reports" / f"{task_id}.txt"
        if not path.is_file():
            raise HTTPException(409, "El reporte estará disponible al terminar")
        return FileResponse(path, media_type="text/plain; charset=utf-8", filename=f"xscanner-{task_id}.txt")

    @app.get("/api/v1/tasks/{task_id}/file", dependencies=[Depends(auth)])
    def file(task_id: str, path: str):
        task = tasks.get(task_id)
        evidence = (task.get("result") or {}).get("evidence", [])
        if path not in [e.get("path") for e in evidence if isinstance(e, dict)]:
            raise HTTPException(403, "Archivo fuera del resultado")
        target = Path(path)
        if target.is_symlink() or not target.is_file():
            raise HTTPException(404, "Archivo no disponible")
        return FileResponse(target, filename=target.name)

    @app.get("/api/v1/tasks/{task_id}/thumbnail", dependencies=[Depends(auth)])
    def thumbnail(task_id: str, path: str):
        from PIL import Image, ImageOps
        task = tasks.get(task_id)
        if task["kind"] != "storage-photo":
            raise HTTPException(403, "La tarea no es una búsqueda de fotos")
        evidence = (task.get("result") or {}).get("evidence", [])
        if path not in [e.get("path") for e in evidence if isinstance(e, dict)]:
            raise HTTPException(403, "Imagen fuera del resultado")
        target = Path(path)
        if target.is_symlink() or not target.is_file() or target.stat().st_size > 80 * 1024 * 1024:
            raise HTTPException(404, "Vista previa no disponible")
        try:
            with Image.open(target) as original:
                image = ImageOps.exif_transpose(original)
                image.thumbnail((320, 240))
                output = io.BytesIO()
                image.convert("RGB").save(output, format="JPEG", quality=78)
            return Response(output.getvalue(), media_type="image/jpeg")
        except (OSError, ValueError):
            raise HTTPException(404, "Vista previa no disponible")

    @app.post("/api/v1/actions/prepare", dependencies=[Depends(auth)])
    def prepare(body: PrepareInput):
        return actions.prepare(body.kind, body.target, tasks.get(body.task_id))

    @app.post("/api/v1/actions/execute", dependencies=[Depends(auth)])
    def execute(body: ExecuteInput):
        outcome = actions.execute(body.token)
        task_id = outcome.pop("_task_id")
        with tasks.lock:
            task = tasks.tasks[task_id]
            task["result"].setdefault("actions_taken", []).append(outcome)
            save_report(task)
            tasks.persist()
        return outcome

    @app.get("/api/v1/labs", dependencies=[Depends(auth)])
    def lab_status():
        return labs.state()

    @app.post("/api/v1/labs/{kind}/start", dependencies=[Depends(auth)])
    def lab_start(kind: str):
        return labs.start(kind)

    @app.post("/api/v1/labs/{kind}/restore", dependencies=[Depends(auth)])
    def lab_restore(kind: str):
        if kind not in {"storage", "process", "network", "strange"}:
            raise HTTPException(400, "Prueba desconocida")
        return labs.restore(kind)

    @app.get("/api/v1/technician/status", dependencies=[Depends(auth)])
    def technician_status():
        return {"configured": bool(settings().get("tech_password"))}

    @app.post("/api/v1/technician/password", dependencies=[Depends(auth)])
    def set_technician_password(body: PasswordInput, request: Request):
        current = settings()
        if current.get("tech_password"):
            raise HTTPException(409, "La contraseña ya está configurada; cámbiala desde la configuración local")
        current["tech_password"] = password_hash(body.password)
        save_settings(current)
        security.require(request).tech_until = time.monotonic() + 900
        return {"configured": True}

    @app.post("/api/v1/technician/unlock", dependencies=[Depends(auth)])
    def technician_unlock(body: PasswordInput, request: Request):
        security.check_tech_attempt()
        if not verify_password(body.password, settings().get("tech_password", "")):
            security.tech_failure()
            raise HTTPException(401, "Contraseña incorrecta")
        security.failed_tech = 0
        security.require(request).tech_until = time.monotonic() + 900
        return {"unlocked_for_seconds": 900}

    @app.get("/api/v1/technician/scripts", dependencies=[Depends(tech)])
    def scripts():
        folder = DATA_DIR / "scripts"
        folder.mkdir(mode=0o700, exist_ok=True)
        return sorted(p.stem for p in folder.glob("*.py") if re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", p.stem))

    @app.get("/api/v1/technician/scripts/{name}", dependencies=[Depends(tech)])
    def read_script(name: str):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", name):
            raise HTTPException(400, "Nombre inválido")
        path = DATA_DIR / "scripts" / f"{name}.py"
        if not path.is_file():
            raise HTTPException(404, "Script no encontrado")
        return {"name": name, "category": "usuario", "source": path.read_text()}

    @app.post("/api/v1/technician/scripts", dependencies=[Depends(tech)])
    def save_script(body: ScriptInput):
        folder = DATA_DIR / "scripts"
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / f"{body.name}.py"
        versions = folder / "versions"
        versions.mkdir(mode=0o700, exist_ok=True)
        if path.exists():
            version = versions / f"{body.name}-{int(time.time())}.py"
            version.write_bytes(path.read_bytes())
            version.chmod(0o600)
        path.write_text(body.source)
        path.chmod(0o600)
        return {"name": body.name, "saved": True}

    @app.post("/api/v1/technician/scripts/{name}/run", dependencies=[Depends(tech)])
    def run_script(name: str):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", name):
            raise HTTPException(400, "Nombre inválido")
        path = DATA_DIR / "scripts" / f"{name}.py"
        if not path.is_file():
            raise HTTPException(404, "Script no encontrado")
        import resource
        import subprocess

        def limits():
            resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))

        try:
            proc = subprocess.run([sys.executable, str(path)], cwd=str(DATA_DIR), capture_output=True,
                                  text=True, timeout=30, preexec_fn=limits, check=False)
        except subprocess.TimeoutExpired:
            raise HTTPException(408, "El script superó 30 segundos")
        return {"exit_code": proc.returncode, "stdout": proc.stdout[-10_000:], "stderr": proc.stderr[-10_000:]}

    return app


app = create_app()


def main():
    import uvicorn

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 8765))
        listener.listen(128)
    except OSError:
        print("X-Scanner: el puerto 8765 está ocupado; no se conectará a otro servicio.", file=sys.stderr)
        sys.exit(1)
    print(f"X-Scanner: código temporal de vinculación {app.state.security.pair_code} (10 minutos)", file=sys.stderr, flush=True)
    print(f"Origen permitido: {next(iter(allowed_origins()))}", file=sys.stderr, flush=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
    server = uvicorn.Server(config)
    import asyncio
    try:
        asyncio.run(server.serve(sockets=[listener]))
    except KeyboardInterrupt:
        pass
    finally:
        listener.close()


if __name__ == "__main__":
    main()
