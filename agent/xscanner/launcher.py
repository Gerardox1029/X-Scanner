import subprocess
import threading
from urllib.parse import urlparse

from .config import allowed_origins
from .main import main


def open_site():
    origin = next(iter(allowed_origins()))
    parsed = urlparse(origin)
    if parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
        try:
            subprocess.Popen(["xdg-open", origin], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


if __name__ == "__main__":
    threading.Timer(1.5, open_site).start()
    main()
