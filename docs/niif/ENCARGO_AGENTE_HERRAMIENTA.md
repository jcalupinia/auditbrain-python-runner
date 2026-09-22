# Encargo común para cada agente constructor de herramienta

Repositorio (worktree): `C:\Users\jcalu\Desktop\PROYECTOS CLAUDE\_wt-command-center` — trabaja SOLO ahí.

1. Lee completo `docs/niif/CONTRATO_PROCESADOR.md` y sigue el contrato al pie de la letra.
2. Lee `backend/app/aud/niif/procesadores/pce_simplificada_niif9.py` (referencia verificada: estructura,
   cédulas con fórmulas, definición, EJEMPLO) y `backend/app/aud/niif/procesadores/base.py` (piezas comunes).
3. Si tu herramienta tiene sección en la especificación del socio, léela:
   `C:\Users\jcalu\Downloads\AUDITBRAIN_ESPECIFICACION_MAESTRA_AMPLIADA_CLAUDE_CODE.md` (y para Efectivo,
   `C:\Users\jcalu\Downloads\AUDITBRAIN_EFECTIVO_EQUIVALENTES_ESPECIFICACION_V1.md`). Las PRUEBAS y CÁLCULOS que
   te asigno abajo son los que manda la matriz del socio: cúbrelos TODOS (cada prueba = al menos una cédula o una
   columna/control de una cédula; las de procedimiento —confirmaciones, circularización, corte— se modelan con los
   datos que el cliente entrega: saldo confirmado vs libros, fechas de documento vs registro, etc.).
4. Norma: consulta el texto oficial cuando sea posible (EUR-Lex en español para NIIF completas:
   https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803 ; PYMES en ifrs.org). Cita párrafos;
   lo que no leas, marca «VERIFICAR». Si la norma difiere entre NIIF completas y PYMES (2015/2025), enruta en
   `ejecutar` con `es_pymes(p)` / `edicion_pymes(p)` y cubre ambas rutas en `ESCENARIOS`.
5. Tasas y valores legales de Ecuador (impuesto a la renta, IESS, SBU, participación, reserva legal…): van como
   PARÁMETROS con su valor por defecto y la nota «vigente al corte; VERIFICAR», nunca fijos en el código.
6. Construye `backend/app/aud/niif/procesadores/<id>.py` y `tests/test_proc_<id>.py`.
7. Corre tu prueba: `python -m pytest tests/test_proc_<id>.py -q -p no:warnings` (verde).
8. Corre `python scripts/verificar_formulas.py <id>` hasta `DIFERENCIAS: 0`. Si Excel está ocupado por otro agente,
   reintenta pasado un minuto.
9. NO edites ningún archivo existente; NO hagas commit; NO corras la suite completa ni pruebas HTTP.

Informe final (en español, breve): archivos creados; cédulas; resultado del EJEMPLO con 3–5 cifras recalculadas a
mano; problemas que muestra el ejemplo; rutas por marco; salida de pytest y del verificador (fórmulas comparadas y
diferencias); lista de «VERIFICAR»; dudas para el socio.
