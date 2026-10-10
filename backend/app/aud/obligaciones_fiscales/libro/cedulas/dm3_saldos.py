"""DM3 Revisión de saldos — saldos al corte de la sumaria vs lo declarado.

Cruza el SALDO AL CORTE que la cédula sumaria (DM2) calcula por categoría
contra lo declarado en los formularios, en cuatro bloques (decisión del dueño
2026-10-10):

| Bloque                         | Según libros (sumaria)        | Declarado            |
|--------------------------------|-------------------------------|----------------------|
| Crédito tributario (IVA compras)| categoría IVA_COMPRAS         | F-104 casillero 529  |
| IVA en ventas                   | categoría IVA_VENTAS          | F-104 casillero 429  |
| Retenciones activo              | categoría IVA_RETENIDO        | F-104 casillero 609  |
| Retenciones del pasivo          | RET_RENTA + RET_IVA           | F-104 799 + F-103 (399−352) |

El saldo al corte de la sumaria es NETO (débito − crédito): las categorías de
pasivo quedan con saldo negativo (acreedor) y las de activo positivo. Los
casilleros declarados son magnitudes positivas, así que la diferencia se toma
sobre el VALOR ABSOLUTO del saldo: ``ROUND(ABS(libros) − declarado, 2)``.

Al final, un CRUCE GLOBAL suma los saldos al corte de todas las categorías
probadas y los contrasta contra el total declarado.
"""

from __future__ import annotations

from openpyxl.utils import get_column_letter

from backend.app.aud.obligaciones_fiscales.libro.estilos import (
    BORDE, FONT_DATA, FONT_TITULO_CEDULA, FONT_TOTAL,
    FORMATO_NUM, RELLENO_TOTAL, escribir_encabezado_cedula, escribir_leyenda_marcas,
    estilo_encabezado_tabla,
)

SHEET_DM3 = "DM3 Revisión de saldos"

COL_CODIGO, COL_ETIQUETA, COL_VALOR = 1, 2, 3


def _mes_de_corte(periodos: list[str]) -> str | None:
    """El mes del ÚLTIMO período presente (el corte)."""
    if not periodos:
        return None
    return max(periodos).split("-")[-1]


def _addr_casillero(dir_datos: dict, periodos: list[str], cas: str):
    """Dirección del casillero del MES DE CORTE (último período presente)."""
    mes = _mes_de_corte(periodos)
    if not mes:
        return None
    periodo = next((p for p in periodos if p.split("-")[-1] == mes), None)
    if not periodo:
        return None
    return dir_datos.get((periodo, cas))


def _formula_declarado(terminos: list[tuple[str | None, str]]) -> str | int:
    """Arma la fórmula de "según declaración" de una lista de (dirección, signo).

    Un término sin dirección (casillero ausente) se omite. Si no queda ninguno,
    devuelve 0 literal.
    """
    partes: list[str] = []
    for addr, signo in terminos:
        if not addr:
            continue
        partes.append(f"{signo}{addr}" if partes or signo == "-" else addr)
    return ("=" + "".join(partes)) if partes else 0


def _bloque_categoria(
    ws,
    *,
    fila: int,
    titulo: str,
    nombre_cuenta: str,
    addrs_libros: list[str],
    formula_declarado: str | int,
    etiqueta_declarado: str,
) -> tuple[int, int, int]:
    """Escribe un bloque de categoría. Devuelve (fila_siguiente, fila_libros,
    fila_declarado) para el cruce global."""
    ws.cell(fila, COL_CODIGO, titulo).font = FONT_TITULO_CEDULA
    fila += 1

    estilo_encabezado_tabla(ws.cell(fila, COL_ETIQUETA, "Cuenta"), centro=False)
    estilo_encabezado_tabla(ws.cell(fila, COL_VALOR, "Valor US$"))
    fila += 1

    fila_libros = fila
    e = ws.cell(fila, COL_ETIQUETA, f"{nombre_cuenta} — saldo al corte (sumaria DM2)")
    e.font = FONT_TOTAL
    e.fill = RELLENO_TOTAL
    if addrs_libros:
        valor = ("=SUM(" + ",".join(addrs_libros) + ")"
                 if len(addrs_libros) > 1 else f"={addrs_libros[0]}")
    else:
        valor = 0
    v = ws.cell(fila, COL_VALOR, valor)
    v.font = FONT_TOTAL
    v.fill = RELLENO_TOTAL
    v.number_format = FORMATO_NUM
    v.border = BORDE
    fila += 1

    fila_declarado = fila
    e = ws.cell(fila, COL_ETIQUETA, etiqueta_declarado)
    e.font = FONT_DATA
    v = ws.cell(fila, COL_VALOR, formula_declarado)
    v.font = FONT_DATA
    v.number_format = FORMATO_NUM
    v.border = BORDE
    fila += 1

    # Diferencia sobre el valor ABSOLUTO del saldo (el saldo de pasivo es
    # acreedor/negativo; el casillero declarado es positivo).
    e = ws.cell(fila, COL_ETIQUETA, "Diferencia")
    e.font = FONT_TOTAL
    v = ws.cell(fila, COL_VALOR, f"=ROUND(ABS(C{fila_libros})-C{fila_declarado},2)")
    v.font = FONT_TOTAL
    v.number_format = FORMATO_NUM
    v.border = BORDE
    fila += 3

    return fila, fila_libros, fila_declarado


def build_dm3(
    wb,
    *,
    dir_f104: dict,
    dir_f103: dict | None = None,
    dir_dm2: dict | None = None,
    periodos: list[str],
    cliente: str,
    periodo: str,
    preparado_por: str | None = None,
    revisado_por: str | None = None,
    **_ignorados,
) -> dict[str, str]:
    """Construye DM3. No publica direcciones: nada la consume por fórmula.

    ``**_ignorados`` absorbe argumentos que el ensamblador aún pasa (p. ej.
    ``dir_mayores``, ``dir_dm7``) y que esta versión ya no necesita.
    """
    if SHEET_DM3 in wb.sheetnames:
        del wb[SHEET_DM3]
    ws = wb.create_sheet(SHEET_DM3)
    dir_dm2 = dir_dm2 or {}
    dir_f103 = dir_f103 or {}

    escribir_encabezado_cedula(
        ws, titulo="Revisión de saldos", referencia="DM3",
        cliente=cliente, periodo=periodo,
        preparado_por=preparado_por, revisado_por=revisado_por,
    )

    mes_corte = _mes_de_corte(periodos)
    etq = f"(mes de corte {mes_corte})" if mes_corte else "(mes de corte)"

    def saldo_cat(categoria: str) -> list[str]:
        addr = dir_dm2.get(("saldo_corte_categoria", categoria))
        return [addr] if addr else []

    fila = 12
    filas_libros: list[int] = []
    filas_declarado: list[int] = []

    def bloque(**kw):
        nonlocal fila
        fila, fl, fd = _bloque_categoria(ws, fila=fila, **kw)
        filas_libros.append(fl)
        filas_declarado.append(fd)

    # 1) Crédito tributario (IVA en compras) vs F-104 casillero 529.
    bloque(
        titulo="CRÉDITO TRIBUTARIO (IVA EN COMPRAS)", nombre_cuenta="IVA en compras",
        addrs_libros=saldo_cat("IVA_COMPRAS"),
        formula_declarado=_formula_declarado([(_addr_casillero(dir_f104, periodos, "529"), "+")]),
        etiqueta_declarado=f"Según F-104 casillero 529 {etq}",
    )

    # 2) IVA en ventas vs F-104 casillero 429.
    bloque(
        titulo="IVA EN VENTAS", nombre_cuenta="IVA en ventas",
        addrs_libros=saldo_cat("IVA_VENTAS"),
        formula_declarado=_formula_declarado([(_addr_casillero(dir_f104, periodos, "429"), "+")]),
        etiqueta_declarado=f"Según F-104 casillero 429 {etq}",
    )

    # 3) Retenciones activo (IVA retenido por clientes) vs F-104 casillero 609.
    bloque(
        titulo="RETENCIONES ACTIVO (IVA RETENIDO POR CLIENTES)",
        nombre_cuenta="IVA retenido por clientes",
        addrs_libros=saldo_cat("IVA_RETENIDO"),
        formula_declarado=_formula_declarado([(_addr_casillero(dir_f104, periodos, "609"), "+")]),
        etiqueta_declarado=f"Según F-104 casillero 609 {etq}",
    )

    # 4) Retenciones del pasivo (ret. fuente + IVA por pagar) vs F-104 799 +
    # F-103 (399 − 352).
    bloque(
        titulo="RETENCIONES DEL PASIVO", nombre_cuenta="Retención fuente e IVA por pagar",
        addrs_libros=saldo_cat("RET_RENTA") + saldo_cat("RET_IVA"),
        formula_declarado=_formula_declarado([
            (_addr_casillero(dir_f104, periodos, "799"), "+"),
            (_addr_casillero(dir_f103, periodos, "399"), "+"),
            (_addr_casillero(dir_f103, periodos, "352"), "-"),
        ]),
        etiqueta_declarado=f"Según F-104 casillero 799 + F-103 (399 − 352) {etq}",
    )

    # --- Cruce global: total de saldos al corte (sumaria) vs total declarado ---
    ws.cell(fila, COL_CODIGO, "CRUCE GLOBAL").font = FONT_TITULO_CEDULA
    fila += 1
    fila_glob_libros = fila
    e = ws.cell(fila, COL_ETIQUETA, "Total saldos al corte según libros (sumaria DM2)")
    e.font = FONT_TOTAL
    e.fill = RELLENO_TOTAL
    v = ws.cell(fila, COL_VALOR,
                "=SUM(" + ",".join(f"ABS(C{r})" for r in filas_libros) + ")")
    v.font = FONT_TOTAL
    v.fill = RELLENO_TOTAL
    v.number_format = FORMATO_NUM
    v.border = BORDE
    fila += 1
    fila_glob_declarado = fila
    e = ws.cell(fila, COL_ETIQUETA, "Total según declaraciones")
    e.font = FONT_TOTAL
    e.fill = RELLENO_TOTAL
    v = ws.cell(fila, COL_VALOR,
                "=SUM(" + ",".join(f"C{r}" for r in filas_declarado) + ")")
    v.font = FONT_TOTAL
    v.fill = RELLENO_TOTAL
    v.number_format = FORMATO_NUM
    v.border = BORDE
    fila += 1
    e = ws.cell(fila, COL_ETIQUETA, "Diferencia global")
    e.font = FONT_TOTAL
    v = ws.cell(fila, COL_VALOR, f"=ROUND(C{fila_glob_libros}-C{fila_glob_declarado},2)")
    v.font = FONT_TOTAL
    v.number_format = FORMATO_NUM
    v.border = BORDE
    fila += 3

    escribir_leyenda_marcas(ws, fila=fila)

    ws.column_dimensions[get_column_letter(COL_CODIGO)].width = 16
    ws.column_dimensions[get_column_letter(COL_ETIQUETA)].width = 60
    ws.column_dimensions[get_column_letter(COL_VALOR)].width = 18

    return {}
