# Plugin `creacion-herramientas-auditoria-externa` — v1.5.0-draft

Paquete de skills de AuditConsulting para **crear, revisar, transformar, publicar y entregar** herramientas y pruebas de auditoría externa (Command Center / plataforma AUDIT-IA).

## Contenido

| Skill | Rol |
|---|---|
| `metodologia-auditbrain/` | Metodología vinculante — reglas **M01–M31** (incluida la **Puerta de conocimiento M31**), compuertas (Compuerta 0 = Puerta de conocimiento), formato de ficha, pantallas, receta, verificación de Excel e integración con el Command Center. Es el insumo que aplican todas las demás skills y agentes. |
| `crear-herramienta-auditoria/` | Orquestador de punta a punta: encadena los agentes de `references/agentes/` en el orden de la receta, con compuertas y aprobación humana. El **paso 0** es el agente `explorador-conocimiento` (M31), antes de `analista-marco-norma`. |

## Novedades v1.5.0-draft

- **M31 · Puerta de conocimiento.** Antes de diseñar un rubro no cubierto por un dominio confirmado (`metodologia-auditbrain/references/dominios/<rubro>.md`): entrevista al socio + inventario de plugins/skills instalados + búsqueda web como borrador + validación del socio + captura en dominios.
- **M02 ampliada.** El marco puede ser contable (NIIF / NIIF para las PYMES) **o** legal/laboral/tributario (Código del Trabajo, IESS, MDT, LRTI) según el rubro.
- **M20 ajustada.** En Claude Code (sin Microsoft Excel) la paridad Excel ↔ motor se verifica con recálculo LibreOffice (`recalc.py`) + prueba de mutación; el Excel real queda para la validación del socio (M23).
- **Compuerta 0** (Puerta de conocimiento) al inicio de la lista de compuertas.
- **Dominios confirmados** (`metodologia-auditbrain/references/dominios/`): nómina y obligaciones acumuladas de Ecuador (reglas D13, D14, FR, VAC, RL, EX; 11 pruebas con sus códigos RQ).
- Agente nuevo `explorador-conocimiento` y `analista-marco-norma` actualizado (acepta marco laboral/tributario). El resto de agentes pasa a `v1.5.0-draft`.

## Prueba de activación de la M31

Pedir «crea una herramienta de conciliación bancaria». Si el agente arranca con la Puerta de conocimiento —pregunta el objetivo, inventaría los plugins instalados que sirven (p. ej. `finance:reconciliation`) y pide validar antes de construir—, la M31 está activa.
