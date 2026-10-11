# Creación de herramientas de auditoría externa

Plugin de Cowork de **AuditConsulting Auditores Cía. Ltda.** para crear, revisar y publicar herramientas y pruebas de
auditoría externa (NIIF y legales/laborales) del Command Center de **AUDIT-IA**, con la Memoria Metodológica AuditBrain
**v1.5.0 (M01–M38)**.

## Novedades v1.5.0

- **M31 · Puerta de conocimiento** y nuevo agente `explorador-conocimiento` (paso 0 de toda herramienta nueva).
- **M32–M38**, destiladas del módulo «Pasivos Acumulados y Gastos de Nómina»: pruebas nacidas de requerimientos y
  vivas en el panel, mayores conciliados antes de usarse, un generador por cédula sin cifras del cliente, valores de
  control y privacidad, rastro de cada cambio, normativa verificada en la fuente, inspección del repositorio antes de
  integrar.
- **Dominio de nómina confirmado** (REGLAS v1.4, FLUJOS v1.22 y catálogo de cédulas), anonimizado.
- **Patrones reutilizables**: mayores RQ-004, muestreo de atributos, calculadora de liquidación hipotética, panel de
  requerimientos y pruebas, paquete de entrega al Command Center.

## Componentes

**Skills**
- `metodologia-auditbrain` — reglas vinculantes M01–M38, compuertas, verificación de cumplimiento, requisitos del
  entregable y límites de honestidad. Referencias: receta, formato de ficha, verificación del Excel, pantallas (M24),
  revisar y reconstruir, entrega al Command Center, reglas M32–M38, dominios confirmados y patrones.
- `crear-herramienta-auditoria` — encadena los agentes en el orden de la receta, con las aprobaciones del socio.

**Agentes (un procedimiento cada uno)**

| Agente | Procedimiento |
|---|---|
| `explorador-conocimiento` | Puerta de conocimiento: dominio confirmado, plugins instalados, borrador web y validación del socio (M31) |
| `analista-marco-norma` | Marco, modelo del rubro y lectura de la norma oficial, NIA y tributario |
| `disenador-ficha` | Versión más simple que cumple y ficha A–E con ejemplo numérico |
| `arquitecto-calculo` | Declarativo, procesador (M18) o artefacto HTML con motor propio (M38); cédulas con fórmulas y entrega a Claude Code |
| `verificador-excel` | Paridad Excel ↔ motor en Excel real y prueba de mutación (M20) |
| `revisor-pantallas` | Pantallas contra el diseño estándar (M24) |
| `auditor-cumplimiento` | Tabla M01–M38 con evidencia y puerta de calidad |
| `preparador-publicacion` | Papel de muestra, validación del socio y paso al catálogo (M23) |
| `revisor-excel-existente` | Revisar o reconstruir un Excel o HTML ya armado |

## Uso

- «Crea una herramienta de pérdidas esperadas para cuentas por cobrar» → `crear-herramienta-auditoria`.
- «Revisa este Excel de inventarios» → `revisor-excel-existente`.
- «Verifica las fórmulas de este papel» → `verificador-excel`.
- «¿Cumple la metodología?» → `auditor-cumplimiento`.

## Relación con otras skills

- Reemplaza a la skill suelta `auditbrain-metodologia` (v1.3.2): al instalar este plugin, desactivar aquella para que no
  compitan.
- Usa, si está instalada, `niif-revisor-rubro` para la capa normativa por rubro.

## Fuentes

Casos de origen: VNR (NIC 2), CXC-PI-01 pérdidas incurridas (Secc. 11 PYMES), CXC-PCE-01 pérdida crediticia esperada
simplificada (NIIF 9), en el repositorio `auditbrain-python-runner` (`docs/niif/fichas/`,
`backend/app/aud/niif/procesadores/`, `scripts/verificar_formulas_*.py`).
