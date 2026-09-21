# Exportador del sitio AuditBrain — copia vendorizada

Estos archivos son **los mismos** de `auditbrain-site/lib/` (tools/, methodology.mjs y requirement.mjs), sin
editar. Arman las cédulas en Excel y el HTML autónomo exactamente como el sitio:
mismas hojas, mismas fórmulas, mismo motor portátil dentro del HTML.

**No se editan aquí.** Si hay que cambiarlos, se cambian en el sitio y se
vuelven a copiar:

```bash
cp <auditbrain-site>/lib/tools/{exports,domain,portable-engine,explanations,workbook-presentation,html-presentation,brand,example}.mjs frontend/src/aud/niif/sitio/tools/
cp <auditbrain-site>/lib/{methodology,requirement}.mjs frontend/src/aud/niif/sitio/
node src/aud/niif/sitio/manifiesto.mjs <commit-del-sitio>   # regenera MANIFIESTO.json
```

`sitio.test.js` compara cada archivo contra `MANIFIESTO.json`: una edición local
lo pone en rojo. No puede comprobar que la copia esté al día con el sitio (el
portal no ve ese repositorio), solo que nadie la tocó aquí.

`domain.mjs` es la autoridad del cálculo; el portal lo corre en el navegador y
lo contrasta contra el motor Python del backend (`contraste.js`), igual que el
sitio contrasta su Worker contra Pyodide.
