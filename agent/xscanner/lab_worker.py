import os
import signal
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"X-Scanner: servidor de prueba activo\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    kind = sys.argv[1]
    if kind == "network":
        HTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
    elif kind == "process":
        end = time.monotonic() + 90
        while time.monotonic() < end:
            for _ in range(1_000_000):
                pass
            time.sleep(0.01)
    elif kind == "strange":
        root = Path(sys.argv[2])
        path = root / "archivo-abierto-eliminado.bin"
        with path.open("wb+") as file:
            file.write(b"X" * (32 * 1024 * 1024))
            file.flush()
            os.unlink(path)
            time.sleep(90)


if __name__ == "__main__":
    main()
