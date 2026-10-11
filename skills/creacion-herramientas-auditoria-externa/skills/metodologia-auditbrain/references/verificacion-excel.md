# Verificación del Excel (M20)

Objetivo: demostrar que cada importe del libro es una fórmula viva que da **el mismo valor** que el motor.

1. Generar el libro con datos ficticios que ejerciten todos los caminos: segmentos, tramos sin historia, saldos
   negativos, duplicados, tasas fijadas, tasas individuales, descuento, pesos distintos.
2. **Abrir en Excel real** y recalcular por completo (en Windows, `win32com` + `CalculateFull()`). Un lector de
   fórmulas no equivale: no reproduce cómo Excel trata celdas vacías, referencias circulares ni fechas.
   Si no hay Excel disponible, declarar la verificación como **Pendiente** (M15): no se marca Cumple.
3. Recorrer **todas** las celdas con fórmula y comparar con el valor del motor: importes con tolerancia de medio
   centavo; tasas con 1e-6. Resultado aceptable: **DIFERENCIAS: 0**.
4. **Prueba de mutación:** alterar a propósito una fórmula (p. ej. el exponente del descuento) y volver a correr; el
   verificador debe reportar diferencias. Si no las reporta, no verifica nada.
5. Revisar además: texto que empieza con `=`, `+`, `-`, `@` sin ser fórmula (Excel lo repararía), errores
   `#REF! #VALUE! #DIV/0! #N/A`, paneles congelados, anchos, filas TOTAL con borde doble.

Errores reales que solo encontró este método: referencia circular en una tasa promedio (`C/B` en la propia columna C);
`IF(D<>"",D,E)` que devuelve 0 cuando E está vacía (debe ser `IF(D<>"",D,IF(E<>"",E,""))`); tasa promedio de Python
calculada con importes ya redondeados.

Guion de referencia en el repositorio del Command Center: `scripts/verificar_formulas_pi.py` y
`scripts/verificar_formulas_pce.py`.
