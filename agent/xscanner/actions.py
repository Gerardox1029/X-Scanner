import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

import psutil
from fastapi import HTTPException
from send2trash import send2trash

from . import labs


class Actions:
    def __init__(self):
        self.prepared: dict[str, dict] = {}
        self.normal_attempts: set[tuple[int, float]] = set()

    def _tree_snapshot(self, directory: Path) -> list[tuple]:
        if directory.is_symlink() or not directory.is_dir():
            raise HTTPException(409, "La carpeta de limpieza no está disponible")
        entries = []
        for root, dirs, files in os.walk(directory, followlinks=False):
            for name in dirs + files:
                path = Path(root) / name
                st = path.lstat()
                entries.append((str(path), st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns))
                if len(entries) > 10_000:
                    raise HTTPException(409, "Demasiados elementos para limpieza segura")
        return sorted(entries)

    def _target(self, kind: str, target: str | None) -> dict:
        if kind == "trash-file":
            if not target:
                raise HTTPException(400, "Selecciona un archivo")
            path = Path(target)
            if not path.is_absolute() or path.is_symlink() or not path.is_file():
                raise HTTPException(409, "El archivo ya no es válido")
            st = path.stat()
            return {"path": str(path), "dev": st.st_dev, "ino": st.st_ino,
                    "size": st.st_size, "mtime_ns": st.st_mtime_ns,
                    "description": f"Mover {path} a la papelera. El espacio no se libera hasta vaciarla."}
        if kind in {"terminate-process", "force-process"}:
            try:
                pid = int(target or "")
                p = psutil.Process(pid)
                own = os.getuid()
                protected = {os.getpid(), os.getppid()}
                ancestor = psutil.Process(os.getpid())
                protected.update(a.pid for a in ancestor.parents())
                name = p.name().lower()
                session_names = ("brave", "chrome", "xscanner", "gnome-shell", "gnome-session",
                                 "cinnamon", "mate-session", "xfce4-session", "plasmashell", "kwin",
                                 "xorg", "xwayland", "wayland", "systemd", "dbus", "pipewire",
                                 "wireplumber", "pulseaudio", "nm-applet", "networkmanager")
                if p.uids().real != own or pid in protected or any(x in name for x in session_names):
                    raise HTTPException(403, "Proceso protegido")
                if kind == "force-process" and (pid, p.create_time()) not in self.normal_attempts:
                    raise HTTPException(403, "Primero solicita el cierre normal del proceso")
                return {"pid": pid, "created": p.create_time(), "name": p.name(),
                        "description": ("Forzar cierre" if kind == "force-process" else "Solicitar cierre") + f" de {p.name()} (PID {pid}). Puede perderse trabajo sin guardar."}
            except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                raise HTTPException(409, "El proceso ya no está disponible")
        if kind == "reconnect-network":
            return {"description": "Reconectar el perfil activo de NetworkManager. La conexión puede interrumpirse brevemente y Linux pedirá autorización administrativa."}
        if kind in {"empty-trash", "clear-cache"}:
            home = Path.home()
            directories = ([home / ".local/share/Trash/files", home / ".local/share/Trash/info"]
                           if kind == "empty-trash" else [home / ".cache/thumbnails"])
            present = [path for path in directories if path.is_dir()]
            if not present:
                raise HTTPException(409, "No hay carpeta reconocida para limpiar")
            snapshots = {str(path): self._tree_snapshot(path) for path in present}
            count = sum(len(x) for x in snapshots.values())
            return {"directories": snapshots, "count": count,
                    "description": (f"Vaciar {count} elementos de la papelera local. No se podrán restaurar."
                                    if kind == "empty-trash" else f"Eliminar hasta {count} miniaturas de caché reconocida.")}
        if kind == "restart-lab-server":
            if "network" not in labs.state():
                raise HTTPException(409, "La prueba de red no está activa")
            return {"description": "Iniciar el servidor HTTP local de prueba en 127.0.0.1:8766."}
        raise HTTPException(400, "Acción desconocida")

    def prepare(self, kind: str, target: str | None, task: dict) -> dict:
        if task.get("status") != "complete":
            raise HTTPException(409, "El diagnóstico no está completo")
        offered = {a["kind"] for a in task["result"].get("actions", [])}
        if kind == "force-process" and "terminate-process" in offered:
            pass
        elif kind not in offered:
            raise HTTPException(403, "La acción no corresponde a este diagnóstico")
        evidence = task["result"].get("evidence", [])
        if kind == "trash-file" and target not in [item.get("path") for item in evidence if isinstance(item, dict)]:
            raise HTTPException(403, "El archivo no aparece en el diagnóstico")
        if kind in {"terminate-process", "force-process"} and target not in [str(item.get("pid")) for item in evidence if isinstance(item, dict)]:
            raise HTTPException(403, "El proceso no aparece en el diagnóstico")
        snapshot = self._target(kind, target)
        token = secrets.token_urlsafe(24)
        self.prepared[token] = {"kind": kind, "target": target, "snapshot": snapshot,
                                "expires": time.monotonic() + 120, "task_id": task["id"]}
        return {"token": token, "kind": kind, "description": snapshot["description"],
                "consequences": "La acción se ejecutará solo tras confirmar. Se comprobará el objetivo nuevamente.",
                "recovery": ("El vaciado de papelera es irreversible." if kind == "empty-trash" else
                             "La papelera permite restaurar archivos; los procesos y conexiones deben abrirse de nuevo.")}

    def execute(self, token: str) -> dict:
        prepared = self.prepared.pop(token, None)
        if not prepared or time.monotonic() > prepared["expires"]:
            raise HTTPException(409, "Confirmación vencida")
        kind = prepared["kind"]
        latest = self._target(kind, prepared["target"])
        old = prepared["snapshot"]
        keys = ("dev", "ino", "size", "mtime_ns") if kind == "trash-file" else (("pid", "created") if kind in {"terminate-process", "force-process"} else ())
        if any(latest.get(key) != old.get(key) for key in keys):
            raise HTTPException(409, "El objetivo cambió; vuelve a diagnosticar")
        if kind in {"empty-trash", "clear-cache"}:
            if latest["directories"] != old["directories"]:
                raise HTTPException(409, "El contenido cambió; vuelve a diagnosticar")
            before = psutil.disk_usage(Path.home().anchor).free
            for directory in old["directories"]:
                root = Path(directory)
                for entry in root.iterdir():
                    if entry.is_dir() and not entry.is_symlink():
                        shutil.rmtree(entry)
                    else:
                        entry.unlink()
            after = psutil.disk_usage(Path.home().anchor).free
            return {"message": "Limpieza completada", "free_bytes_before": before,
                    "free_bytes_after": after, "items_examined": old["count"],
                    "_task_id": prepared["task_id"]}
        if kind == "trash-file":
            path = Path(old["path"])
            before = psutil.disk_usage(path.anchor).free
            send2trash(path)
            after = psutil.disk_usage(path.anchor).free
            return {"message": "Archivo movido a la papelera", "free_bytes_before": before,
                    "free_bytes_after": after, "note": "La papelera del mismo disco no libera espacio todavía.",
                    "_task_id": prepared["task_id"]}
        if kind in {"terminate-process", "force-process"}:
            p = psutil.Process(old["pid"])
            if kind == "force-process":
                p.kill()
            else:
                p.terminate()
            try:
                p.wait(timeout=3)
                stopped = True
            except psutil.TimeoutExpired:
                stopped = False
            if kind == "terminate-process" and not stopped:
                self.normal_attempts.add((old["pid"], old["created"]))
            return {"message": "Se envió la señal de cierre", "stopped": stopped,
                    "cpu_percent_after": psutil.cpu_percent(interval=1),
                    "note": "Si sigue activo, el cierre forzado requiere otra confirmación.",
                    "_task_id": prepared["task_id"]}
        if kind == "restart-lab-server":
            return {"message": "Servidor de prueba reiniciado", **labs.restart_server(),
                    "_task_id": prepared["task_id"]}
        if kind == "reconnect-network":
            helper = Path("/usr/lib/xscanner/privileged.py")
            if not helper.is_file():
                raise HTTPException(501, "El ejecutor administrativo no está instalado")
            try:
                proc = subprocess.run(["pkexec", str(helper), "reconnect-active"],
                    capture_output=True, text=True, timeout=40, check=False)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                raise HTTPException(503, "No se completó la autorización de Linux")
            if proc.returncode:
                raise HTTPException(409, "Reconexión cancelada o fallida: " + proc.stderr[-300:])
            return {"message": "Se solicitó la reconexión", "output": proc.stdout[-300:],
                    "_task_id": prepared["task_id"]}
        raise HTTPException(400, "Acción desconocida")
