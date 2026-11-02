# X-Scanner project memory

## Map

- `web/`: React + TypeScript + Vite browser interface.
- `agent/xscanner/`: loopback FastAPI service; diagnostics, labs, reports and technician tools.
- `packaging/`: Debian installer, launcher and fixed privileged helper.
- `netlify.toml`: static build, navigation and browser security headers.
- `docs/API.md`: HTTP contract. `docs/INSTALL.md`: setup and removal.

## Decisions

- The local service is bound to `127.0.0.1:8765`; pair codes and bearer sessions live only in process memory.
- Only exact configured web origins pass CORS and Origin checks. No Netlify wildcard.
- Browser requests name predefined operations and typed parameters, never a shell command.
- XDG paths hold local settings, history and reports; no personal data is sent to the hosting site.
- Photo capture dates use EXIF or ffprobe when available; Pillow generates bounded thumbnails. NetHogs attribution is optional and requires polkit.
- The first delivery is source, `.deb` build process and Netlify-ready static files. Publication and a second-machine compatibility test require those environments.
- La vista de resultados tiene Cliente por defecto y Técnico JSON; las alertas de laboratorio usan únicamente evidencia medida.
- La exploración de archivos usa HOME y carpetas XDG visibles del usuario; no presenta `/sys` o `/dev` como carpetas personales.
- Arsenal permite editar solo scripts personales; los diagnósticos y acciones privilegiadas integrados permanecen fijos.

## Commands

See `docs/INSTALL.md` for development, builds, installation and removal. Key checks: `.venv/bin/pytest -q agent/tests`, `cd web && npm run build`, `./packaging/build-deb.sh`, `xscanner-cli restore-labs` after installation. Update this document when a command or decision changes.
