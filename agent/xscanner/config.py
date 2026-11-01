import json
import os
from pathlib import Path

APP = "xscanner"
HOME = Path.home()


def xdg(env: str, default: str) -> Path:
    return Path(os.environ.get(env, str(HOME / default))) / APP


CONFIG_DIR = xdg("XDG_CONFIG_HOME", ".config")
DATA_DIR = xdg("XDG_DATA_HOME", ".local/share")
CACHE_DIR = xdg("XDG_CACHE_HOME", ".cache")


def ensure_dirs() -> None:
    for path in (CONFIG_DIR, DATA_DIR, CACHE_DIR, DATA_DIR / "reports", DATA_DIR / "labs"):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)


def settings() -> dict:
    ensure_dirs()
    path = CONFIG_DIR / "settings.json"
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def save_settings(value: dict) -> None:
    ensure_dirs()
    path = CONFIG_DIR / "settings.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    tmp.chmod(0o600)
    tmp.replace(path)


def allowed_origins() -> set[str]:
    configured = settings().get("origin") or os.environ.get("XSCANNER_ORIGIN", "http://localhost:5173")
    return {configured.rstrip("/")}
