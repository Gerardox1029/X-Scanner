import sys
from urllib.parse import urlparse

from . import labs
from .config import save_settings, settings


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "origin":
        origin = sys.argv[2].rstrip("/")
        parsed = urlparse(origin)
        if not ((parsed.scheme == "https" and parsed.hostname) or
                (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"})) or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise SystemExit("Usa el origen HTTPS exacto, por ejemplo https://mi-sitio.netlify.app")
        value = settings()
        value["origin"] = origin
        save_settings(value)
        print("Origen configurado. Reinicia el complemento.")
        return
    if len(sys.argv) == 2 and sys.argv[1] == "restore-labs":
        for kind in ("storage", "process", "network", "strange"):
            print(kind, labs.restore(kind))
        return
    raise SystemExit("Uso: xscanner-cli origin https://sitio.netlify.app | restore-labs")


if __name__ == "__main__":
    main()
