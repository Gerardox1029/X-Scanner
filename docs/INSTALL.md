# Instalación, uso y desinstalación

## Desarrollo local

Requisitos: Python 3.12, Node 22, npm, entorno gráfico Linux, systemd y NetworkManager para la ruta de compatibilidad inicial.

```sh
python3 -m venv .venv
.venv/bin/pip install -e './agent[test]'
cd web && npm ci && npm run dev
```

En otra terminal, desde la raíz del proyecto:

```sh
.venv/bin/xscanner-agent
```

Abre `http://localhost:5173` en Brave. El origen predeterminado del agente es exactamente ese. El código de vinculación se muestra en la terminal del agente; vence a los diez minutos. El servicio aborta si otro programa ocupa el puerto 8765. Si refrescas o cierras la pestaña después de vincular, reinicia el complemento para obtener un código nuevo.

## Paquete Debian y sitio Netlify

```sh
./packaging/build-deb.sh
sudo apt install ./dist/xscanner-agent_0.1.0_amd64.deb
xscanner-cli origin https://TU-SITIO.netlify.app
```

`build-deb.sh` descarga las dependencias Python fijadas en `agent/requirements.lock`, las empaqueta y produce un `.deb` para Python 3.12 en `amd64`. La instalación del `.deb` usa esas ruedas sin acceder a internet. El sitio usa `netlify.toml`, `web/package-lock.json`, `npm ci && npm run build` y publica `web/dist`. Los archivos `_headers` y `_redirects` se copian a `web/dist`, incluso para un despliegue manual. Sustituye `TU-SITIO` por el dominio exacto publicado, sin barra final. Reinicia X-Scanner después de cambiar el origen.

Si publicas manualmente, usa el contenido de `web/dist` o el archivo `dist/xscanner-web-netlify.zip` construido desde esa carpeta. La página debe servirse por HTTPS para solicitar acceso al complemento local.

### Despliegue desde GitHub y dirección del sitio

1. En Netlify, entra a **Add new project → Import an existing project → GitHub** y elige `Gerardox1029/X-Scanner`.
2. El archivo raíz `netlify.toml` fija **Base directory:** `web`, **Build command:** `npm ci && npm run build`, **Publish directory:** `dist` (relativo a `web`). `web/.nvmrc` fija Node 22.23.4. Revisa esos valores antes de publicar.
3. Publica. En la vista del proyecto, usa **Customize** junto a la dirección de vista previa para intentar el nombre `xscanner`. Solo si Netlify lo acepta, el origen será `https://xscanner.netlify.app`. Si el nombre ya pertenece a otro sitio, elige otro y copia la URL real de tu proyecto.
4. En tu Linux, configura ese origen exacto: `xscanner-cli origin https://DIRECCION-REAL.netlify.app`. Reinicia el complemento y abre la URL HTTPS. El enlace no se escribe en el código de React ni en `netlify.toml`; se guarda localmente para la lista de orígenes permitidos.

Inicia **X-Scanner** desde el menú de aplicaciones. La terminal muestra el código temporal y permanece abierta mientras el servicio se use; el lanzador abre el sitio configurado. En Brave, permite el acceso al dispositivo de bucle local cuando se solicite. No desactives las protecciones del navegador. La aplicación distingue servicio apagado, permiso denegado y versión incompatible. El complemento no usa contraseña de administrador para mediciones normales; polkit la solicita por cada operación administrativa predefinida.

Si otro proceso ya usa 8765, X-Scanner se cierra con un mensaje y no se conecta a ese proceso. El complemento no se instala como servicio de sistema ni escucha en la red local.

### Volver a iniciar y obtener otro código

Si la primera instancia sigue abierta, ciérrala con Ctrl-C en su terminal o desde el lanzador. Después ejecuta `xscanner-launch` otra vez. Si aparece “puerto 8765 ocupado”, identifica el proceso con `sudo fuser -v 8765/tcp`; detén únicamente una instancia identificada de X-Scanner y vuelve a lanzarlo. El código anterior es de un solo uso y vence a los diez minutos.

En la web, el resultado aparece primero en modo Cliente. Cambia a “Técnico · JSON” para revisar mediciones completas. Herramientas del técnico incluye Arsenal para scripts personales guardados en `~/.local/share/xscanner/scripts/`.

Arsenal muestra por módulo el código real de diagnósticos y soluciones. Al guardar una edición se crea una versión personal con permisos de usuario. Los diagnósticos y acciones integrados continúan usando el código instalado; para cambiar ese comportamiento en todos los clientes, actualiza el paquete y vuelve a instalarlo.

## Datos y restauración

- Configuración: `${XDG_CONFIG_HOME:-~/.config}/xscanner/settings.json`.
- Historial, reportes, scripts y laboratorios: `${XDG_DATA_HOME:-~/.local/share}/xscanner/`.
- Caché propia: `${XDG_CACHE_HOME:-~/.cache}/xscanner/`.
- Para restaurar todas las pruebas sin navegador: `xscanner-cli restore-labs`.

Desinstala con `sudo apt remove xscanner-agent`. La desinstalación retira el programa y el ejecutor privilegiado, pero conserva el historial, los reportes y la configuración del usuario para que pueda decidir qué borrar. Ejecuta `xscanner-cli restore-labs` antes de desinstalar si hay pruebas activas. Tras desinstalar, puedes eliminar manualmente las tres carpetas XDG de X-Scanner si ya no necesitas sus datos.

## Alcance comprobado

El código y el paquete se construyen en el entorno de desarrollo. La conexión HTTPS real desde un sitio Netlify publicado en Brave, una instalación del `.deb` en otro equipo compatible, los permisos polkit y sensores específicos requieren las comprobaciones de [TESTING.md](TESTING.md) en esos entornos.
