# Validación aislada: Ingesta masiva ↔ Motor Analítico (Preview por PR)

> Objetivo: validar el flujo **Ingesta masiva → población contable normalizada y
> persistida (`dataset_id`) → consumo por el Motor Analítico** en un **Preview
> aislado** de este PR, **sin tocar producción** ni usar datos de cliente.

## 1. Evidencia del benchmark reproducible (ya ejecutado)

`scripts/benchmark_ingesta_masiva.py --filas 100001 --lote 2000` (SQLite temporal,
sin red ni credenciales):

```json
{
  "filas_esperadas": 100001,
  "filas_persistidas": 100001,
  "suma_debe": "125001.25",
  "suma_haber": "25000.25",
  "duracion_segundos": 1.696,
  "rss_pico_mb": 54.96,
  "integridad_ok": true,
  "memoria_dentro_limite": true,
  "tipo_bd": "sqlite-temporal"
}
```

- Conteo íntegro: 100 001 filas persistidas = esperadas.
- Sumas exactas: débito `100001 × 1.25 = 125001.25`; crédito `100001 × 0.25 = 25000.25`.
- Streaming real: RSS pico ~55 MB (no materializa la población completa).

## 2. Cadena verificada en código (`main` fusionado)

- `POST /api/v1/ingesta/masiva/cargar` → `ingesta_masiva.ingerir_archivo` persiste en
  **SQLite aislada** (opt-in por `INGESTA_MASIVA_SQLITE_PATH`) y devuelve `dataset_id`,
  `total_filas`, `filas_revision`, `estado`.
- `GET /api/v1/ingesta/masiva/{dataset_id}/filas?cliente_id&encargo_id` → página de la
  población persistida (la fuente que consume el Motor Analítico por `dataset_id`).
- Mayor por secciones: `formato_mayor=secciones` normaliza y exige cuadre
  (`cuadra_reporte`) antes de persistir.

## 3. Prueba funcional en el Preview (pasos)

El Preview levanta backend + consola + portal con **BD y secretos exclusivos del PR**.

1. **Habilitar la ingesta masiva en el preview**: el `docker-compose.preview.yml` no
   define `INGESTA_MASIVA_SQLITE_PATH` (los endpoints `/ingesta/masiva/*` responden 503
   sin ella). Para la prueba, definir esa variable en la aplicación de previews en
   Coolify apuntando a una ruta `.sqlite` dentro del volumen del preview.
2. **Cargar** un mayor sintético de 100 001 filas (`cuenta,fecha,debe,haber`) por
   `POST /ingesta/masiva/cargar` → anotar `dataset_id`, `total_filas`, `estado`.
3. **Conteos y sumas**: recorrer `GET /ingesta/masiva/{dataset_id}/filas` y verificar
   100 001 filas y sumas `125001.25` / `25000.25`.
4. **Consumo por el Motor Analítico**: comprobar que el Analítico opera sobre el mismo
   `dataset_id` y que sus totales concilian con los de Ingesta (diferencia 0).

## 4. Aislamiento y limpieza

- Sin credenciales productivas ni datos de cliente (población sintética).
- El admin del preview (`preview-admin@audit-ia.ec`) usa contraseña efímera en
  `/run/secrets/admin_password` (no se imprime).
- Al **cerrar o fusionar** este PR, el controlador elimina el preview (contenedores,
  red, dominios y BD del PR). Este PR **no debe fusionarse**: es solo validación.
