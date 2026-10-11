# Patrón · Panel HTML de requerimientos y pruebas (cara de la herramienta)

Un único HTML autónomo por módulo es la interfaz del auditor (M24, M32).

## Bloques
1. **Encabezado del encargo**: cliente, RUC, ejercicio, corte, visita, marco y logos (firma, AUDIT-IA, cliente). En el
   prototipo vienen de `let ENC` / `LOGOS` / `FIRMS`; en el Command Center se inyectan desde la ficha del encargo.
2. **Requerimientos** (`RQS`): código, nombre, `hint` (qué entregar), sub-compartimentos (`subs`), `opt` (opcional, no
   bloquea), carga por lotes, multiformato y eliminación individual.
3. **Procesamiento**: «Procesar» habilitado cuando los RQ obligatorios están completos; «Encerar» con doble confirmación.
4. **Pruebas** (`TESTS`): tarjeta por prueba con sus dependencias (`prog`, `prog2`), estado, descarga de la cédula y modal
   con pestañas (`#ovP`, PTABS) para trabajar; nada queda colgando debajo del botón.
5. **Hallazgos** al final.

## Reglas
- La tarjeta se habilita solo cuando sus dependencias tienen resultado.
- Colores del libro y del panel: azul = dato a ingresar, verde = vínculo, naranja = provisional.
- El año auditado se ve en el encabezado y en cada modal.
- En el prototipo los datos del encargo son simulados; nunca se publican datos reales del cliente en una plantilla.
- Tras cada cambio: capturas (Playwright), republicación del panel y bitácora (M36).
