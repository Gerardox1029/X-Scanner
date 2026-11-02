# Estilos de la interfaz X-Scanner

## Sistema visual

- Fondo principal: `#07121D`; paneles: `#0C1F2C` y `#102E34`.
- Texto principal: `#EAF4F6`; texto secundario: `#88A7B1`.
- Acento: cian/verde `#5BE7B5`; bordes: `#28414B`.
- Advertencia: fondo `#4C3A18`, borde `#D9AA42`, texto `#FFE8AA`.
- Éxito: verde `#2DA36F`; error: rojo oscuro con texto claro.

## Tipografía y componentes

La interfaz usa Space Grotesk para títulos y DM Sans para textos, con fallback Arial. La jerarquía combina títulos grandes, etiquetas pequeñas en mayúsculas y párrafos breves. Los componentes principales son barra lateral, tarjetas de módulo, panel de diagnóstico, barras `<progress>`, alertas, botones con estados y diálogos de confirmación.

## Estados y accesibilidad

Cada estado se comunica con texto e icono además de color: servicio desconectado, diagnóstico en curso, problema encontrado, acción en progreso, éxito y error. Los botones tienen foco visible, los formularios usan etiquetas y los resultados técnicos conservan JSON legible. La presentación replica este contraste y funciona sin conexión con teclado: `←`, `→`, `Home`, `End` y `Espacio`.
