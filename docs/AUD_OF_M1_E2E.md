# AUD Obligaciones Fiscales · M1 · Checklist E2E

Verifica que la herramienta funciona end-to-end en producción tras el merge a `main`.

## Pre-requisitos

- [ ] Branch `feat/aud-of-m1` mergeada a `main`
- [ ] Render auto-deploy verde (backend + frontend)
- [ ] Logs de Render no muestran error al arrancar (`init_db OK`, `aud_of cleanup loop started`)
- [ ] Postgres tiene la tabla nueva `tool_jobs` (verificar en logs de inicio)
- [ ] Variables de entorno definidas (sí existen los defaults pero podemos overridear):
  - `AUD_OF_JOB_TTL_MINUTES` (default 60)
  - `AUD_OF_MAX_FILE_MB` (default 20)
  - `AUD_OF_TMP_DIR` (default `/tmp/auditbrain/obligaciones_fiscales`)

## Verificación funcional

1. [ ] Login en https://auditbrain-frontend.onrender.com con admin
2. [ ] WKS Workspaces → si no existe, crear un cliente de prueba
3. [ ] WKS → crear proyecto con `module_code = AUD` y período "Ejercicio 2025"
4. [ ] Activar el proyecto con el selector "Workspace" en el header
5. [ ] Click en el módulo **AUD** en el sidebar
6. [ ] Click en la pestaña **Análisis** del Workspace cognitivo
7. [ ] Ver el **catálogo de 15 categorías**, todas con badge "Próximamente" excepto **Impuestos**
8. [ ] Click en la herramienta **Auditoría de Obligaciones Fiscales**
9. [ ] Aparece el form con:
   - Inputs: Cliente, Período, Fecha de corte, Preparado/Revisado por
   - 6 zonas de upload (F-104 marcada como requerida, resto opcionales)
10. [ ] Llenar Cliente="NEGOCIOS MORACOSTA S.A.", Período="Ejercicio 2025"
11. [ ] Subir 1 PDF F-104 real al slot "F-104 IVA"
12. [ ] Click **"Generar papel de trabajo"** → status pasa a `processing`
13. [ ] Después de ~10-30s, status pasa a `done`
14. [ ] Aparece el botón **"Descargar Excel"** y un resumen JSON
15. [ ] Click → se descarga el archivo `DM_Obligaciones_Fiscales_*_*.xlsx`
16. [ ] Abrir el Excel localmente:
    - Pestaña **"DM7 Retenciones x pagar"**: fila de Enero (row 21) tiene casilleros H21/I21/J21/K21/L21/M21 pobladas con valores del PDF
    - Pestaña **"DM6 IVA"**: encabezado actualizado con cliente y período
    - Otras pestañas: contenido original de plantilla intacto (no se sobreescriben formulas existentes)

## Verificación de cleanup

- [ ] Crear un job y NO descargarlo. Esperar 1 hora.
- [ ] Pasada la hora: `GET /api/v1/aud/obligaciones-fiscales/jobs/{id}` devuelve status `expired`
- [ ] El directorio `/tmp/auditbrain/obligaciones_fiscales/{job_id}/` ya no existe en el contenedor (verificar via shell de Render si es accesible)

## Verificación de multi-tenant

- [ ] Crear otro admin en una organización distinta (SQL directo o segundo proyecto)
- [ ] El admin B NO debe ver jobs creados por admin A en `GET /jobs?project_id=X`
- [ ] El admin B con `GET /jobs/<id_de_A>` debe recibir 403 Forbidden

## Verificación de error handling

- [ ] Intentar subir un .xlsx al slot F-104 → recibe 415 Unsupported Media Type
- [ ] Intentar crear job sin ningún PDF → recibe 400 con mensaje "Sube al menos 1 PDF F-103 o F-104"
- [ ] Subir un PDF corrupto (cambiar bytes) → job termina con status `failed` y `error_message` poblado

## Criterio de éxito M1

Todo arriba en verde → M1 DONE. Listos para arrancar M2:
- M2.1: parser de mayor de compras Excel
- M2.2: parser de mayor de ventas Excel
- M2.3: cédulas DM3, DM4, DM5 (Sumaria + Compras + Ventas)
- M2.4: ATS XML parser + cédula DM8
- M2.5: F-101 PDF + cédulas DM9, DM10

## Bloqueos a resolver antes de M2

- [ ] Conseguir 12 F-104 reales anonimizados (o usar los del cliente del usuario)
- [ ] Conseguir 12 F-103 reales (para cédulas Sumaria, ingresos retenciones)
- [ ] Conseguir mayores Excel de prueba (Compras, Ventas, Balance)
- [ ] Conseguir 1 ATS XML de prueba
- [ ] Conseguir 1 F-101 PDF de prueba
