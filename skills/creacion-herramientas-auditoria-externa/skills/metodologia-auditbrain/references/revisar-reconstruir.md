# Revisar y reconstruir una herramienta ya construida

Vale para un Excel de cualquier cuenta de balance (bancos, cuentas por cobrar, inventarios, activos fijos, intangibles, obligaciones financieras, provisiones, impuestos diferidos, patrimonio): el circuito es el mismo y lo que cambia es la norma de fondo del rubro.

Antes de abrir el archivo, confirmar marco y edición (M02), rubro y aseveraciones que pretende cubrir, contexto del encargo (M04) y si los datos son reales o ficticios —si son reales, anonimizar antes de cualquier análisis que salga del archivo.

Diagnóstico en tres capas, sin mezclarlas:

1. **Técnica**: hojas y rango real de datos; fórmulas vs. valores pegados presentados como cálculo; errores `#REF! #VALUE! #DIV/0! #N/A #NAME?`; rangos de suma que no cubren todas las filas; constantes incrustadas en fórmulas; vínculos externos; hojas ocultas; redondeos inconsistentes.
2. **Metodológica**: tabla M01–M17 con hoja y celda como evidencia (sección 5).
3. **Normativa del rubro**: manda la norma del marco confirmado; para los rubros cubiertos, encadenar con la skill `niif-revisor-rubro` e incorporar sus hallazgos como fondo, separados de los estructurales. Sin marco confirmado esta capa queda pendiente.

Luego: plan de cambios clasificado en bloqueante / recomendado / opcional, declarando qué cifras cambian y por qué; confirmación humana antes de modificar nada; reconstrucción en **versión nueva**, sin sobrescribir el original ni alterar retroactivamente un papel ya descargado; y verificación final con recálculo de cero errores y declaración de paridad —qué cifras coinciden con el original y cuáles cambian a propósito—. Una diferencia no explicada es un hallazgo, no una mejora.

Cautelas que evitan destruir el original: los vínculos a otros libros se pierden al re-guardar y recalcular (copiar antes esos valores o declarar que el libro no es reconstruible sin el archivo enlazado); un `.xlsm` pierde las macros salvo que se preserve el VBA; y las funciones modernas (XLOOKUP, FILTER, UNIQUE, SORT, SEQUENCE) pueden aparecer como error en el motor de verificación sin estarlo en Excel —se declara la limitación, no se borra la fórmula.

Procedimiento detallado y prompt listo para copiar: `metodologia/Prompt_revisar_reconstruir_excel.md`.
