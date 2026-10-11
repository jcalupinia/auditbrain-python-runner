# Patrón · Paquete de entrega a Claude Code para el Command Center

Complementa `../integracion-command-center.md` con la experiencia de nómina (M35, M38).

## Antes de armar el paquete (M38)
1. Inspeccionar el repositorio: herramienta existente del rubro (id, versión, alcance), `docs/niif/CONTRATO_PROCESADOR.md`,
   precedentes (`procesadores/artefacto_html.py` + `assets/*.tmpl.html`: artefacto HTML con motor propio al que se le
   inyectan ficha y logos).
2. Preguntar al socio: ¿reemplazar, convivir o extender? ¿el panel propio es la cara y los generadores el motor?
3. Inventariar con honestidad lo que falta: cédulas sin generador, dependencias de papeles del equipo, literales del
   cliente en el código, dependencias del contenedor (LibreOffice, pdftotext).

## Contenido del ZIP
- `00_ENCARGO_CLAUDE_CODE.md`: texto para pegar en Claude Code (decisiones del socio, paso 0 de lectura, plan previo
  con visto bueno, rama, motor, plantilla del panel, ficha y logos, verificación, PR sin merge).
- `01_ESPECIFICACION_CONEXION.md`: constantes del panel → placeholders, orden de ejecución del motor, lo que falta,
  verificación, archivos que se tocan, privacidad, fuera de alcance.
- `referencia/`: panel, generadores, cédulas, REGLAS y FLUJOS.
- `valores_control/`: JSON de cifras, `intermedios/*.csv`, inventario de literales.
- `DATOS_PRIVADOS_<CLIENTE>_NO_SUBIR_AL_REPO/`: solo para la aceptación local.

## Criterio de «listo» exigido a Claude Code
Paridad con los valores de control (tolerancia 0,01) con tabla esperado/obtenido/diferencia; recálculo LibreOffice con
0 errores y controles en OK; juego genérico sin cifras del cliente; Playwright del panel conectado con capturas; pruebas
automáticas con datos ficticios; PR en español contra `main`, **sin merge** (aprueba el socio).
