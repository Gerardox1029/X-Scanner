#!/usr/bin/python3
"""Root-owned, polkit-gated operations. No browser-provided command or argument is used."""
import os
import re
import subprocess
import sys


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit(2)
    operation = sys.argv[1]
    if operation == "reconnect-active":
        active = subprocess.run(["/usr/bin/nmcli", "-t", "-f", "UUID,DEVICE", "connection", "show", "--active"],
                                capture_output=True, text=True, timeout=10, check=True)
        uuids = []
        for line in active.stdout.splitlines():
            uuid, _, device = line.partition(":")
            if device and device != "lo" and re.fullmatch(r"[0-9a-fA-F-]{36}", uuid):
                uuids.append(uuid)
        if not uuids:
            print("No hay perfil activo de NetworkManager", file=sys.stderr)
            raise SystemExit(1)
        result = subprocess.run(["/usr/bin/nmcli", "connection", "up", "uuid", uuids[0]],
                                capture_output=True, text=True, timeout=30, check=False)
        print(result.stdout[-500:])
        print(result.stderr[-500:], file=sys.stderr)
        raise SystemExit(result.returncode)
    if operation == "nethogs-10s":
        binary = "/usr/sbin/nethogs"
        if not os.path.isfile(binary):
            print("NetHogs no está instalado", file=sys.stderr)
            raise SystemExit(1)
        try:
            result = subprocess.run([binary, "-t", "-d", "1", "-c", "10"],
                                    capture_output=True, text=True, timeout=18, check=False)
        except subprocess.TimeoutExpired:
            print("NetHogs superó el límite de tiempo", file=sys.stderr)
            raise SystemExit(1)
        print(result.stdout[-100_000:])
        print(result.stderr[-500:], file=sys.stderr)
        raise SystemExit(result.returncode)
    print("Operación no permitida", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
