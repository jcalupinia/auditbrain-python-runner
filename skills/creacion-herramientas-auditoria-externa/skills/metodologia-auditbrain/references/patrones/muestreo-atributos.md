# Patrón · Muestreo de atributos con partidas clave y selección sistemática

Usar solo cuando la prueba no puede cubrir el 100 % (documentos físicos: solicitudes firmadas, contratos). El resto de
pruebas cubre la población completa.

## Libro (generador tipo `mk_rq007.py`)
- **Ficha**: % de muestra (por defecto 10 %), n.º de partidas clave, arranque (editable, azul).
- **Población**: sale por fórmula de la prueba de origen (no se pega); orden por importe con `RANK` + `COUNTIF` para
  desempatar.
- **Parámetros**: n = `ROUNDUP(N × %, 0)`; clave = las k mayores; intervalo = (N − k) / (n − k);
  posiciones sistemáticas = `ROUND(arranque + (i−1) × intervalo, 0)` sobre la población sin las clave.
- **Muestra**: el auditor marca Sí / No / N/A por atributo (celdas azules con validación de lista).
- **Conclusión** por fórmula: PENDIENTE (faltan marcas) · CONFORME · CON EXCEPCIONES → genera hallazgo en la hoja final y
  recomienda ampliar la muestra.

## Control de ejemplo (nómina, solicitudes de acumulación de décimos)
N = 147, 10 % → n = 15; 5 clave; 10 sistemáticas; arranque 2; intervalo 14,20; posiciones 2, 16, 30, 45, 59, 73, 87,
101, 116, 130. Una sola muestra cubre los dos atributos (D13 y D14; D14 = N/A si no acumula).
