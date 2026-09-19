# Presupuestos IA · sección Automatizaciones — Diseño

Fecha: 2026-09-16 · Rama: `feat/automatizaciones-presupuestos`

## 1. Objetivo
Llevar la herramienta de **Elaboración Inteligente de Presupuestos** (prototipada en
Lovable, repo `jcalupinia/smart-budget-builder`) al portal AUDIT-IA como herramienta
**nativa**, siguiendo el patrón de ICT 2025: mismo backend FastAPI, misma base
PostgreSQL de Render, mismo login, mismos entitlements. **Sin Supabase.**

Fuente de verdad funcional: *Documento Maestro de Elaboración Inteligente de
Presupuestos Empresariales con IA v1.1* y el plan maestro aprobado (M01–M20, 10
decisiones del cliente: participación 15 %, IR 25 % configurable, umbral de
supuestos críticos 5 %, marketing dentro de OPEX, etc.).

## 2. Decisiones de arquitectura
| Tema | Decisión |
|---|---|
| Sección | Nueva categoría del catálogo `AUTOMATIZACIONES` ("Automatizaciones"). Primera herramienta: `PRESUPUESTOS_IA`. |
| Registro | `ToolConfig(code="PRESUPUESTOS_IA", category="AUTOMATIZACIONES", slots={}, processor=None)` — flujo propio como ICT. |
| Backend | Paquete `backend/app/presupuestos/` (models, schemas, service, router, catalogo_sectorial). Router `/api/v1/client/presupuestos/*`. |
| Frontend cliente | Ruta dedicada `/tools/PRESUPUESTOS_IA` en `frontend-client` con `PortalShell activeCategory="AUTOMATIZACIONES"`. |
| Command Center | El módulo `AUT · Automation Core` pasa a llamarse **`AUT · Automatizaciones`** y muestra el acceso a Presupuestos IA (abre el portal cliente; los operadores entran con su mismo usuario, como en ICT). |
| Acceso | `require_client_with_device` + entitlement `PRESUPUESTOS_IA` (rol client). Operadores (admin/user) hacen bypass, como en el resto del portal. |
| Tenencia | **Empresa = cliente del portal** (`clients.id`). Un usuario client solo ve empresas de su `client_id`; los operadores ven todas. |
| Roles internos (F1) | Simplificados: cualquier cuenta client del mismo cliente edita su presupuesto; operadores editan todo. Roles por departamento (responsable, revisor, gerencia) quedan para una fase posterior. |
| Seguridad | Reglas en el backend (no en la base): toda consulta filtra por tenencia; identificadores y `client_id` inmutables; **sin borrado físico** (columna `activo`); auditoría de cambios. |
| Motor de cálculo | Se reutiliza `src/lib/motor/index.ts` (TypeScript puro, 6 pruebas verificadas a mano) en `frontend-client` (F2). |
| Archivos (F3) | Mismo almacenamiento en disco persistente de Render que usa ICT. |
| IA (F4) | Servidor IA local de la firma vía LiteLLM (proveedor `local` ya existente en el portal). Sin proveedores externos para datos de clientes. |
| Tablas | Prefijo `pres_`, creadas con `Base.metadata.create_all` como el resto del portal. |

## 3. Fases
- **F1 · Base (este PR):** categoría + registro, modelos, diagnóstico (crear empresa → departamentos + matriz del sector + período + versión v1 + escenario Base, todo atómico), estructura (departamentos, centros de costo, unidades), matriz de requerimientos (ficha estándar, estados con nota obligatoria, avance), historial, catálogo sectorial (5 sectores), Command Center renombrado.
- **F2 · Cálculo:** supuestos (M07), líneas de presupuesto y parámetros, motor, Estado de resultados, flujo de caja, alertas, supuestos críticos, trazabilidad.
- **F3 · Evidencias:** carga, validación con segregación (quien sube no valida), duplicados por hash.
- **F4 · IA local:** análisis de evidencias con propuesta de suficiencia confirmada por una persona.
- **F5 · Cierre MVP:** escenarios, consolidación, revisión/aprobación, exportación XLSX/PDF.

## 4. Modelo de datos F1
- `pres_empresas`: id, client_id (FK clients, nullable solo para empresas de prueba de operadores), nombre, identificacion, pais (def. Ecuador), moneda (def. USD), tamano, sector_clave, actividad, modelo_negocio, activo, creado_por, created_at, updated_at.
- `pres_periodos`: id, empresa_id, nombre, anio, fecha_inicio, fecha_fin, frecuencia, estado.
- `pres_versiones`: id, empresa_id, periodo_id, numero, nombre, estado (borrador/en_revision/aprobada/cerrada/reabierta), creado_por, created_at. Único (periodo_id, numero).
- `pres_escenarios`: id, empresa_id, version_id, nombre, es_base, activo. Base creado por el sistema.
- `pres_unidades`, `pres_departamentos` (responsable_nombre/email, aporte, activo, orden), `pres_centros_costo`.
- `pres_requerimientos`: ficha estándar (nombre, que_es, para_que_sirve, datos_minimos JSON, periodicidad, formato_admitido, driver, presupuesto_afectado, responsable, prioridad, fecha_objetivo, periodo_id), estado (7 estados), suficiencia (4), accion_siguiente, notas, origen (catalogo/manual), activo.
- `pres_eventos`: id, empresa_id, entidad, entidad_id, tipo, estado_anterior, estado_nuevo, nota, usuario_id, usuario_email, version_id, origen, created_at. Solo inserción desde el servicio.
- Catálogo sectorial en código (`catalogo_sectorial.py`), extraído del catálogo validado en Lovable (5 sectores × 11 departamentos × 11 requerimientos).

## 5. Reglas de negocio F1 (probadas con pytest)
1. Crear empresa es atómico: empresa + período + v1 borrador + escenario Base + 11 departamentos + 11 requerimientos; si algo falla, nada queda.
2. Aislamiento: un client de otro cliente recibe 404 en cualquier recurso ajeno; sin entitlement → 403.
3. Cambiar estado de un requerimiento exige nota; queda evento con usuario, fecha, versión y origen.
4. No existe DELETE: desactivar exige nota y queda evento.
5. `client_id`, `empresa_id`, ids e información de creación no se pueden cambiar por la API.
6. Registrar una ruta de captura (subir/conversar/reporte) no cambia estado ni avance.
7. Avance excluye departamentos inactivos y requerimientos desactivados.

## 6. Verificación antes de entregar
- `pytest` de los archivos nuevos + suite de entitlements existente en verde.
- `vitest` del frontend-client en verde y `vite build` sin errores.
- Prueba E2E local (backend SQLite + Vite) con una cuenta client con y sin entitlement y un operador: crear empresa, ver matriz, cambiar estado con nota, verificar aislamiento.

## 7. Fuera de alcance de F1
Supuestos, cálculo, evidencias, IA, escenarios adicionales, aprobaciones, exportación, roles internos por departamento.
