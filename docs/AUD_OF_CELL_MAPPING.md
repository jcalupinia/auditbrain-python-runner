# DM Obligaciones Fiscales — Mapeo de celdas

Documentación del mapeo de celdas en la plantilla `dm_obligaciones_fiscales.xlsx` para que el `excel_assembler.py` sepa dónde escribir cada dato extraído de los PDFs SRI.

## DM6 IVA (pestaña "DM6 IVA")

### Filas por mes
| Mes | Fila |
|---|---|
| Enero | 20 |
| Febrero | 21 |
| Marzo | 22 |
| Abril | 23 |
| Mayo | 24 |
| Junio | 25 |
| Julio | 26 |
| Agosto | 27 |
| Septiembre | 28 |
| Octubre | 29 |
| Noviembre | 30 |
| Diciembre | 31 |

### Columnas
| Col | Cell (Enero) | Contenido | Origen |
|---|---|---|---|
| A | A20 | Nombre del mes | Hardcoded en plantilla |
| B | B20 | Ventas tarifa diferente 0% libros | Linked a `'DM5 Ventas '!C19` — no tocar en M1 |
| **C** | **C20** | **Ventas netas tarifa 0% (c/ derecho)** | **De F-104 casillero 411** |
| **D** | **D20** | **Ventas netas tarifa 0% (s/ derecho)** | **De F-104 casillero 412** |
| **E** | **E20** | **Exportaciones de bienes y servicios** | **De F-104 casillero 421** |
| F | F20 | Tarifa 15% (12% antes) | Formula `=+B20` — no tocar |
| G | G20 | Tarifa IVA vigente | 0.15 — no tocar |
| H–S | H20:S20 | Formulas Excel | No tocar |

**Decisión M1:** Solo se escriben columnas **C, D, E** con casilleros del F-104. El resto queda como está en la plantilla.

## DM7 Retenciones x pagar (pestaña "DM7 Retenciones x pagar")

### Filas por mes
| Mes | Fila |
|---|---|
| Enero | 21 |
| Febrero | 22 |
| Marzo | 23 |
| Abril | 24 |
| Mayo | 25 |
| Junio | 26 |
| Julio | 27 |
| Agosto | 28 |
| Septiembre | 29 |
| Octubre | 30 |
| Noviembre | 31 |
| Diciembre | 32 |

### Columnas
| Col | Cell (Enero) | Contenido | Origen |
|---|---|---|---|
| A | A21 | Nombre del mes | Hardcoded |
| B | B21 | Retención 10% libros | Mayor de retenciones — **M1 deja vacío** |
| C | C21 | Retención 20% libros | Mayor — vacío en M1 |
| D | D21 | Retención 30% libros | Mayor — vacío en M1 |
| E | E21 | Retención 70% libros | Mayor — vacío en M1 |
| F | F21 | Retención 100% libros | Mayor — vacío en M1 |
| G | G21 | Total retenciones IVA libros | Formula `=SUM(B21:F21)` — no tocar |
| **H** | **H21** | **Retención 10% (casillero 721)** | **De F-103 casillero 721** |
| **I** | **I21** | **Retención 20% (casillero 723)** | **De F-103 casillero 723** |
| **J** | **J21** | **Retención 30% (casillero 725)** | **De F-103 casillero 725** |
| **K** | **K21** | **Retención 70% (casillero 729)** | **De F-103 casillero 729** |
| **L** | **L21** | **Retención 100% (casillero 731)** | **De F-103 casillero 731** |
| **M** | **M21** | **Retención 50% (casillero 727)** | **De F-103 casillero 727** |
| N | N21 | Total IVA retenido (casillero 799) | Formula `=SUM(H21:M21)` — no tocar |
| O–S | O21:S21 | Diferencias | Formulas Excel — no tocar |

**Decisión M1:** Se escriben columnas **H, I, J, K, L, M** con casilleros del F-103. Las diferencias las calcula Excel.

## Encabezado común

Todas las pestañas tienen encabezado en filas 4-10 con cliente, periodo, preparado por, revisado por, referencia.

| Celda | Contenido |
|---|---|
| A5 / B5 | Nombre del cliente |
| D5 | Período terminado (fecha) |
| A7 | Preparado por |
| A9 | Revisado por |

El `excel_assembler` actualiza estas celdas en todas las pestañas relevantes.

## Casilleros SRI relevantes

### F-103 (Retenciones en la fuente)
| Casillero | Descripción |
|---|---|
| 721 | Retención IVA 10% |
| 723 | Retención IVA 20% |
| 725 | Retención IVA 30% |
| 727 | Retención IVA 50% |
| 729 | Retención IVA 70% |
| 731 | Retención IVA 100% |
| 799 | Total IVA retenido |

### F-104 (IVA)
| Casillero | Descripción |
|---|---|
| 411 | Ventas netas tarifa 0% con derecho a crédito |
| 412 | Ventas netas tarifa 0% sin derecho a crédito |
| 419 | Ventas netas gravadas tarifa diferente de 0% |
| 421 | Exportaciones de bienes y servicios |
| 429 | IVA generado en ventas |
| 480 | Adquisiciones e importaciones |
| 499 | IVA crédito tributario |
| 529 | IVA por pagar |

## Referencias

- Spec: `docs/superpowers/specs/2026-05-26-aud-obligaciones-fiscales-design.md`
- Plan M1: `docs/superpowers/plans/2026-05-26-aud-obligaciones-fiscales-m1.md`
- Plantilla baked-in: `backend/app/aud/obligaciones_fiscales/templates/dm_obligaciones_fiscales.xlsx`
- Fixtures de tests: `tests/fixtures/obligaciones_fiscales/f103_enero.pdf`, `f104_enero.pdf`
