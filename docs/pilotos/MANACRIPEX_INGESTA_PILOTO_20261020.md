# Piloto MANACRIPEX: ingesta persistente (20-10-2026)

## Alcance autorizado
Implementar en esta rama, sin despliegue ni alteraciones de produccion, la ingesta del mayor contable y su consulta reutilizable. No crear una segunda base PostgreSQL. No incluir credenciales ni datos de clientes en Git.

## Evidencia previa (por corroborar en pruebas automatizadas)
- Backend conectado a auditbrain-db mediante DATABASE_URL y SELECT exitoso.
- Mayor MANACRIPEX procesado: 34.842 movimientos, 531 cuentas, debe/haber USD 84.532.027,87 cada uno.
- Cuenta 1010101002 Caja Chica Oficina: saldo esperado USD 113,98 al 2026-08-31; diferencia esperada USD 0,00.
- Tablas observadas: tool_jobs, aud_prueba_archivos, mayor_clasificacion_job, mayor_homologaciones, mayor_categorias.

## Secuencia de implementacion
1. Localizar parser/API de ingesta existente y documentar contrato de entrada/salida. Confirmar si fecha, asiento, comprobante y descripcion existen en el archivo original; nunca inventarlos.
2. Revisar modelos y migraciones actuales. Reutilizar entidades de proyecto/encargo/archivo y proponer migracion aditiva, reversible, para detalle de movimientos SOLO si no existe estructura equivalente. No ejecutar migracion en produccion.
3. Campos minimos: organizacion/cliente, encargo/proyecto, periodo, archivo_id, sha256 origen, version de carga, fila_origen, cuenta_codigo, cuenta_nombre, fecha, asiento, comprobante, descripcion, debe NUMERIC, haber NUMERIC; admitir nulos para campos ausentes, registrar calidad de datos.
4. Ingesta atomica e idempotente por archivo+version; impedir doble contabilizacion y cruces entre organizaciones. Validar conteo, sumas, naturaleza de movimientos, errores y trazabilidad.
5. API autenticada de consulta por organizacion, encargo, periodo y cuenta, con filtros de autorizacion del servidor; paginacion y sumas deterministicas. MCP debe consultar la API autorizada, no exponer DATABASE_URL.
6. Pruebas con fixture anonimizado y luego dataset MANACRIPEX autorizado: 34.842 filas, 531 cuentas, sumas debe/haber 84.532.027,87; consulta 1010101002 saldo 113,98 al 2026-08-31 y diferencia 0,00 con balance, siempre comprobando formula saldo inicial+movimientos y corte.
7. Registrar pruebas y limitaciones; abrir PR para revision. Sin merge, deploy, cambios Coolify, backups ni produccion sin autorizacion adicional.

## Criterio de terminado
Pruebas automatizadas en verde, migracion revisada y reversible, API protegida y consulta Caja Chica conciliada con evidencia. Un documento o rama por si solos NO acreditan piloto operativo.

## Riesgos abiertos
Ubicacion real del parser y del archivo original; esquema de relaciones y version efectiva de PostgreSQL; saldo inicial y signo de la cuenta; permisos por tenant; estrategia de rollback.
