import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from threading import Event

import psutil
from PIL import Image

from .config import DATA_DIR, HOME

KINDS = {
    "storage-space", "storage-photo", "storage-file",
    "process-slow", "process-frozen", "process-heat",
    "network-offline", "network-slow", "network-page", "full-scan", "strange-case",
}


def result(summary: str, **kwargs) -> dict:
    return {"summary": summary, "measurements": [], "findings": [], "evidence": [],
            "limitations": [], "recommendations": [], "actions": [], **kwargs}


def check(cancel: Event) -> None:
    if cancel.is_set():
        raise InterruptedError("Diagnóstico cancelado por la persona")


def wait(seconds: int, cancel: Event) -> None:
    for _ in range(seconds):
        check(cancel)
        time.sleep(1)


def same_content(left: Path, right: Path, cancel: Event) -> bool:
    try:
        with left.open("rb") as a, right.open("rb") as b:
            while True:
                check(cancel)
                first = a.read(1024 * 1024)
                second = b.read(1024 * 1024)
                if first != second:
                    return False
                if not first:
                    return True
    except OSError:
        return False


def local_mounts() -> list:
    excluded = {"proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup", "cgroup2", "squashfs", "overlay", "autofs", "tracefs", "debugfs", "securityfs", "pstore", "fusectl", "mqueue"}
    seen = set()
    out = []
    for part in psutil.disk_partitions(all=True):
        if part.fstype in excluded or part.device.startswith("//") or ":" in part.device:
            continue
        try:
            device = os.stat(part.mountpoint).st_dev
        except OSError:
            continue
        if device in seen:
            continue
        seen.add(device)
        out.append(part)
    return out


def walk_files(root: Path, cancel: Event, limit: int = 20_000, denied: list[str] | None = None):
    count = 0
    stack = [root]
    visited = 0
    while stack and count < limit and visited < limit:
        check(cancel)
        directory = stack.pop()
        visited += 1
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            count += 1
                            yield Path(entry.path), entry.stat(follow_symlinks=False)
                    except PermissionError:
                        if denied is not None and len(denied) < 30:
                            denied.append(entry.path)
                        continue
                    except FileNotFoundError:
                        continue
        except PermissionError:
            if denied is not None and len(denied) < 30:
                denied.append(str(directory))
            continue
        except (FileNotFoundError, NotADirectoryError):
            continue


def user_scan_roots() -> list[Path]:
    """Return visible user folders, never virtual system trees."""
    candidates = [HOME / name for name in ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music")]
    candidates.extend([Path(value).expanduser() for key, value in os.environ.items() if key.startswith("XDG_") and key.endswith("_DIR")])
    candidates.append(HOME)
    roots = []
    seen = set()
    for path in candidates:
        try:
            path = path.resolve()
        except OSError:
            continue
        if path.is_dir() and path not in seen and (path == HOME or path.is_relative_to(HOME)):
            seen.add(path)
            roots.append(path)
    return roots


def storage_space(params: dict, cancel: Event) -> dict:
    r = result("Capacidad de los sistemas locales montados y archivos grandes del usuario")
    for part in local_mounts():
        check(cancel)
        try:
            usage = psutil.disk_usage(part.mountpoint)
            st = os.statvfs(part.mountpoint)
            r["measurements"].append({"volume": part.mountpoint, "used_bytes": usage.used,
                "free_bytes": usage.free, "percent": usage.percent, "inodes_free": st.f_favail,
                "inodes_total": st.f_files})
            if usage.percent >= 90:
                r["findings"].append(f"{part.mountpoint}: {usage.percent:.1f}% ocupado")
        except (OSError, PermissionError) as exc:
            r["limitations"].append(f"{part.mountpoint}: {exc}")
    big = []
    denied = []
    folders = defaultdict(int)
    for root in user_scan_roots():
        for path, st in walk_files(root, cancel, 20_000, denied):
            if path != HOME:
                folders[path.relative_to(HOME).parts[0]] += st.st_size
            if st.st_size >= 16 * 1024 * 1024:
                big.append({"path": str(path), "name": path.name, "bytes": st.st_size})
    r["evidence"] = sorted(big, key=lambda item: -item["bytes"])[:30]
    r["measurements"].append({"largest_home_folders_bytes": dict(sorted(folders.items(), key=lambda x: -x[1])[:10])})
    r["limitations"].extend(f"Ruta inaccesible: {path}" for path in denied)
    r["limitations"].append("La búsqueda de archivos grandes examina hasta 20 000 archivos del usuario; las rutas inaccesibles se omiten.")
    trash = HOME / ".local/share/Trash/files"
    if trash.exists():
        r["measurements"].append({"trash_items": sum(1 for _ in trash.iterdir())})
        r["actions"].append({"kind": "empty-trash", "description": "Vaciar la papelera local por separado; irreversible"})
    thumbnails = HOME / ".cache/thumbnails"
    if thumbnails.is_dir():
        r["measurements"].append({"recognized_cache": str(thumbnails)})
        r["actions"].append({"kind": "clear-cache", "description": "Limpiar miniaturas reconocidas del usuario"})
    r["recommendations"].append("Mover a la papelera no libera espacio en el mismo disco hasta vaciarla por separado.")
    if params.get("duplicates"):
        groups = defaultdict(list)
        for root in user_scan_roots():
            for path, st in walk_files(root, cancel, 20_000):
                if 0 < st.st_size <= 2 * 1024 * 1024 * 1024:
                    groups[st.st_size].append((path, st))
        duplicate_groups = []
        for candidates in groups.values():
            if len(candidates) < 2:
                continue
            hashes = defaultdict(list)
            for path, st in candidates:
                check(cancel)
                try:
                    h = hashlib.sha256()
                    with path.open("rb") as file:
                        for chunk in iter(lambda: file.read(1024 * 1024), b""):
                            check(cancel)
                            h.update(chunk)
                    hashes[h.hexdigest()].append((path, st))
                except OSError:
                    continue
            for matches in hashes.values():
                unique = {(st.st_dev, st.st_ino): str(path) for path, st in matches}
                if len(unique) > 1:
                    paths = list(unique.values())
                    confirmed = [paths[0]]
                    for candidate in paths[1:]:
                        if same_content(Path(paths[0]), Path(candidate), cancel):
                            confirmed.append(candidate)
                    if len(confirmed) > 1:
                        duplicate_groups.append(confirmed)
        r["evidence"].append({"duplicate_groups": duplicate_groups[:20]})
        r["limitations"].append("Los hashes detectan candidatos; revisa cada archivo antes de eliminarlo.")
    r["actions"].append({"kind": "trash-file", "description": "Mover un archivo elegido a la papelera"})
    return r


PHOTO_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".mp4", ".mov", ".avi", ".mkv"}


def capture_date(path: Path) -> str | None:
    if path.suffix.casefold() in {".jpg", ".jpeg", ".png", ".webp"}:
        try:
            with Image.open(path) as image:
                raw = image.getexif().get(36867)
            if raw:
                return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S").isoformat()
        except (OSError, ValueError, SyntaxError):
            pass
    if path.suffix.casefold() in {".mp4", ".mov", ".avi", ".mkv"} and shutil.which("ffprobe"):
        try:
            out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format_tags=creation_time",
                                  "-of", "json", str(path)], capture_output=True, text=True, timeout=3, check=False)
            return json.loads(out.stdout).get("format", {}).get("tags", {}).get("creation_time")
        except (subprocess.TimeoutExpired, ValueError, OSError):
            pass
    return None


def search_files(params: dict, cancel: Event, photos: bool) -> dict:
    root = Path(params.get("root") or HOME).expanduser().resolve()
    if not root.is_dir():
        return result("La carpeta indicada no existe", limitations=[str(root)])
    name = str(params.get("name") or "").casefold()
    ext = str(params.get("extension") or "").casefold().lstrip(".")
    month = str(params.get("month") or "")
    expanded = bool(params.get("expand_month"))
    month_range = None
    if month:
        try:
            y, m = map(int, month.split("-"))
            if not 1 <= m <= 12:
                raise ValueError
            indexes = [y * 12 + m + offset for offset in ((-1, 0, 1) if expanded else (0,))]
            month_range = {((i - 1) // 12, (i - 1) % 12 + 1) for i in indexes}
        except ValueError:
            return result("Mes inválido", limitations=["Usa AAAA-MM"])
    matches = []
    denied = []
    for path, st in walk_files(root, cancel, 20_000, denied):
        suffix = path.suffix.casefold()
        if photos and suffix not in PHOTO_EXT:
            continue
        if name and name not in path.name.casefold():
            continue
        if ext and suffix != "." + ext:
            continue
        if params.get("min_bytes") and st.st_size < int(params["min_bytes"]):
            continue
        if params.get("max_bytes") and st.st_size > int(params["max_bytes"]):
            continue
        captured = capture_date(path) if photos else None
        try:
            date_used = datetime.fromisoformat(captured) if captured else datetime.fromtimestamp(st.st_mtime)
        except ValueError:
            date_used = datetime.fromtimestamp(st.st_mtime)
        if month_range and (date_used.year, date_used.month) not in month_range:
            continue
        content = str(params.get("content") or "")
        if content and not photos:
            if st.st_size > 2 * 1024 * 1024 or suffix not in {".txt", ".md", ".csv", ".log"}:
                continue
            try:
                if content.casefold() not in path.read_text(errors="ignore").casefold():
                    continue
            except OSError:
                continue
        matches.append({"path": str(path), "name": path.name, "bytes": st.st_size,
                        "modified": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(),
                        "created": datetime.fromtimestamp(st.st_birthtime).astimezone().isoformat() if hasattr(st, "st_birthtime") else None,
                        "captured": captured, "date_used": "captura" if captured else "modificación"})
        if len(matches) >= 500:
            break
    r = result(f"{len(matches)} archivos coincidentes", evidence=matches,
               measurements=[{"matches": len(matches), "root": str(root), "date_filter": month,
                              "expanded_month": expanded}])
    r["limitations"].append("Máximo 20 000 archivos examinados y 500 resultados. En fotos se usa captura EXIF/video cuando está disponible; de otro modo modificación. La creación solo aparece si el sistema la expone.")
    if photos and not shutil.which("ffprobe"):
        r["limitations"].append("ffprobe no está instalado; fecha de captura de video no disponible.")
    r["limitations"].extend(f"Ruta inaccesible: {path}" for path in denied)
    r["actions"].append({"kind": "download-file", "description": "Descargar un archivo legible"})
    return r


def process_slow(params: dict, cancel: Event) -> dict:
    before = psutil.disk_io_counters()
    proc_before = {}
    for p in psutil.process_iter(["pid", "cpu_times", "create_time"]):
        try:
            i = p.info
            if i["cpu_times"]:
                proc_before[(i["pid"], i["create_time"])] = sum(i["cpu_times"][:2])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    psutil.cpu_percent(interval=None, percpu=True)
    start = time.monotonic()
    samples = []
    while time.monotonic() - start < 10:
        check(cancel)
        samples.append(psutil.cpu_percent(interval=1, percpu=True))
    cpu = [round(sum(row[i] for row in samples) / len(samples), 1) for i in range(len(samples[0]))]
    after = psutil.disk_io_counters()
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    processes = []
    for p in psutil.process_iter(["pid", "name", "username", "memory_info", "cpu_times", "create_time"]):
        try:
            info = p.info
            processes.append({"pid": info["pid"], "name": info["name"],
                "user": info["username"], "rss_bytes": info["memory_info"].rss if info["memory_info"] else 0,
                "cpu_percent_sample": round(100 * max(0, sum(info["cpu_times"][:2]) - proc_before.get((info["pid"], info["create_time"]), sum(info["cpu_times"][:2]))) / max(time.monotonic() - start, 0.1), 1) if info["cpu_times"] else 0,
                "created": info["create_time"]})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    processes.sort(key=lambda p: (-p["cpu_percent_sample"], -p["rss_bytes"]))
    r = result("Muestreo de diez segundos de CPU, memoria y disco",
        measurements=[{"cpu_percent_by_core": cpu, "memory_available_bytes": memory.available,
            "swap_used_bytes": swap.used, "disk_read_bytes": after.read_bytes - before.read_bytes,
            "disk_write_bytes": after.write_bytes - before.write_bytes}],
        evidence=processes[:30])
    r["limitations"].append("El uso de CPU por proceso es una muestra de diez segundos; una muestra no prueba por sí sola la causa de lentitud.")
    r["actions"].append({"kind": "terminate-process", "description": "Solicitar cierre de una aplicación del usuario"})
    return r


def process_frozen(params: dict, cancel: Event) -> dict:
    query = str(params.get("name") or "").casefold()
    matches = []
    for p in psutil.process_iter(["pid", "name", "username", "status", "memory_info", "create_time"]):
        check(cancel)
        try:
            i = p.info
            if query in (i["name"] or "").casefold():
                matches.append({"pid": i["pid"], "name": i["name"], "user": i["username"],
                    "status": i["status"], "rss_bytes": i["memory_info"].rss if i["memory_info"] else 0,
                    "created": i["create_time"]})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    r = result(f"{len(matches)} procesos asociados", evidence=matches[:100])
    r["limitations"].append("El estado y el consumo no demuestran que una ventana esté congelada; confirma antes de cerrar.")
    r["actions"].append({"kind": "terminate-process", "description": "Cierre normal; forzado solo tras nueva confirmación"})
    return r


def process_heat(params: dict, cancel: Event) -> dict:
    r = process_slow(params, cancel)
    r["summary"] = "Carga sostenida y sensores de temperatura disponibles"
    try:
        sensors = psutil.sensors_temperatures()
        r["measurements"].append({"temperatures_celsius": {name: [x.current for x in values] for name, values in sensors.items()}})
        if not sensors:
            r["limitations"].append("No hay sensores de temperatura accesibles.")
    except (AttributeError, OSError):
        r["limitations"].append("No se pudieron leer sensores de temperatura.")
    r["limitations"].append("Sin umbrales del fabricante no se diagnostica sobrecalentamiento solo por temperatura.")
    r["recommendations"].append("Si persiste el calor o ruido, revisa ventilación y limpieza física con el equipo apagado.")
    return r


def command(args: list[str], timeout: int = 5) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False).stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def network_offline(params: dict, cancel: Event) -> dict:
    check(cancel)
    interfaces = []
    for name, addresses in psutil.net_if_addrs().items():
        interfaces.append({"name": name, "addresses": [a.address for a in addresses if a.family in (socket.AF_INET, socket.AF_INET6)]})
    route = command(["ip", "route", "show", "default"])
    dns_servers = []
    try:
        dns_servers = [line.split()[1] for line in Path("/etc/resolv.conf").read_text().splitlines() if line.startswith("nameserver ")]
    except OSError:
        pass
    dns_ok = False
    outside_ok = False
    try:
        dns_ok = bool(socket.getaddrinfo("example.com", 443, type=socket.SOCK_STREAM))
    except OSError:
        pass
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=3):
            outside_ok = True
    except OSError:
        pass
    r = result("Estado de interfaz, ruta, DNS y conexión exterior",
        measurements=[{"interfaces": interfaces, "default_route": route, "dns_servers": dns_servers,
                       "dns_resolves": dns_ok, "outside_tcp": outside_ok}])
    if not outside_ok:
        r["findings"].append("No se logró conexión TCP exterior en la prueba.")
    if not dns_ok:
        r["findings"].append("La resolución DNS de prueba falló.")
    r["limitations"].append("Un servidor externo puede bloquear la prueba; un resultado aislado no prueba fallo total de internet.")
    r["actions"].append({"kind": "reconnect-network", "description": "Reconectar el perfil activo de NetworkManager con autorización de Linux"})
    return r


def network_slow(params: dict, cancel: Event) -> dict:
    before = psutil.net_io_counters(pernic=True)
    start = time.monotonic()
    wait(10, cancel)
    duration = time.monotonic() - start
    after = psutil.net_io_counters(pernic=True)
    traffic = []
    for name, end in after.items():
        if name in before and name != "lo":
            traffic.append({"interface": name, "received_bytes_per_second": round((end.bytes_recv - before[name].bytes_recv) / duration),
                            "sent_bytes_per_second": round((end.bytes_sent - before[name].bytes_sent) / duration)})
    ping = command(["ping", "-n", "-c", "3", "-W", "2", "1.1.1.1"], timeout=8)
    r = result("Tráfico de interfaces y latencia de prueba durante diez segundos",
               measurements=traffic, evidence=[ping] if ping else [])
    loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", ping)
    timing = re.search(r"(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = [\d.]+/([\d.]+)/", ping)
    if loss or timing:
        r["measurements"].append({"packet_loss_percent": float(loss.group(1)) if loss else None,
                                  "latency_average_ms": float(timing.group(1)) if timing else None})
    if params.get("per_process"):
        helper = Path("/usr/lib/xscanner/privileged.py")
        if not helper.is_file() or not Path("/usr/sbin/nethogs").is_file():
            r["limitations"].append("NetHogs o el ejecutor administrativo no está instalado; no se midió tráfico por proceso.")
        else:
            try:
                proc = subprocess.run(["pkexec", str(helper), "nethogs-10s"], capture_output=True,
                                      text=True, timeout=30, check=False)
                if proc.returncode:
                    r["limitations"].append("Medición por proceso cancelada o fallida: " + proc.stderr[-200:])
                else:
                    attributed = {}
                    unknown = 0.0
                    for line in proc.stdout.splitlines():
                        fields = line.split()
                        if len(fields) != 3:
                            continue
                        try:
                            rate = float(fields[1]) + float(fields[2])
                        except ValueError:
                            continue
                        parts = fields[0].rsplit("/", 2)
                        if len(parts) == 3 and parts[1].isdigit():
                            pid = int(parts[1])
                            if pid not in attributed or rate > attributed[pid]["kilobytes_per_second"]:
                                attributed[pid] = {"pid": pid, "process": parts[0], "kilobytes_per_second": rate}
                        else:
                            unknown = max(unknown, rate)
                    r["evidence"].extend(sorted(attributed.values(), key=lambda x: -x["kilobytes_per_second"])[:5])
                    r["measurements"].append({"unknown_kilobytes_per_second": unknown})
                    r["limitations"].append("La atribución de NetHogs es una muestra de diez segundos; el tráfico desconocido no se asigna a ningún proceso.")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                r["limitations"].append("No se completó la medición administrativa con NetHogs.")
    else:
        r["limitations"].append("La medición opcional por proceso no se solicitó; requiere NetHogs y autorización administrativa.")
    if not ping:
        r["limitations"].append("No hubo respuesta ICMP o ping no está disponible.")
    return r


def network_page(params: dict, cancel: Event) -> dict:
    raw = str(params.get("url") or "http://127.0.0.1:8766/")
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return result("URL inválida", limitations=["Se acepta una URL HTTP o HTTPS sin credenciales."])
    check(cancel)
    dns = []
    try:
        dns = sorted({a[4][0] for a in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))})
    except OSError as exc:
        return result("No se resolvió el nombre", findings=[str(exc)])
    try:
        request = urllib.request.Request(raw, method="GET", headers={"User-Agent": "X-Scanner/0.1"})
        with urllib.request.urlopen(request, timeout=7) as response:
            status = response.status
        r = result(f"La página respondió HTTP {status}", measurements=[{"url": raw, "addresses": dns, "status": status}])
    except urllib.error.HTTPError as exc:
        r = result(f"El servidor respondió HTTP {exc.code}", measurements=[{"url": raw, "addresses": dns, "status": exc.code}])
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        r = result("No se abrió la página", findings=[str(exc)], measurements=[{"url": raw, "addresses": dns}])
    if parsed.hostname in {"127.0.0.1", "localhost"} and parsed.port == 8766:
        r["actions"].append({"kind": "restart-lab-server", "description": "Restaurar servidor HTTP de prueba de X-Scanner"})
    return r


def strange_case(params: dict, cancel: Event) -> dict:
    lab = str(DATA_DIR / "labs")
    found = []
    for p in psutil.process_iter(["pid", "name", "open_files"]):
        check(cancel)
        try:
            fd_dir = Path(f"/proc/{p.pid}/fd")
            for fd in fd_dir.iterdir():
                try:
                    target = os.readlink(fd)
                    if target.startswith(lab) and target.endswith(" (deleted)"):
                        found.append({"pid": p.pid, "process": p.name(), "fd": str(fd), "deleted_path": target})
                except OSError:
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    r = result("Archivos de laboratorio eliminados pero abiertos", evidence=found)
    if found:
        r["findings"].append("Un proceso conserva un archivo sin nombre; el espacio puede seguir ocupado hasta que cierre.")
    r["limitations"].append("Se examinan descriptores visibles del laboratorio; otros procesos pueden requerir permisos adicionales.")
    r["recommendations"].append("Caso técnico: restaura el laboratorio o espera el temporizador; no hay reparación automática.")
    return r


FUNCTIONS = {
    "storage-space": storage_space, "storage-photo": lambda p, c: search_files(p, c, True),
    "storage-file": lambda p, c: search_files(p, c, False), "process-slow": process_slow,
    "process-frozen": process_frozen, "process-heat": process_heat,
    "network-offline": network_offline, "network-slow": network_slow,
    "network-page": network_page, "strange-case": strange_case,
}


def diagnose(kind: str, params: dict, cancel: Event) -> dict:
    if kind == "full-scan":
        parts = []
        for subkind in ("storage-space", "process-slow", "network-offline"):
            check(cancel)
            parts.append({"kind": subkind, "result": FUNCTIONS[subkind]({}, cancel)})
        return result("Full Scan de almacenamiento, procesos y redes", evidence=parts,
                      limitations=["Las búsquedas que requieren parámetros se ofrecen por separado. No se ejecutan reparaciones automáticas."])
    return FUNCTIONS[kind](params, cancel)
