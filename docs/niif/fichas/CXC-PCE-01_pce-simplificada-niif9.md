# CXC-PCE-01 · Pérdida crediticia esperada de cuentas por cobrar — enfoque simplificado (NIIF 9)

**Cuenta:** Cuentas por cobrar comerciales · **Marco:** solo **NIIF completas**
**Procesador:** `pce_simplificada_niif9` (`backend/app/aud/niif/procesadores/pce_simplificada_niif9.py`)
**Estado:** construida y verificada; pendiente de la aprobación del dueño para enviarla al catálogo.

> Las PYMES no usan esta ficha: la tercera edición de la NIIF para las PYMES (2025) **mantiene** el modelo de
> pérdida incurrida (Sección 11) → ficha `CXC-PI-01`.

Texto de la norma leído en el Reglamento (UE) 2016/2067 (NIIF 9 en español, con su guía de aplicación).

## A · Base técnica

| Párrafo | Qué establece | Cómo lo aplica la herramienta |
|---|---|---|
| **5.5.15** | Cuentas por cobrar comerciales y activos por contratos (NIIF 15): corrección de valor **siempre** igual a la pérdida esperada durante toda la vida | Una sola medición; no hay etapas ni análisis de aumento significativo del riesgo |
| **B5.5.35** | Solución práctica: **matriz de provisiones** por días de mora con el historial de pérdidas; agrupar por segmentos si pierden distinto | Matriz por tramo y segmento opcional (columna del anexo) |
| **5.5.17** | Importe (a) ponderado por probabilidad, (b) con valor temporal del dinero, (c) con información pasada, actual y **prospectiva** | (a) tres escenarios con peso; (b) tasa efectiva y plazo (0 % por defecto, con sustento); (c) factor prospectivo |
| **B5.5.51–B5.5.53** | El historial es el ancla, **ajustado** a condiciones actuales y previstas; las tasas se aplican a grupos definidos igual que los medidos | Tasa histórica × factor; mismos tramos y segmentos en historia y en cartera |
| **B5.5.37** | Presunción de impago a los **90 días** de mora | Marca «en impago» y cuenta como pérdida lo que un año después sigue impago |
| **5.4.4** | Baja de lo que no se espera recuperar | Los castigos del año entran en la tasa histórica y en el movimiento |
| **NIIF 7 35H, 35M, 35N** | Conciliación de la corrección de valor y exposición por grado de riesgo (matriz de provisiones admitida) | Cédulas «Movimiento» y «Revelación NIIF 7» |

**NIA:** 540 (Revisada) párr. 13 y 17–30 · 500 párr. 9 · 505 párr. 7 · 560 párr. 6.
**Tributario:** LRTI Art. 10 num. 11 (1 % anual sobre la cartera corriente, 10 % acumulado) y NIC 12 para el diferido.

## B · Programa

CXCPCE-01 integridad · 02 tasas históricas · 03 información prospectiva · 04 medición · 05 movimiento,
castigos y revelación · 06 fiscal · 07 cobros posteriores.

## C · Requerimientos

| id | Documento | Uso | Obligatorio |
|---|---|---|---|
| RQ-001 | Cartera por factura al corte del ejercicio | cálculo | Sí |
| RQ-002 | Cartera por factura al corte del ejercicio anterior | cálculo | Sí |
| RQ-003 | Castigos del ejercicio por factura | cálculo | No (recomendado) |
| RQ-004 | Información prospectiva (proyecciones, indicadores) | soporte | Sí |
| RQ-005 | Política de crédito y gestión de clientes en mora | soporte | Sí |
| RQ-006 | Cobros posteriores al cierre | soporte | No |

Columnas de la cartera: N° de factura, cliente, vencimiento, saldo; **opcionales** segmento, tasa individual (%) y RUC.
La provisión registrada y la inicial se ingresan como parámetros (del mayor).

## E · Procesamiento

1. Tramos: corriente, 1–30, 31–60, 61–90, 91–180, 181–360, más de 360 días.
2. Tasa histórica por segmento y tramo = (sigue impago un año después + castigado) ÷ saldo positivo al corte anterior.
   El cruce es por N° de factura (el mismo que haría SUMIF en el Excel).
3. Sin historia, el auditor fija la tasa por tramo (se aplica a todos los segmentos). Nunca queda en cero por omisión:
   la herramienta lo marca como problema.
4. Factor prospectivo = Σ peso × (1 + ajuste) ÷ Σ peso. Por defecto 1,00 con aviso para documentarlo.
5. Pérdida esperada por factura = saldo × min(tasa × factor; 100 %) ÷ (1 + i)^(plazo/12); tasa individual si se informa.
6. Ajuste = pérdida esperada − provisión registrada. Dotación neta = final − inicial + castigos.
7. Fiscal y diferido sobre totales.

**Ejemplo de control (E.6):** al corte anterior el tramo 31–60 tenía 2.000; un año después 150 siguen impagos y 50
se castigaron → 10 %. Escenarios 60 %×0 %, 20 %×−10 %, 20 %×+25 % → factor 1,03 → 10,3 %. Una factura de 3.000 en
ese tramo espera perder **309,00**.

## Verificación (2026-09-21)

- `tests/test_aud_procesador_pce.py`: ejemplo, tasa fijada, individual, descuento, escenarios y ciclo HTTP completo.
- `scripts/verificar_formulas_pce.py`: Excel real, 592 fórmulas en dos escenarios, **0 diferencias**. Encontró y
  se corrigió una referencia circular en la tasa promedio de la revelación NIIF 7.
