# Plugin NIIF Multi-Agente — Paquete de Skills

Paquete de 6 skills cargables para AuditBrain que implementan el especialista NIIF como sistema multi-agente.

## Contenido

| Carpeta | Skill | Rol |
|---|---|---|
| `niif-orquestador/` | `niif-orquestador` | Router: identidad compartida + enrutamiento a los 5 agentes |
| `niif-instructor/` | `niif-instructor` | Agente 1 — Formación NIIF (plenas y PYMES) |
| `niif-consultor/` | `niif-consultor` | Agente 2 — Análisis de casos reales |
| `niif-monitor-normativo/` | `niif-monitor-normativo` | Agente 3 — Vigencia y boletines normativos |
| `niif-revisor-rubro/` | `niif-revisor-rubro` | Agente 4 — Revisión técnica por rubro |
| `niif-automatizacion-herramientas/` | `niif-automatizacion-herramientas` | Agente 5 — Construcción de herramientas Python NIIF/PYMES |

## Cómo cargar

Cada carpeta contiene un `SKILL.md` con el formato cargable de AuditBrain (bloque YAML `name` + `description` con disparadores, seguido del cuerpo). Cargar las 6 carpetas en el proyecto de Auditoría Externa / el proyecto NIIF correspondiente.

## Cambios v0.3 (2026-09-25) — papel de trabajo del Command Center

Los agentes conocen el papel de trabajo vigente de las herramientas NIIF del Command Center:
- **Orquestador:** enruta «nueva prueba / procesador / arreglar el papel» a Automatización y «revisa este papel
  de trabajo» al Revisor Técnico.
- **Automatización:** construye pruebas del catálogo como procesadores, siguiendo
  `docs/niif/CONTRATO_PROCESADOR.md` y `docs/niif/ENCARGO_AGENTE_HERRAMIENTA.md`:
  - sin cifras calculadas pegadas;
  - datos del cliente dentro del libro;
  - explicación humana por columna;
  - `PANEL` y `REF_PROBLEMAS`;
  - los mismos gráficos del HTML en todos los formatos;
  - logos en todos los formatos;
  - los verificadores del contrato.
- **Revisor Técnico:** sabe leer el papel. Portada con 5 tarjetas y 4 gráficos; secciones Resultado, Cómo se
  calculó, Datos del cliente y Documentación; Anexo técnico. Cita hoja y celda de cada cifra.

Fuente de las reglas: `CLAUDE.md` › «Papeles de trabajo de las herramientas NIIF».

## Pendientes antes de producción

1. Validar los `name` contra el registro de skills para evitar colisiones.
2. Asignar Skill IDs definitivos del registro maestro v1.8 (el 051 sugerido choca con Ciberseguridad 051–065).
3. Verificar licencias de los 7 repositorios GitHub del Agente 5 antes de integrarlos.
4. Probar el enrutamiento del orquestador con un caso de cada tipo.

---

*AuditBrain · Plugin NIIF Multi-Agente · Borrador técnico · Sujeto a validación humana*
