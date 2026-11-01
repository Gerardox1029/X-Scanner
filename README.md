# X-Scanner

Aplicación de diagnóstico local para Linux Mint 22.x y Ubuntu 24.04 con escritorio, systemd y NetworkManager. La interfaz estática se publica en Netlify; el complemento Python ejecuta las mediciones en `127.0.0.1:8765` y conserva reportes e historial en el equipo.

## Comenzar

1. Construye el sitio: `cd web && npm ci && npm run build`.
2. Para desarrollo local: crea `.venv`, instala `agent/` y ejecuta `xscanner-agent` (comandos completos en [docs/INSTALL.md](docs/INSTALL.md)).
3. Para una instalación compatible: genera `dist/xscanner-agent_0.1.0_amd64.deb` con `./packaging/build-deb.sh`, publica `dist/xscanner-web-netlify.zip`, instala el `.deb` y configura el origen HTTPS exacto de Netlify.
4. Abre X-Scanner desde el menú, permite el acceso a red local si Brave lo solicita y vincula con el código temporal mostrado por el complemento.

La página no recibe la contraseña de Linux. Los archivos personales, resultados y reportes permanecen en las ubicaciones XDG del usuario.

La especificación y el estado de verificación están en [PLAN.md](PLAN.md) y [plan.md](plan.md). Contrato: [docs/API.md](docs/API.md). Pruebas: [docs/TESTING.md](docs/TESTING.md).

Para publicar desde GitHub en Netlify y configurar la URL real del sitio en el complemento, sigue la sección **Despliegue desde GitHub y dirección del sitio** de [docs/INSTALL.md](docs/INSTALL.md).
