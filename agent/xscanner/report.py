import json
import platform
from datetime import datetime
from pathlib import Path

from . import __version__
from .config import DATA_DIR, ensure_dirs


def render_report(task: dict) -> str:
    result = task.get("result") or {}
    now = datetime.now().astimezone()
    lines = [
        "X-SCANNER — REPORTE DE DIAGNÓSTICO",
        f"Fecha: {now.isoformat()}",
        f"Zona horaria: {now.tzname()}",
        f"Equipo: {platform.node()}",
        f"Sistema: {platform.platform()}",
        f"Complemento: {__version__}",
        f"Tarea: {task['id']}",
        f"Estado: {task['status']}",
        f"Alcance: {task['kind']}",
        "Parámetros: " + json.dumps(task.get("params", {}), ensure_ascii=False),
        "",
        "RESUMEN",
        str(result.get("summary", "Sin resultado completo")),
        "",
    ]
    for label, key in (("MEDICIONES", "measurements"), ("HALLAZGOS", "findings"),
                       ("EVIDENCIA", "evidence"), ("LIMITACIONES", "limitations"),
                       ("RECOMENDACIONES", "recommendations"), ("ACCIONES", "actions"),
                       ("RESULTADOS DE REPARACIÓN", "actions_taken")):
        lines.append(label)
        value = result.get(key, [])
        if isinstance(value, list):
            lines.extend("- " + (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for v in value)
        else:
            lines.append(json.dumps(value, ensure_ascii=False))
        if not value:
            lines.append("- Ninguno registrado")
        lines.append("")
    if task.get("error"):
        lines += ["ERROR", str(task["error"]), ""]
    return "\n".join(lines)


def save_report(task: dict) -> Path:
    ensure_dirs()
    path = DATA_DIR / "reports" / f"{task['id']}.txt"
    path.write_text(render_report(task), encoding="utf-8")
    path.chmod(0o600)
    return path
