# Patrón · Calculadora de liquidación hipotética al corte (p. ej. vacaciones no gozadas)

Para pasivos que dependen de un registro auxiliar del cliente (kárdex) y de la antigüedad de cada trabajador.

## Estructura (generador tipo `mk_vac.py`)
- **Ficha** (parámetros azules, con sustento): fecha de corte, cierre anterior, días base, adicionales por antigüedad
  (desde el año 6, máx. 15), **tope de acumulación en períodos** (decisión del socio; 0 = sin tope), **base del valor
  día** (lista: remuneración de corte / 30 · promedio 12 meses / 30).
- **Kárdex** (RQ-008, opcional): días gozados/pagados por trabajador.
- **Cálculo por trabajador activo**: devengados = 15·Y + Σ adicionales + fracción del año en curso; saldo = devengados −
  gozados (con tope: `MIN(saldo, tope × días del año en curso)`, estado «Tope aplicado»); pasivo = saldo × valor día.
  Columna alternativa con la otra base del valor día.
- **Resumen**: Σ pasivo vs libros al corte → ajuste; pasivo correcto al cierre anterior vs libros → resultados
  acumulados (NIC 8); gasto del año por diferencia.
- **Asiento propuesto** habilitado solo con estado CALCULADO.

## Estados y alertas
NO SOPORTADO (sin kárdex: observación automática, M32) · PARCIAL (no concluyente) · CALCULADO. Alertas: saldo negativo,
más de tres períodos acumulados (art. 75 CT), tope aplicado.

## Modo demostración
`python3 mk_vac.py DEMO <salida>` genera una copia con datos ficticios para probar la mecánica. Ejemplo de control:
ingreso 2018-03-01, corte 2026-12-31, remuneración 1.200, gozados 100 → devengados 141,88, saldo 41,88, pasivo 1.675,20.
