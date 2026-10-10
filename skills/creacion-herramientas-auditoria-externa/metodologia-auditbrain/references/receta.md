# Receta: construir una prueba NIIF de punta a punta

La secuencia que funcionó en VNR, pérdidas incurridas y pérdida esperada. Cada paso termina con evidencia, no con una intención.

1. **Marco y modelo (M02).** Confirmar NIIF plenas o PYMES y qué modelo impone el marco al rubro. Ejemplo que no se debe confundir: cuentas por cobrar comerciales → PYMES Secc. 11 **pérdida incurrida** (sin evento de pérdida no hay deterioro; la 3.ª edición 2025 lo mantiene); NIIF 9 → **pérdida esperada**, enfoque simplificado 5.5.15 con matriz B5.5.35 (ningún tramo en cero por omisión). La ficha declara `frameworks` y la herramienta avisa si el encargo usa otro marco.
2. **Leer la norma (M03).** Tabla párrafo → qué establece → cómo lo aplica el cálculo, más lo que la norma **no permite** y la herramienta respeta. NIA aplicables con párrafo y exigencia concreta. Tributario Ecuador (LRTI/RALRTI) marcado «VERIFICAR» hasta leerlo vigente al corte.
3. **Diseño más simple que cumple.** Preguntar qué versión basta: la norma suele ofrecer una solución práctica (p. ej. matriz de provisiones). Menos anexos, mismos requisitos normativos.
4. **Ficha (bloques A–E).** A base técnica · B programa (código, objetivo, riesgo, afirmación, procedimiento, evidencia, criterio, fuente) · C requerimientos por ítem con columnas y uso cálculo/soporte (M17) · D criterios de aceptación y rechazo · E procesamiento con parámetros, pasos, cédulas, problemas y el **ejemplo numérico** (M19).
5. **Dónde vive el cálculo (M18).** Declarativo o procesador; si es procesador, un anexo = un requerimiento con su modelo Excel para el cliente.
6. **Construir y probar.** Pruebas con el ejemplo de la ficha y casos límite: saldo negativo, duplicado, sin historia, denominador cero, 29 de febrero, pesos en cero, tasa individual, descuento. Luego el ciclo completo por la API (del modelo Excel al papel aprobado).
7. **Cédulas con fórmulas y verificación en Excel real (M20).** Cero diferencias y prueba de mutación.
8. **Formatos (M21).** Excel, HTML sin internet con descargas, Word, PowerPoint, PDF.
9. **Prueba en pantalla (M24).** Recorrer la vista de trabajo con datos ficticios: subir, Procesar, revisar cédulas, aprobar, descargar. Recalcular a mano las cifras principales.
10. **Producción.** Desplegar, crear la ficha en «Diseñar fichas», instalar el cálculo, reproducir el ejemplo de control en producción, marcar probada.
11. **Validación del socio (M23).** Enviar el papel de muestra; corregir lo que observe; enviar al catálogo solo con su aprobación expresa.
12. **Registrar.** Ficha actualizada con lo verificado (fecha, pruebas, cifras) y lo pendiente.

**Lecciones que dieron origen a M18–M23:** el primer Excel de pérdidas incurridas salió con valores pegados en lugar de fórmulas y se detectó al revisar antes de publicar (M20, M21); en pérdida esperada, el verificador en Excel encontró una referencia circular y una celda vacía convertida en 0 % que las pruebas unitarias no veían (M20, M22); una tasa fijada por el auditor pisaba tasas medidas de otros segmentos (M22); y las fichas enviadas no aparecían en el catálogo del módulo hasta enlazarlo por rubro (M23).
