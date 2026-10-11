# Patrón · Lectura y conciliación de mayores contables (RQ-004)

Aplicable a cualquier rubro cuyo «según libros» salga de mayores del cliente (nómina, proveedores, provisiones).

## Lectura
1. Normalizar cada archivo a un DataFrame con: cuenta, fecha, mes, asiento, referencia, concepto/explicación, débito,
   crédito, **importe = débito − crédito** (débito +, crédito −).
2. Detectar saldo inicial (fila «SALDO ANTERIOR» o equivalente) y separarlo de los movimientos.
3. Clasificar cada movimiento por reglas explícitas sobre el texto del concepto (diccionario en código, en orden de
   prioridad). Nómina, pasivo de beneficios:
   - PROVISION — «DECIMO 13», «DECIMO 14», «VACACIONES» (provisión mensual)
   - FINIQUITOS — «LIQ.», «VAC.FINIQUIT»
   - GOCES — «VAC TOMADAS»
   - PAGOS — «TRANSF», «PGO», «PAGO»
   - AJUSTES — todo lo demás (se revisa uno a uno)
   IESS por pagar: por la columna de referencia del cliente; los pagos se separan en pago al IESS, notas de crédito
   (p. ej. permisos médicos) y otros.
4. No usar nombres de columna `cat`, `str`, `dt` (choque con accesores de pandas): usar `clase`.

## Controles antes de usar el mayor (M33)
- Por cuenta de pasivo: saldo inicial (anexo) + Σ movimientos = saldo final (ESF). Diferencia 0,00.
- Gasto: Σ mayor por cuenta = anexo en cuentas comunes; listar las cuentas solo en el mayor y solo en el anexo.
- Reversiones: identificar pares cargo/abono del mismo importe en el mes (no confundir con pagos).

## Funciones de servicio para las cédulas
`gasto_mes(concepto)`, `gasto_cta(cuenta)`, `pasivo_mes(df, cuenta, clase)`, `pasivo_tot(df, cuenta, clase)` y un dict
`ANEXO = {cuenta: (saldo_anterior, saldo_actual)}`. Las cédulas escriben estos valores en una hoja «Mayor RQ-004» del
libro y las celdas de cálculo la referencian con fórmulas calificadas (`='Mayor RQ-004'!D12`).

## Regla de pagos a entidades con planilla mensual
El pago del mes m corresponde a la planilla del mes m−1; el de enero cancela el saldo inicial y la planilla de
diciembre queda como saldo final. Conciliar pagos por período contra comprobantes y explicar el residual.
