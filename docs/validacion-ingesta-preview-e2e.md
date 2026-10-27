# Validación E2E de la ingesta masiva en un Preview aislado

> **Este PR NO debe fusionarse.** Existe únicamente para levantar un Preview aislado por PR y
> ejecutar la validación de extremo a extremo (E2E) de la ingesta masiva. Al cerrarlo, el
> controlador elimina el Preview.

## Objetivo

Validar, contra un backend realmente desplegado (no solo pruebas de componente), que
`/api/v1/ingesta/masiva/*` funciona de punta a punta en un Preview: carga de un archivo
sintético → `dataset_id` → persistencia en el SQLite aislado del PR → recuperación paginada →
conciliación de conteos y de sumas de débitos/créditos, con segregación por cliente/encargo.

## Requisitos operativos

- La ingesta masiva es **opt-in**: requiere la variable `INGESTA_MASIVA_SQLITE_PATH`
  (`/var/data/ingesta_masiva.sqlite`) definida en la aplicación de previews de Coolify. Está
  configurada a nivel de aplicación, por lo que **este preview la hereda** al desplegarse.
- No modifica `docker-compose.preview.yml` ni los Dockerfiles (plantilla confiable intacta).
- Datos **100 % sintéticos**; sin credenciales productivas ni datos de cliente.
- Autenticación del runner por `X-API-Key` (secreto `api_key` exclusivo del PR).

## Evidencia previa (de componente, ya obtenida)

Benchmark reproducible (SQLite temporal, sin red) de 100 001 filas: conteo íntegro y sumas
exactas (`×1.25` = 125001.25 débito; `×0.25` = 25000.25 crédito); RSS pico ~55 MB.
El arreglo del controlador de previews (verificación con reintentos, sin bucle de redespliegue)
ya está en `main`.

## Alcance

- Solo valida la **ingesta masiva** (persistencia y endpoints). La integración
  Ingesta → Motor Analítico queda **fuera de alcance** (requiere definir su contrato; es otra fase).
- No desplegar producción. No fusionar este PR.
