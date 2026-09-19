# VNR Command Center — plan de implementación

> Ejecución nativa con superpowers:executing-plans; revisión independiente al terminar.

Objetivo: herramienta VNR operativa en AUD → Análisis → Inventarios y código reutilizable en artefactos.
Spec: ../specs/2026-09-19-vnr-command-center.md
Arquitectura: motor Decimal + exportadores puros; API FastAPI sin persistencia; React con estado de pestaña; distribución por archivos y manifiesto SHA256.

## Restricciones
Preservar JWT, autorización de proyecto y temas existentes. No credenciales nuevas ni integración IA simulada. Marco y política explícitos. Sin tasa tributaria predeterminada. Cero archivos de clientes en GitHub.

## Foco de revisión
- Precios faltantes, duplicados y formatos numéricos ambiguos bloquean el proceso.
- Reversiones y activos diferidos nunca se reconocen sin sustento explícito.
- Cambiar ficha, datos o parámetros invalida resultados y descargas anteriores.
- ZIP/XML, fórmulas inyectadas y archivos grandes no ejecutan código ni usan disco.
- Un proyecto ajeno o un usuario cliente no obtiene proceso/descarga/contexto.

## Tareas
- [ ] 1. Motor y contrato: tests en tests/test_vnr.py, engine.py y metadata.py; entrada normalizada por código, importes Decimal y validación previa. Verificar contra cálculo manual conocido, no valores generados por el propio motor.
- [ ] 2. Ingesta y exportadores: parsers.py, exports.py; doce cédulas, fórmulas y valores cacheados; tests de ZIP límites, texto peligroso y reapertura XLSX.
- [ ] 3. Router y React: router.py, api agregado, VnrTool.jsx, catálogo; pruebas con FastAPI independiente y dependencias de acceso simuladas; frontend build y recorrido.
- [ ] 4. Distribuir código probado en artefactos, manifiesto y guía de uso, crear ramas y PRs, comprobar cambios antes de integrar. Verificar publicación disponible sin declarar éxito solo por merge.

## Decisiones
Ruling: continuar con implementación conforme a la autorización previa del usuario y la metodología detallada en conversación; no repetir aprobación de arquitectura.
Ruling: conservar evidencia en memoria de la pestaña y procesar sin almacenamiento servidor para satisfacer limpieza; cerrar/recargar pierde datos no descargados, avisar visiblemente.
Ruling: extracción tabular automática solo cuando hay estructura inequívoca; imágenes/PDF no tabular requieren transcripción revisada, no inventar datos.
