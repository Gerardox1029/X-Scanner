# Contrato local `/api/v1`

Versión 1 del contrato para `http://127.0.0.1:8765`. La especificación generada por FastAPI se conserva en `openapi.json`. Todos los cuerpos y respuestas JSON usan UTF-8. El servidor acepta solo el `Origin` exacto configurado y todos los endpoints salvo `health` y `pair` exigen `Authorization: Bearer <token>`. El token y el código de vinculación viven solo en la memoria del proceso. El código expira a los 10 minutos y se usa una sola vez.

| Método | Ruta | Uso |
|---|---|---|
| GET | `/health` | Identidad y versión; sin datos del equipo. |
| POST | `/pair` | `{"code":"123456"}`; devuelve token de sesión. |
| GET | `/capabilities` | Distribución, escritorio, ejecutor y diagnósticos disponibles. |
| POST | `/tasks` | `{"kind":"storage-space","params":{}}`; inicia tarea. |
| GET | `/tasks`, `/tasks/{id}` | Historial y estado/resultado de una tarea. |
| POST | `/tasks/{id}/cancel` | Solicita cancelación. |
| GET | `/tasks/{id}/report` | Descarga TXT UTF-8, incluso si terminó cancelada o incompleta. |
| GET | `/tasks/{id}/file?path=...` | Descarga un archivo legible incluido en los resultados de esa tarea. |
| GET | `/tasks/{id}/thumbnail?path=...` | Vista previa JPEG acotada de una foto incluida en esa tarea. |
| POST | `/actions/prepare` | `task_id`, `kind`, `target` opcional; devuelve cambio, consecuencias y token efímero. |
| POST | `/actions/execute` | `token` de preparación; valida el objetivo otra vez y registra resultado. |
| GET | `/labs` | Estado de recursos de prueba. |
| POST | `/labs/{kind}/start`, `/labs/{kind}/restore` | Crea o restaura recursos propios de almacenamiento, procesos, redes o caso extraño. |
| GET/POST | `/technician/...` | Configuración/desbloqueo y scripts de usuario, tras contraseña técnica. |

`kind` de diagnóstico: `storage-space`, `storage-photo`, `storage-file`, `process-slow`, `process-frozen`, `process-heat`, `network-offline`, `network-slow`, `network-page`, `full-scan`, `strange-case`.

El modo Cliente es una transformación visual del mismo resultado JSON; el modo Técnico muestra las estructuras completas. Los scripts personales se consultan con `GET /technician/scripts/{name}` y se clasifican como `usuario`; los diagnósticos integrados no se pueden editar desde la API.

Las tareas tienen `id`, `kind`, `params`, `status` (`queued`, `running`, `complete`, `cancelled`, `failed`), `progress`, `created`, `finished`, `result` y `error`. Un resultado contiene `summary`, `measurements`, `findings`, `evidence`, `limitations`, `recommendations`, `actions` y, después de una acción, `actions_taken`. Las mediciones incluyen unidades en sus nombres (`_bytes`, `_seconds`, `_celsius`, etc.).

Las acciones incorporadas son `trash-file`, `empty-trash`, `clear-cache`, `terminate-process`, `force-process`, `reconnect-network` y `restart-lab-server`. Ningún endpoint acepta texto de comando, argumentos de shell o una ruta para el ejecutor administrativo. Los scripts técnicos se guardan como versiones y se ejecutan con el usuario de la sesión, con límites de CPU, memoria y tiempo.

Los parámetros opcionales de búsqueda son `root`, `name`, `extension`, `min_bytes`, `max_bytes`, `month` (`AAAA-MM`), `expand_month` y `content` (solo documentos de texto pequeños). `network-page` recibe `url`; `network-slow` puede recibir `per_process: true`; `storage-space` puede recibir `duplicates: true`.

Ejemplo de estado:

```json
{
  "id": "uuid",
  "kind": "network-page",
  "params": {"url": "http://127.0.0.1:8766/"},
  "status": "complete",
  "progress": 100,
  "result": {
    "summary": "No se abrió la página",
    "measurements": [], "findings": [], "evidence": [],
    "limitations": [], "recommendations": [],
    "actions": [{"kind": "restart-lab-server", "description": "Restaurar servidor HTTP de prueba"}]
  },
  "error": null
}
```

Los reportes incluyen fecha, zona horaria, equipo, versiones, alcance, parámetros, mediciones, hallazgos, evidencia, limitaciones, recomendaciones y reparaciones registradas. La aplicación conserva hasta 100 tareas recientes en el historial local. `/openapi.json` está disponible en el proceso para inspección; el archivo de este directorio fija la versión entregada.
