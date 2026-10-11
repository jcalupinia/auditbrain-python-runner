# Factibilidad — Capa de Mapeo Universal → Motor Analítico (ingresos / costos / gastos)

**Fecha:** 2026-10-11 · **Decisión:** no construir por ahora; retomar cuando haya un
mayor real que el motor NO logre mapear.

## Pregunta

¿Puede la salida del **Motor de Ingesta / Capa de Mapeo Universal**
(`backend/app/ingesta/mapeo/`) alimentar las herramientas del Command Center de
**ingresos, costos y gastos** —«Análisis de mayores y diarios» y «Análisis de bases
de datos» (Ventas/Compras/Gastos)— para que acepten un mayor venga como venga el
formato del cliente?

## Hallazgos (verificados en código, ambos repos)

1. **Esas herramientas corren en un motor EXTERNO**, no en este repo:
   `jcalupinia/motor-auditoria-analitica`. El backend de este repo solo emite un
   permiso JWT + URL (`backend/app/aud/motor_analitico/router.py`); **el navegador
   sube el archivo directo al motor externo**, sin pasar por nuestro backend.

2. **El único archivo tabular que sube el usuario es el MAYOR.** Ingresos (ventas,
   cuentas 4), costos y gastos (cuentas 5) **no son archivos aparte**: el motor los
   **deriva internamente** del mayor + los XML del SRI.
   - Evidencia (repo externo): `motor/taac_ventas.py` («TAAC de ingresos y ventas»),
     `motor/taac_compras.py` («TAAC de compras, **costos y gastos**», lee
     `mayor_gastos` filtrado por prefijo de cuenta).

3. **El motor externo YA tiene su propia capa de mapeo flexible de columnas**, igual
   o más potente que la Capa de Mapeo Universal:
   - `motor/ingesta/mayor.py`: `SINONIMOS` por campo (`codigo`,
     `debe`/`debito`/`cargo`, `haber`/`credito`/`abono`…), detección de encabezado,
     formatos regionales (`_limpiar_importe`) y **perfiles ERP** que inyectan alias
     por cliente (`_sinonimos_con`).
   - `motor/ingesta/tipos.py`: la ingesta del mayor **fue portada de este mismo repo**
     (`backend/app/aud/obligaciones_fiscales/mayor/tipos.py`). Es la misma familia de
     lógica que la Capa de Mapeo.

4. **Hoy son caminos 100% separados.** Nada en AUD consume el `DatasetNormalizado`.
   Los únicos consumidores de `backend.app.ingesta` fuera de su paquete son
   `api/ingesta.py`, `client_portal/validador_sri.py` y
   `router_engine/master_router.py`.

5. **La Capa de Mapeo no tiene esquemas GASTOS/COSTOS/INGRESOS** (solo MAYOR,
   ASIENTO_DIARIO, BALANCE, VENTAS, COMPRAS en `mapeo/esquemas.py`).

## Conclusión

El problema que resuelve la Capa de Mapeo («aceptar un mayor venga como venga el
formato») **ya está resuelto dentro del motor externo**, para el mayor del que se
derivan ingresos/costos/gastos. Conectarla ahí **no agregaría capacidad; duplicaría
lógica ya probada** (contra la regla «no tocar lo probado» y «determinístico primero,
sin reinventar»). Además, el archivo no pasa por nuestro backend, así que no hay dónde
insertar la normalización sin re-arquitecturar el flujo navegador→motor.

## Qué sí tendría sentido (cuándo retomar)

1. **Gap real, no inventado.** Si aparece un **mayor real** que el motor externo NO
   logra mapear (encabezados que sus `SINONIMOS`/perfiles ERP no reconocen), ese es el
   trabajo concreto: ampliar los `SINONIMOS`/perfil ERP en `motor/ingesta/mayor.py`
   (repo externo), con el archivo que falla como caso de prueba.
2. **Otra dirección (este repo):** los procesadores NIIF de rubro —
   `backend/app/aud/niif/procesadores/{gastos_analisis.py (COSTOS_GASTOS),
   ingresos_contratos.py (INGRESOS), inventarios_costos.py}`— sí viven aquí y podrían
   recibir un **adaptador aditivo** `DatasetNormalizado → CAMPOS` sin tocar los
   procesadores. Es un camino distinto del motor externo.

**Estado:** en pausa a pedido del dueño (2026-10-11): «déjalo documentado y seguimos
cuando tenga un mayor real».
