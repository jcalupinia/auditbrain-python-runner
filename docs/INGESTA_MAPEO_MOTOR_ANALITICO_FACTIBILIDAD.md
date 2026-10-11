# Factibilidad — Capa de Mapeo Universal → Motor Analítico (ingresos / costos / gastos)

> **Registro de decisión (ADR).** Fecha: 2026-10-11 · Estado: **En pausa** por
> decisión del dueño.
>
> **Veredicto:** **No se construye** la conexión de la Capa de Mapeo Universal a las
> herramientas de ingresos/costos/gastos del Command Center. El motor que las ejecuta
> ya resuelve «aceptar un mayor venga como venga el formato»; conectarla duplicaría
> lógica ya probada.
>
> **Disparador para retomar:** que aparezca un **mayor real que el motor NO logre
> mapear** (gap verificable con el archivo que falla).

## 1. Pregunta

¿Puede la salida del **Motor de Ingesta / Capa de Mapeo Universal**
(`backend/app/ingesta/mapeo/`) alimentar las herramientas de **ingresos, costos y
gastos** del Command Center —«Análisis de mayores y diarios» y «Análisis de bases de
datos» (Ventas/Compras/Gastos)— para que acepten un mayor con cualquier formato de
cliente?

## 2. Respuesta corta

No aporta, porque el flujo real es:

```
Navegador  ──(sube el MAYOR + XML del SRI)──►  Motor externo (motor-auditoria-analitica)
                                               │  mapea columnas (SINONIMOS + perfiles ERP)
                                               └► deriva ventas (4) / costos·gastos (5)
```

El archivo **no pasa por nuestro backend**, y el motor **ya mapea el mayor** por su
cuenta. La Capa de Mapeo Universal no tiene dónde insertarse ni qué agregar.

## 3. Hallazgos (verificados en código, ambos repos)

| # | Hallazgo | Evidencia |
|---|----------|-----------|
| 1 | Las herramientas corren en un **motor EXTERNO**, no en este repo. Nuestro backend solo emite permiso (JWT + URL); el **navegador sube el archivo directo al motor**. | `backend/app/aud/motor_analitico/router.py` · repo `jcalupinia/motor-auditoria-analitica` |
| 2 | El **único archivo tabular** que sube el usuario es el **MAYOR**. Ingresos (ventas, cuentas 4), costos y gastos (cuentas 5) **se derivan dentro del motor** del mayor + XML del SRI; no son archivos aparte. | (externo) `motor/taac_ventas.py` («TAAC de ingresos y ventas»), `motor/taac_compras.py` («TAAC de compras, **costos y gastos**», lee `mayor_gastos` por prefijo de cuenta) |
| 3 | El motor **ya tiene su propia capa de mapeo flexible** del mayor, igual o más potente: sinónimos por campo, detección de encabezado, formatos regionales y **perfiles ERP** por cliente. | (externo) `motor/ingesta/mayor.py` (`SINONIMOS`, `_sinonimos_con`, `_limpiar_importe`) |
| 4 | Esa capa del motor **fue portada de este mismo repo** (misma familia de lógica que la Capa de Mapeo). | (externo) `motor/ingesta/tipos.py` ← `backend/app/aud/obligaciones_fiscales/mayor/tipos.py` |
| 5 | Hoy son **caminos 100 % separados**: nada en AUD consume el `DatasetNormalizado`. | Únicos consumidores de `backend.app.ingesta`: `api/ingesta.py`, `client_portal/validador_sri.py`, `router_engine/master_router.py` |
| 6 | La Capa de Mapeo **no tiene esquemas GASTOS/COSTOS/INGRESOS** (solo MAYOR, ASIENTO_DIARIO, BALANCE, VENTAS, COMPRAS). | `backend/app/ingesta/mapeo/esquemas.py` |

## 4. Conclusión

El problema que resuelve la Capa de Mapeo («aceptar un mayor venga como venga el
formato») **ya está resuelto dentro del motor externo**, para el mayor del que se
derivan ingresos/costos/gastos. Conectarla ahí **no agregaría capacidad y duplicaría
lógica ya probada**, contra las reglas «no tocar lo probado» y «determinístico primero,
sin reinventar». Además, al no pasar el archivo por nuestro backend, no hay dónde
insertar la normalización sin rearquitecturar el flujo navegador→motor.

## 5. Cuándo retomar (y por dónde)

1. **Gap real, no inventado.** Si aparece un **mayor real** que el motor NO logre
   mapear (encabezados que sus `SINONIMOS`/perfiles ERP no reconocen), el trabajo
   concreto es ampliar los `SINONIMOS`/perfil ERP en `motor/ingesta/mayor.py` (repo
   externo), usando el archivo que falla como caso de prueba.
2. **Vía alternativa (este repo), aditiva.** Los procesadores NIIF de rubro sí viven
   aquí y podrían recibir un **adaptador** `DatasetNormalizado → CAMPOS` **sin tocar**
   los procesadores (camino distinto del motor externo):
   - `backend/app/aud/niif/procesadores/gastos_analisis.py` — rubro `COSTOS_GASTOS`
   - `backend/app/aud/niif/procesadores/ingresos_contratos.py` — rubro `INGRESOS`
   - `backend/app/aud/niif/procesadores/inventarios_costos.py` — costos de inventario (NIC 2)

---

_Pausa a pedido del dueño (2026-10-11): «déjalo documentado y seguimos cuando tenga un
mayor real»._
