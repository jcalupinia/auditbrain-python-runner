# AuditSmart Costo Global 2026 — Plan de implementación (PR #389)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar en el Portal de Clientes ocho bloques integrados de costeo industrial y conciliación contable, escalable, multiempresa, sin interrumpir ICT.

**Architecture:** Frontend React/Vite existente → rutas autenticadas FastAPI → servicio de ingestión asíncrona y persistencia por organización/cliente/proyecto → motor Python determinístico → artefactos auditables. Command Center solo recibe adaptación posterior. No se procesan archivos masivos mediante `await f.read()` del router genérico.

**Tech Stack:** React 18, Vite, FastAPI, SQLAlchemy/PostgreSQL, Python Decimal, pytest; almacenamiento de objetos/volúmenes y trabajo asíncrono sujeto a verificación del despliegue Hetzner/Coolify.

**Spec:** `AuditSmart_Costo_Global_2026_Arquitectura_AuditBrain_Python.md` (documento maestro original externo, enlazar al repositorio antes del cierre final).

## Global Constraints
- Implementar primero en Portal de Clientes, no Command Center.
- No alterar comportamiento de ICT, Flujo de Efectivo ni herramientas existentes.
- Nunca sumar USD de MOD/GIF a cantidades físicas.
- Evitar doble conteo de MOI si viene incluida en CIF.
- Separar claramente DEMO/SIMULADO de datos reales; ninguna conciliación simulada se certifica.
- Mantener evidencia de origen, versión, usuario, archivo, hoja, fila, transformación y excepción.
- Trabajo pesado sin lecturas completas a RAM, con cuotas, colas, checkpoints y cancelación.
- Aplicar autorización por tenant y entitlement a CADA recurso, job y descarga (no solo al menú).
- No activar un módulo en producción hasta pasar seguridad, regresión y recuperación.
- Política costeo industrial y comercial distinta según clasificación de empresa.
- Ninguna fusión/despliegue automático si fallan puertas de calidad.

## Review Focus
1. Usuario cliente A intenta consultar/descargar proyecto de cliente B: 403/404 sin filtrar existencia (Task 1).
2. Archivo XLSX/CSV masivo o inválido: carga streaming, límite configurable, no OOM ni ejecución arbitraria (Task 2).
3. Mismo documento reimportado: idempotencia o rechazo explícito, nunca duplicar movimientos (Task 2).
4. Suministros, MOI y GIF solapados: excepción de doble conteo antes del estado (Task 4).
5. Balance contable ausente o mapping ambiguo: estado bloqueado, jamás diferencia artificial cero (Task 8).

## Task 0: Base de cálculo pura y trazable
**Files:** `backend/app/client_portal/costos/engine.py`, `tests/test_costos_engine.py`.
**Interfaces:** `CostState.from_mapping(data)`, `calculate(state)`, `compare_ledger(computed, ledger)`.
- [x] Añadir pruebas con OP 45638 (13.471,40 MP; 475,48 suministros; 607,99 MOD; 14.554,87 transferencia; 3.638,72 costo ventas).
- [x] Implementar cascada monetaria con Decimal, balances MP/PEP/PT y costos no absorbidos separados.
- [x] Ejecutar 10 pruebas unitarias localmente. **No es suite de integración del repositorio.**
- [ ] Hacer revisión de la categoría comercial: mercadería vs PT (mismos importes no implican flujo industrial).
- [ ] Ejecutar CI en PR.

## Task 1: Modelo multiempresa y permisos
**Files:** `backend/app/client_portal/costos/models.py`, `schemas.py`, `repository.py`, `tests/test_costos_auth.py`.
**Interfaces:** tenant `organization_id/client_id/project_id`, IDs de ejecución; acceso autenticado por dependencia.
- [ ] Crear pruebas que demuestren rechazo de acceso cruzado (RED).
- [ ] Implementar modelos y migración aditiva PostgreSQL, índices compuestos tenant/período y versionado.
- [ ] Pasar pytest y verificar aislamiento con Postgres de prueba.
- [ ] Commit independiente.

## Task 2: Ingestión masiva normalizada
**Files:** `backend/app/client_portal/costos/ingestion.py`, `jobs.py`, `tests/test_costos_ingestion.py`.
**Interfaces:** `submit_upload(tenant, slot, stream, checksum)` y `status(job_id)`.
- [ ] Probar CSV/XLSX grande, archivo corrupto, duplicado, interrupción y reintento (RED).
- [ ] Implementar lectura incremental, staging, checksum SHA-256, formatos de columnas/hojas, bitácora de errores.
- [ ] Worker separado con topes CPU/RAM/tiempo y concurrencia, sin acaparar API web.
- [ ] Verificar carga 100k/1M registros en entorno controlado según presupuesto aprobado.
- [ ] Commit independiente.

## Task 3: Catálogos, mapeo y formatos de entrada
**Files:** `backend/app/client_portal/costos/catalog.py`, `mapping.py`, `tests/test_costos_mapping.py`.
- [ ] Definir contratos versionados para saldos iniciales MP/suministros, compras, importaciones, OP/BOM, nómina/IESS, GIF, movimientos PT/ventas, mayor y balanza.
- [ ] Probar códigos duplicados, unidades incompatibles, líneas desconocidas y saldos no clasificados.
- [ ] Crear plantillas XLSX/CSV documentadas y parser configurable por cliente.
- [ ] Pruebas y commit.

## Task 4: Bloques 1–3 (MP, compras, MOD, MOI y GIF)
**Files:** `backend/app/client_portal/costos/inventory.py`, `labor.py`, `overhead.py`; tests individuales.
- [ ] Escribir primero casos de inventarios iniciales/compras/consumos e importaciones.
- [ ] Costo acumulado por OP, vínculo origen SKU/OP/transfer_id, exclusión de base eficiencia salarial no aprobada.
- [ ] Separación MOD/MOI/GIF y bases parametrizadas; NIC 2 capacidad normal y no absorbidos.
- [ ] Pruebas físicas, monetarias y commit por bloque.

## Task 5: Bloques 4–5 (PEP/PT, Kárdex y ventas)
**Files:** `backend/app/client_portal/costos/wip.py`, `finished.py`, `sales.py`; tests.
- [ ] Pruebas de movimientos, lotes, reversos, cortes, ventas duplicadas y unidades.
- [ ] Transferencias MP→PEP→PT→COGS por IDs trazables; no calcular cantidades físicas de USD.
- [ ] Modo OP real y modo estimado con procedencia diferenciada.
- [ ] Pruebas y commit por bloque.

## Task 6: Bloque 6 (conciliación integral de inventarios)
**Files:** `backend/app/client_portal/costos/reconciliation.py`, tests.
- [ ] Conciliar MP, PEP, PT por cantidades y valores, detectar transferencias huérfanas.
- [ ] Tratar el ejemplo OP 45638 como SIMULADO; repetir artículo 2615 y cinco salidas no asignadas como alertas.
- [ ] Pruebas y commit.

## Task 7: Bloque 7 (estado de costos) y comercial
**Files:** `backend/app/client_portal/costos/statements.py`, tests.
- [ ] Industrial: MP + MOD + GIF + cambios PEP/PT → costo de ventas.
- [ ] Comercial: inventario mercaderías + compras netas + ajustes – inventario final → costo de ventas, sin fingir producción.
- [ ] Separar diferencias contables, no absorbidos y ajustes; PDF/Excel auditables.
- [ ] Pruebas y commit.

## Task 8: Bloque 8 (mayores/contabilidad)
**Files:** `backend/app/client_portal/costos/ledger.py`, tests.
- [ ] Importar mayor/balanza, homologar cuentas, conciliación por cuenta/subcuenta/período.
- [ ] Comparar motor vs libros con diferencias NO forzadas; generar registro de excepciones con evidencia.
- [ ] Pruebas y commit.

## Task 9: API protegida y frontend definitivo
**Files:** `backend/app/client_portal/costos/router.py`; `frontend-client/src/costos/*`; tests API y E2E.
- [ ] Pruebas auth/entitlements, límites, navegación y no regresión ICT.
- [ ] Integrar rutas protegidas a router existente sin tocar rutas de producción.
- [ ] Implementar botones de documentos de entrada, ejecución, seguimiento, consulta, reportes y exportación.
- [ ] Incorporar las pantallas oscuras Audit-IA aprobadas, no reemplazarlas por simples tarjetas.
- [ ] Pruebas E2E con datasets simulados y commit.

## Task 10: Puertas de calidad, revisión y despliegue
**Files:** `tests/`, `docs/costos/*`, workflows CI autorizados.
- [ ] Ejecutar pytest, frontend build, E2E, seguridad multiempresa, benchmark, estrés y regresión ICT.
- [ ] Verificar backup/recovery, variables, límites y consumo en Hetzner/Coolify.
- [ ] PR listo para revisión únicamente con resultados reproducibles.
- [ ] Merge a main SOLO con suite verde, revisión y permiso de despliegue operacional.
- [ ] Publicación gradual y rollback probado. Nunca afirmar deploy por haber mergeado.

## Estado del plan
- PR #389: pantalla inicial y ruta + registro en catálogo existentes.
- Motor puro básico y sus pruebas: añadido en la misma rama. Sin API, ingesta ni motor productivo completo.
- Pendientes: Tasks 1–10, seguridad, volumetría, frontend aprobado y CI.
