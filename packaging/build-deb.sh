#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"
WHEELS="$ROOT/packaging/wheels"
STAGE="$ROOT/packaging/stage"
OUTPUT="$ROOT/dist"

test -x "$VENV/bin/pip" || { echo "Crea .venv e instala agent/pyproject.toml primero" >&2; exit 1; }
mkdir -p "$WHEELS" "$OUTPUT"
"$VENV/bin/pip" download --dest "$WHEELS" --requirement "$ROOT/agent/requirements.lock"
rm -f "$WHEELS"/xscanner_agent-*.whl
rm -rf "$ROOT/agent/build"
"$VENV/bin/pip" wheel --no-deps --wheel-dir "$WHEELS" "$ROOT/agent"
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/lib/xscanner/wheels" "$STAGE/usr/share/polkit-1/actions" "$STAGE/usr/share/applications" "$STAGE/usr/bin"
cp "$WHEELS"/*.whl "$STAGE/usr/lib/xscanner/wheels/"
install -m 0755 "$ROOT/packaging/privileged.py" "$STAGE/usr/lib/xscanner/privileged.py"
install -m 0644 "$ROOT/packaging/org.xscanner.policy" "$STAGE/usr/share/polkit-1/actions/org.xscanner.policy"
install -m 0644 "$ROOT/packaging/xscanner.desktop" "$STAGE/usr/share/applications/xscanner.desktop"
cat > "$STAGE/DEBIAN/control" <<'EOF'
Package: xscanner-agent
Version: 0.1.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: X-Scanner Project <local@xscanner.invalid>
Depends: python3 (>= 3.12), python3-venv, pkexec, network-manager
Description: Local Linux diagnostics for the X-Scanner static web interface
 A loopback-only service with polkit-gated fixed administrative operations.
EOF
cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
/usr/bin/python3 -m venv /opt/xscanner/venv
/opt/xscanner/venv/bin/pip install --no-index --find-links /usr/lib/xscanner/wheels xscanner-agent==0.1.0
EOF
cat > "$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
  rm -rf /opt/xscanner/venv
fi
EOF
cat > "$STAGE/usr/bin/xscanner-launch" <<'EOF'
#!/bin/sh
exec /opt/xscanner/venv/bin/python -m xscanner.launcher
EOF
cat > "$STAGE/usr/bin/xscanner-cli" <<'EOF'
#!/bin/sh
exec /opt/xscanner/venv/bin/python -m xscanner.cli "$@"
EOF
chmod 0755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/postrm" "$STAGE/usr/bin/xscanner-launch" "$STAGE/usr/bin/xscanner-cli"
dpkg-deb --build --root-owner-group "$STAGE" "$OUTPUT/xscanner-agent_0.1.0_amd64.deb"
rm -rf "$ROOT/agent/build"
