# X-Scanner: plan de desarrollo para Linux y Netlify

## 1. Objetivo y decisiones fijadas

Construir una aplicación funcional con tres módulos —Almacenamiento, Procesos y Redes—, tres problemas recurrentes por módulo, diagnóstico integral y cuatro pruebas controladas. Cada diagnóstico ofrecerá una explicación visual y un botón **“Descargar reporte .txt”**.

La interfaz se publicará como sitio estático en Netlify. Un complemento instalado en la computadora ejecutará los diagnósticos y las reparaciones. Los datos personales y los reportes permanecerán en esa computadora.

- **Entorno inicial comprobado:** Linux Mint 22.3, escritorio GNOME, Brave y Python 3.12.
- **Compatibilidad inicial:** Linux Mint 22.x y Ubuntu 24.04 con escritorio, systemd y NetworkManager. Otras distribuciones mostrarán capacidades disponibles; su compatibilidad requerirá pruebas posteriores.
- **Uso:** cliente y técnico frente a la misma computadora.
- **Modo cliente:** diagnósticos y reparaciones frecuentes seleccionadas y confirmadas por la persona.
- **Modo técnico:** configuración avanzada, edición de scripts y análisis del caso extraño.
- **Autorización:** Linux solicitará la contraseña del administrador para cada operación que requiera privilegios. La página no recibirá ni almacenará esa contraseña.
- **Primera entrega:** código, instalador, documentación y archivos listos para publicar en Netlify. Gmail, MongoDB, Windows y administración remota quedan para versiones posteriores.

## 2. Documentación y organización del trabajo

La primera actividad de implementación será crear estos tres documentos en la raíz. Durante esta fase de planificación quedan especificados; todavía no se crean archivos.

| Documento | Contenido y mantenimiento |
|---|---|
| `plan.md` | Este alcance aprobado, etapas, tareas pendientes, dependencias, criterios de aceptación y evidencias de verificación. Cada tarea tendrá estado y resultado comprobable. |
| `AGENTS.md` | Instrucciones del proyecto y responsabilidades de arquitectura, interfaz, complemento Linux y pruebas. Se usará este nombre en mayúsculas para que Codex reconozca las instrucciones. |
| `memory.md` | Mapa de módulos, decisiones vigentes y sus motivos, comandos de trabajo, limitaciones comprobadas, errores recurrentes y soluciones. Se actualizará tras cambios relevantes, sin guardar contraseñas ni datos del usuario. |

También se incluirá una guía de instalación y uso, documentación del contrato entre interfaz y complemento, procedimientos de pruebas y registro de herramientas, licencias y fuentes.

Las responsabilidades serán:

- **Arquitectura e integración:** mantener el contrato de datos, los límites de permisos y la coherencia entre componentes.
- **Interfaz:** navegación, formularios, resultados, accesibilidad y conexión con el complemento.
- **Complemento Linux:** recopilación de datos, tareas, reparaciones, reportes e instalador.
- **Pruebas:** comprobar permisos, resultados reales, restauración de sabotajes y compatibilidad con Brave.

Estas responsabilidades podrán ejecutarse mediante agentes durante la implementación. Primero se fijarán los contratos compartidos; después podrán avanzar en paralelo la interfaz y el complemento.

## 3. Arquitectura y funcionamiento

### Interfaz y conexión local

- Interfaz en español con **React, TypeScript y Vite**, estilos propios e iconos consistentes. Dependencias fijadas mediante archivo de bloqueo.
- Complemento en **Python con FastAPI, Uvicorn y psutil**; Bash se reservará para operaciones concretas donde aporte claridad.
- Servicio vinculado exclusivamente a `127.0.0.1:8765`. Si el puerto está ocupado por otro programa, mostrará un error y evitará conectarse a él.
- Un lanzador del menú de Linux iniciará el complemento y abrirá la web configurada.
- La vinculación usará un código temporal de un solo uso mostrado por el complemento. La sesión posterior se mantendrá en memoria y terminará al cerrar o reiniciar el complemento.
- La API exigirá autenticación y comprobará el origen permitido. No aceptará comodines para dominios de Netlify ni comandos arbitrarios enviados desde la página.
- La interfaz explicará cómo instalar, iniciar y conectar el complemento, y distinguirá entre servicio detenido, permiso del navegador denegado y versión incompatible.

La primera comprobación de integración será una página HTTPS conectándose al complemento desde Brave. Se manejará el permiso de acceso local que pueda exigir el navegador, sin pedir desactivar sus protecciones. [Referencia de acceso local en Chromium](https://developer.chrome.com/docs/modern-web-guidance/guides/security/local-network-access).

### Permisos, scripts y almacenamiento

- El complemento habitual se ejecutará con el usuario de la sesión.
- Un ejecutor instalado y protegido por el administrador realizará únicamente operaciones privilegiadas predefinidas mediante polkit.
- Cada reparación mostrará objetivos, cambios previstos, consecuencias y posibilidad de recuperación antes de ejecutarse.
- Se volverán a comprobar archivos y procesos antes de actuar: un diagnóstico antiguo no autoriza a modificar un objetivo que cambió.
- El modo técnico tendrá contraseña propia configurada localmente y vencimiento tras 15 minutos de inactividad. Protege el acceso desde la aplicación; el administrador de Linux conserva el control del equipo.
- El editor permitirá configurar parámetros y crear versiones de scripts de usuario. Los scripts personalizados se ejecutarán con los permisos del usuario, con límite de tiempo y registro de salida.
- Las operaciones administrativas incorporadas no podrán convertirse en scripts arbitrarios mediante el editor.
- Configuración, historial y cachés usarán las ubicaciones XDG del usuario. El instalador colocará el código administrativo en ubicaciones protegidas.

### Contrato entre componentes y reportes

La API local tendrá versión `/api/v1` y operaciones para vincularse, consultar capacidades, iniciar diagnósticos, consultar o cancelar tareas, preparar reparaciones, ejecutarlas, descargar reportes y gestionar pruebas y scripts.

Cada tarea devolverá un identificador, estado, progreso y resultado. Los resultados contendrán módulo, problema, mediciones con unidades, hallazgos, evidencia, limitaciones y acciones disponibles. Se conservará una especificación OpenAPI y tipos equivalentes para la interfaz.

Cada reporte TXT será UTF-8 e incluirá:

- Fecha, zona horaria, equipo y versiones.
- Alcance y parámetros del diagnóstico.
- Mediciones, hallazgos y explicación.
- Rutas o procesos relevantes.
- Elementos no examinados y motivos.
- Recomendaciones y, cuando corresponda, resultado antes/después de una reparación.

Los diagnósticos cancelados o incompletos también podrán descargarse, claramente identificados. No se prometerá una duración fija.

## 4. Experiencia y funciones de la primera versión

Inicio mostrará tres tarjetas principales y una tarjeta grande **FULL SCAN**, con el texto: “Algo anda mal, pero no sé por dónde comenzar”. La navegación incluirá Inicio, los tres módulos, Pruebas, Historial y Herramientas del técnico.

El aspecto tomará de la referencia el fondo oscuro y los acentos cian y verde, con textos legibles, diseño adaptable y estados que no dependan únicamente del color.

Cada problema seguirá el flujo: **seleccionar → configurar opcionalmente → diagnosticar → entender resultados → descargar reporte → revisar acción → ejecutar → comprobar resultado**.

| Módulo y afirmación | Diagnóstico | Solución o respuesta prevista |
|---|---|---|
| **Almacenamiento: “Me estoy quedando sin espacio”** | Capacidad e inodos por volumen, carpetas grandes, papelera, cachés y archivos voluminosos. Búsqueda de duplicados opcional mediante tamaño, hash y comparación, evitando contar enlaces al mismo archivo como copias independientes. | Selección de archivos para papelera y limpieza de cachés reconocidas. Vaciado de papelera separado y explícito. Medición del espacio efectivamente recuperado. |
| **Almacenamiento: “No encuentro una foto o video”** | Nombre, formatos, tamaño y fechas aproximadas; metadatos cuando existan. | Galería paginada, miniaturas, ruta, descarga y gestión confirmada del archivo. |
| **Almacenamiento: “No encuentro un archivo”** | Nombre parcial, tipo, tamaño, fechas y carpetas. | Lista ordenable con ruta y descarga. Búsqueda opcional dentro de documentos de texto, con límites de tamaño. |
| **Procesos: “Mi computadora está lenta”** | Muestreo de CPU por núcleo y proceso, memoria disponible, intercambio y actividad de disco durante diez segundos. | Seleccionar aplicaciones del usuario para cerrarlas y volver a medir. Explicar causas que no admitan corrección automática. |
| **Procesos: “Una aplicación se quedó congelada”** | Procesos asociados, consumo y estado. La aplicación no declarará un bloqueo basándose solo en consumo elevado. | Cierre solicitado por la persona; señal de terminación normal y cierre forzado como segunda acción explícita. |
| **Procesos: “El equipo se calienta o hace mucho ruido”** | Sensores disponibles y carga sostenida. Indicar ausencia de sensores o umbrales del fabricante. | Cerrar una aplicación identificada y repetir medición; recomendaciones de revisión física cuando corresponda. |
| **Redes: “No tengo conexión”** | Interfaz, dirección IP, ruta, puerta de enlace, DNS y acceso exterior. | Reconectar el perfil activo de NetworkManager con confirmación; instrucciones específicas cuando falle otra parte de la conexión. |
| **Redes: “Internet está lento”** | Tráfico de interfaz, latencia, pérdida y medición opcional de diez segundos por aplicación usando NetHogs, con autorización administrativa. | Mostrar hasta cinco consumidores identificados y permitir cerrar aplicaciones seleccionadas del usuario. |
| **Redes: “Una página no abre”** | Comprobación de URL HTTP/HTTPS, DNS, conexión y respuesta. | Recomendación según la causa; reinicio de un servicio local gestionado por X-Scanner cuando ese sea el origen del fallo. |

La medición de NetHogs distinguirá tráfico atribuido y tráfico desconocido. Un origen desconocido no aparecerá como malicioso ni tendrá un botón para finalizar un proceso que no se pudo identificar. [Documentación de NetHogs](https://github.com/raboof/nethogs).

Reglas adicionales:

- Escanear todos los sistemas de archivos locales montados, evitando duplicar montajes y excluyendo sistemas virtuales como `/proc`, `/sys` y `/dev`. Discos de red se incorporarán mediante selección explícita.
- Informar rutas inaccesibles; ofrecer un análisis administrativo adicional para metadatos del sistema. Las previsualizaciones y descargas respetarán los permisos de lectura del usuario.
- Todos los filtros de búsqueda serán opcionales. Elegir agosto de 2025 permitirá ampliar a julio–septiembre y mostrará el intervalo usado.
- Distinguir fecha de modificación, creación disponible y fecha de captura. No deducir fechas a partir del número de inodo.
- No clasificar una carpeta como basura únicamente por contener el nombre de una aplicación desinstalada. Mostrar candidatos y evidencia; excluir partidas y documentos de limpiezas automáticas.
- Explicar que mover archivos a la papelera del mismo disco no libera espacio hasta vaciarla.
- Full Scan ejecutará los tres diagnósticos generales; las búsquedas de archivos y las acciones que necesiten parámetros se ofrecerán después. No reparará automáticamente.
- Proteger los procesos del sistema, la sesión, Brave y el propio complemento frente a cierres desde las acciones frecuentes.

## 5. Pruebas, entrega y criterios de aceptación

Las tres pruebas recurrentes tendrán diagnóstico, solución existente y medición antes/después:

| Prueba | Alteración real y acotada | Solución del proyecto |
|---|---|---|
| **Almacenamiento** | Crear 128 MiB de archivos identificados en un directorio de laboratorio, previa comprobación del espacio disponible. | El diagnóstico los encuentra y la limpieza de datos de prueba los elimina; se verifica el espacio recuperado. |
| **Procesos** | Iniciar un proceso de prueba que ocupe un núcleo, con memoria limitada y duración máxima de 90 segundos. | El diagnóstico lo identifica y la acción habitual de finalizar proceso reduce la carga. |
| **Redes** | Detener el servidor HTTP de prueba de X-Scanner en un puerto local, provocando que su página deje de responder. | El diagnóstico identifica el servicio local detenido y la acción de reinicio restaura el acceso. |

La prueba de redes se etiquetará como fallo de un servicio local; no se presentará como simulación de lentitud del proveedor de internet.

El **caso extraño** mantendrá abierto un archivo de prueba de 32 MiB después de eliminar su nombre. El diagnóstico contrastará ocupación y archivos visibles, identificará el proceso que conserva el archivo y generará evidencia para el técnico. No ofrecerá reparación automática; finalizará por temporizador o restauración manual del laboratorio.

Todas las pruebas usarán recursos propios, permitirán detenerse y tendrán limpieza independiente del navegador.

La implementación avanzará en este orden:

1. Crear documentación y contratos; comprobar conexión HTTPS de Netlify con el complemento en Brave y autorización mediante Linux.
2. Completar Almacenamiento, reportes y la primera prueba de extremo a extremo.
3. Completar Procesos, Redes y sus pruebas.
4. Añadir Full Scan, historial, modo técnico, editor y caso extraño.
5. Empaquetar, verificar en otro Linux y preparar la publicación.

Se entregarán un instalador `.deb`, código fuente, guía de instalación/desinstalación y un sitio estático listo para Netlify. La configuración usará `npm run build`, publicará la carpeta compilada y contemplará navegación de la aplicación y cabeceras de seguridad. [Configuración de Netlify](https://docs.netlify.com/build/configure-builds/file-based-configuration/).

La versión se considerará terminada cuando:

- Los nueve recorridos funcionen con datos reales o indiquen una limitación concreta.
- Cada diagnóstico y Full Scan permitan descargar un TXT coherente con la pantalla.
- Las tres pruebas recurrentes se detecten y resuelvan usando acciones del proyecto.
- El caso extraño produzca evidencia y permita restaurar el laboratorio.
- Cancelar una autorización no cambie el sistema.
- Se rechacen peticiones sin sesión, desde orígenes ajenos y dirigidas a ejecutar comandos arbitrarios.
- Se comprueben nombres de archivo especiales, permisos denegados, cambios de objetivos durante un diagnóstico y procesos ya finalizados.
- La web publicada se conecte al complemento desde Brave sin desactivar protecciones.
- La instalación y una prueba funcional se reproduzcan en una segunda instalación compatible de Linux.
- La documentación distinga los resultados medidos de las capacidades todavía no verificadas.
