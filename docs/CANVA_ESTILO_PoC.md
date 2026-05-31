# Estilo de referencia para presentaciones Canva (PoC aprobado)

Referencia extraída del PoC `AuditBrain_Reporte_Canva_POC.pptx` (generado con
Canva vía MCP). Es la estética aprobada para los decks ejecutivos que produce el
botón **🎨 Presentación** del módulo TAX › Análisis.

## Identidad visual
- **Tipografía:** DM Sans (regular, bold, italic).
- **Tema:** oscuro, premium y minimalista; texto claro (blancos/grises
  `#FFFFFF`, `#DDDDDD`, `#CCCCCC`) sobre fondos oscuros.
- **Acentos de marca:** Gold `#C7A83C` sobre Deep Blue `#071B2F` / Navy `#0A2342`.
- **Composición:** mucho espacio en blanco, jerarquía visual clara, KPIs con
  números grandes y legibles, look de agencia.

## Estructura del PoC (referencia narrativa)
1. Portada — título, empresa, contacto.
2. Resumen Ejecutivo — opinión/mensaje clave en pocas líneas.
3. (Sección visual / divisoria).
4. KPIs — tarjetas con número grande + etiqueta (ej. "USD 12.5M · INGRESOS").
5. Recomendaciones y Plan.
6. Conclusiones y próximos pasos.

## Cómo se aplica en la herramienta
El endpoint `POST /api/v1/tax/planificacion-utilidades/presentacion` usa este
estilo por defecto (parámetro `style`) y, si se indica, un **Brand Kit ID** de
Canva para consistencia total de marca. El contenido (KPIs, diagnósticos, matriz
de los 4 escenarios, modelación, plan de acción) lo arma el frontend en vivo.

> Nota: el PoC se exportó en A4 vertical (formato reporte). El deck ejecutivo de
> la herramienta usa `design_type=presentation` (apaisado) manteniendo esta
> misma estética.
