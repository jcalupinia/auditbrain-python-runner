# Encargo común para cada agente constructor de herramienta

Repositorio (worktree): `C:\Users\jcalu\Desktop\PROYECTOS CLAUDE\_wt-command-center` — trabaja SOLO ahí.

1. Lee completo `docs/niif/CONTRATO_PROCESADOR.md` y sigue el contrato al pie de la letra. Pon atención a
   «Lo que exige el papel de trabajo»: `PANEL`, `REF_PROBLEMAS`, explicación humana por columna (`explica`),
   hojas de datos del cliente (`D1_…` con `guia` y origen) y **ninguna cifra calculada pegada**.
2. Lee `backend/app/aud/niif/procesadores/pce_simplificada_niif9.py` (estructura, cédulas con fórmulas,
   definición, EJEMPLO), `backend/app/aud/niif/procesadores/perdidas_incurridas_s11.py` (piloto del papel actual:
   datos del cliente dentro del libro, `EXPLICA`, `PANEL`, `REF_PROBLEMAS`) y `procesadores/base.py`
   (piezas comunes; `hoja(..., explica=, guia=, ocultas=, origen=)`).
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
9. Corre `python scripts/verificar_explicaciones.py <id>` (sin faltantes) y
   `python scripts/verificar_problemas_enlazados.py <id>` (`PENDIENTES: 0`).
10. Corre las pruebas transversales filtradas a tu herramienta (no usan base de datos):
    `python -m pytest -q -p no:warnings tests/test_aud_sin_datos_fijos.py tests/test_aud_html_premium.py tests/test_aud_office_como_html.py -k <id>`.
11. Genera tu papel de muestra y míralo: `python scripts/papeles_muestra.py <carpeta> <id>` (Excel, HTML, PDF,
    Word, PowerPoint). La portada del Excel, el Word y el PowerPoint deben mostrar las 5 tarjetas y los 4 gráficos
    del panel del HTML; si algo sale vacío o raro, el problema está en tu `PANEL` o en tus cédulas.
12. NO edites ningún archivo existente (tampoco `libro.py`, `panel_excel.py`, `papel_office.py`, `svg_png.py`,
    `html_ejecutivo.py`, `graficos*.py`, `problemas.py`, `base.py`); NO hagas commit; NO corras la suite completa
    ni pruebas HTTP.

Informe final (en español, breve): archivos creados; cédulas (y hojas de datos del cliente, si las hay); resultado
del EJEMPLO con 3–5 cifras recalculadas a mano; problemas que muestra el ejemplo y a qué celda remite cada uno
(`REF_PROBLEMAS`); rótulos del `PANEL`; rutas por marco; salida de pytest y de los tres verificadores (fórmulas
comparadas y diferencias, explicaciones, problemas enlazados); lista de «VERIFICAR»; dudas para el socio.
