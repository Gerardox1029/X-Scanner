# Procedimiento de verificación

## Comprobaciones automáticas

```sh
.venv/bin/pytest -q agent/tests
cd web && npm ci && npm run build
cd .. && ./packaging/build-deb.sh
dpkg-deb --contents dist/xscanner-agent_0.1.0_amd64.deb
```

Las pruebas cubren origen y sesión, código de un solo uso, comando desconocido, búsqueda con caracteres especiales, EXIF y miniatura autorizada, reporte, rechazo de archivo cambiado y proceso protegido, y creación/limpieza exacta del laboratorio de 128 MiB. También verifican la restauración del servidor local, el caso extraño y el proceso de carga con cierre confirmado.

## Prueba manual de extremo a extremo

1. Publica `web/dist` en un sitio HTTPS de Netlify y configura su origen exacto con `xscanner-cli origin`.
2. En Brave sobre Linux Mint 22.x o Ubuntu 24.04, abre el sitio, pulsa **Comprobar servicio local**, acepta el permiso de bucle local y vincula el código. Verifica también bloqueo del permiso y servicio apagado.
3. Ejecuta los nueve recorridos con datos reales. Confirma mediciones y limitaciones; descarga el TXT de cada uno y compáralo con la pantalla.
4. Ejecuta Full Scan. Comprueba que cubre tres diagnósticos generales y no cambia nada.
5. Crea cada alteración de laboratorio: 128 MiB, proceso de un núcleo y servidor HTTP detenido. Diagnostica, aplica la solución indicada, mide antes/después y restaura. Ejecuta `xscanner-cli restore-labs` con el navegador cerrado.
6. Crea el caso extraño, diagnostica el descriptor de archivo eliminado y restaura por temporizador y por CLI. No debe ofrecer cierre automático.
7. Cancela una autorización polkit y comprueba que el estado del sistema no cambia. Prueba origen no permitido y sesión inválida con el complemento activo.
8. Repite instalación y un recorrido funcional en una segunda instalación compatible. Registra distribución, versión de Brave y resultado.

No atribuyas un fallo externo de internet a la prueba de servidor local. El tráfico desconocido de NetHogs se informa por separado y nunca se etiqueta como malicioso. Los procesos protegidos deben quedar fuera del cierre frecuente. Registra cualquier ruta inaccesible y cada capacidad no disponible.

## Evidencia pendiente de entorno externo

En este repositorio no hay URL Netlify publicada ni segunda instalación de Linux. Hasta completar los pasos 1, 2 y 8, esos criterios de aceptación no están verificados.
