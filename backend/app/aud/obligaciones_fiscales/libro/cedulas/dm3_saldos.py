"""DM3 Revisión de saldos — tres cifras anuales, libros vs F-104.

A diferencia de DM4..DM7, aquí no hay tabla de 12 meses: cada bloque es UNA
sola cifra anual. El "según libros" es el movimiento ACUMULADO DEL AÑO de la
cuenta (la columna Total del resumen "Mayores homologados"), no el saldo al
cierre.

Tres bloques, cada uno con su propia cuenta y su propio casillero. El
casillero declarado se toma del MES DE CORTE (el último período presente), no
de diciembre: en un corte interino diciembre no existe y el declarado salía 0.

| Bloque              | Cuenta (parametrizable)  | Casillero declarado          |
|----------------------|--------------------------|-------------------------------|
| Crédito tributario    | 1.1.5.1.2 (por defecto)  | 615 + 617 del mes de corte    |
| IVA Diferido           | 2.1.7.4.2 (por defecto)  | 485 del mes de corte          |
| SRI por Pagar           | 2.1.7.5.6 (por defecto)  | 859 del mes de corte + reten-
                                                        ciones de renta del corte (DM7) |

Si el cliente no tiene alguna de esas cuentas en su mayor, el bloque igual
se escribe con 0: no se puede referenciar por fórmula una celda que no
existe, así que se deja el valor en 0 literal y una nota junto al bloque
para que el auditor sepa qué cuenta se esperaba encontrar.
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
    """El mes del ÚLTIMO período presente (el corte).

    Antes se comparaba siempre contra diciembre; en un corte interino (p. ej.
    agosto) ese casillero no existía y el "declarado" salía 0. El corte es el
    mes más alto de los períodos efectivamente cargados.
    """
    if not periodos:
        return None
    return max(periodos).split("-")[-1]


def _addr_casillero(dir_f104: dict, periodos: list[str], cas: str, mes: str | None = None):
    mes = mes or _mes_de_corte(periodos)
    if not mes:
        return None
    periodo = next((p for p in periodos if p.split("-")[-1] == mes), None)
    if not periodo:
        return None
    return dir_f104.get((periodo, cas))


def _bloque_saldo(
    ws,
    *,
    fila: int,
    titulo: str,
    codigo_cuenta: str,
    nombre_cuenta: str,
    addr_libros: str | None,
    formula_declarado: str,
    etiqueta_declarado: str,
) -> tuple[int, int, int]:
    """Escribe un bloque de una sola cifra anual.

    Devuelve ``(fila_siguiente, fila_libros, fila_declarado)``: las dos últimas
    para que el cruce global de DM3 pueda sumar los "según libros" y los "según
    declaraciones" de todos los bloques.

    ``addr_libros`` es la dirección (de la cédula sumaria DM2) del saldo al
    corte de la cuenta, para que DM3 cruce contra la MISMA cifra de la sumaria.
    """
    ws.cell(fila, COL_CODIGO, titulo).font = FONT_TITULO_CEDULA
    fila += 1

    for i, texto in enumerate(("Código", "Cuenta", "Valor US$")):
        estilo_encabezado_tabla(ws.cell(fila, COL_CODIGO + i, texto))
    fila += 1

    ws.cell(fila, COL_CODIGO, codigo_cuenta).font = FONT_DATA
    ws.cell(fila, COL_ETIQUETA, nombre_cuenta).font = FONT_DATA
    fila += 1

    if addr_libros:
        ws.cell(fila, COL_ETIQUETA,
               f"Nota: saldo al corte según la cédula sumaria (DM2) de la cuenta "
               f"{codigo_cuenta}").font = FONT_DATA
    else:
        c = ws.cell(fila, COL_ETIQUETA,
                   f"⚠ Nota: la cuenta {codigo_cuenta} no aparece en el mayor del "
                   "cliente; el auditor debe verificar si debía existir.")
        c.font = FONT_DATA
    fila += 1

    fila_libros = fila
    e = ws.cell(fila, COL_ETIQUETA, "Según libros (sumaria DM2)")
    e.font = FONT_TOTAL
    e.fill = RELLENO_TOTAL
    valor_libros = f"={addr_libros}" if addr_libros else 0
    v = ws.cell(fila, COL_VALOR, valor_libros)
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

    e = ws.cell(fila, COL_ETIQUETA, "Diferencia")
    e.font = FONT_TOTAL
    v = ws.cell(fila, COL_VALOR, f"=ROUND(C{fila_libros}-C{fila_declarado},2)")
    v.font = FONT_TOTAL
    v.number_format = FORMATO_NUM
    v.border = BORDE
    fila += 3

    return fila, fila_libros, fila_declarado


def build_dm3(
    wb,
    *,
    dir_mayores: dict,
    dir_f104: dict,
    dir_dm7: dict,
    dir_dm2: dict | None = None,
    periodos: list[str],
    cliente: str,
    periodo: str,
    cuenta_credito_tributario: str = "1.1.5.1.2",
    nombre_credito_tributario: str = "Crédito Tributario IVA",
    cuenta_iva_diferido: str = "2.1.7.4.2",
    nombre_iva_diferido: str = "IVA Diferido",
    cuenta_sri_por_pagar: str = "2.1.7.5.6",
    nombre_sri_por_pagar: str = "SRI por Pagar",
    preparado_por: str | None = None,
    revisado_por: str | None = None,
) -> dict[str, str]:
    """Construye DM3. No publica direcciones: nada la consume por fórmula.

    El "según libros" de cada saldo se toma de la cédula sumaria (DM2) por
    fórmula (``dir_dm2``), así DM3 cruza exactamente el mismo saldo al corte
    que la sumaria; el casillero declarado sale del F-104 del mes de corte.
    """
    if SHEET_DM3 in wb.sheetnames:
        del wb[SHEET_DM3]
    ws = wb.create_sheet(SHEET_DM3)

    escribir_encabezado_cedula(
        ws, titulo="Revisión de saldos", referencia="DM3",
        cliente=cliente, periodo=periodo,
        preparado_por=preparado_por, revisado_por=revisado_por,
    )

    fila = 12
    dir_dm2 = dir_dm2 or {}

    # El saldo al corte se compara contra el casillero del MES DE CORTE (el
    # último período presente), no contra diciembre: en un corte interino
    # diciembre no existe y el declarado salía 0.
    mes_corte = _mes_de_corte(periodos)
    etq_mes = f"(mes de corte {mes_corte})" if mes_corte else "(mes de corte)"

    # --- Bloque 1: Crédito tributario = 615 + 617 del mes de corte ---
    addr615 = _addr_casillero(dir_f104, periodos, "615")
    addr617 = _addr_casillero(dir_f104, periodos, "617")
    partes = [a for a in (addr615, addr617) if a]
    formula_credito = ("=" + "+".join(partes)) if partes else 0
    fila, fl_1, fd_1 = _bloque_saldo(
        ws, fila=fila, titulo="CREDITO TRIBUTARIO",
        codigo_cuenta=cuenta_credito_tributario, nombre_cuenta=nombre_credito_tributario,
        addr_libros=dir_dm2.get(("saldo_corte", cuenta_credito_tributario)),
        formula_declarado=formula_credito,
        etiqueta_declarado=f"Según F-104 casillero 615+617 {etq_mes}",
    )

    # --- Bloque 2: IVA Diferido = 485 del mes de corte ---
    addr485 = _addr_casillero(dir_f104, periodos, "485")
    formula_diferido = f"={addr485}" if addr485 else 0
    fila, fl_2, fd_2 = _bloque_saldo(
        ws, fila=fila, titulo="IVA DIFERIDO",
        codigo_cuenta=cuenta_iva_diferido, nombre_cuenta=nombre_iva_diferido,
        addr_libros=dir_dm2.get(("saldo_corte", cuenta_iva_diferido)),
        formula_declarado=formula_diferido,
        etiqueta_declarado=f"Según F-104 casillero 485 {etq_mes}",
    )

    # --- Bloque 3: SRI por Pagar = 859 del mes de corte + retenciones de renta
    # del mes de corte (DM7) ---
    addr859 = _addr_casillero(dir_f104, periodos, "859")
    addr_ret_renta_corte = dir_dm7.get(("ret_renta_declarado", mes_corte)) if mes_corte else None
    partes_sri = [a for a in (addr859, addr_ret_renta_corte) if a]
    formula_sri = ("=" + "+".join(partes_sri)) if partes_sri else 0
    fila, fl_3, fd_3 = _bloque_saldo(
        ws, fila=fila, titulo="PASIVO: SRI POR PAGAR",
        codigo_cuenta=cuenta_sri_por_pagar, nombre_cuenta=nombre_sri_por_pagar,
        addr_libros=dir_dm2.get(("saldo_corte", cuenta_sri_por_pagar)),
        formula_declarado=formula_sri,
        etiqueta_declarado=f"Según F-104 casillero 859 {etq_mes} + retenciones "
                            f"de renta del mes de corte (DM7)",
    )

    # --- Cruce global: el total de los saldos al corte de la sumaria (de las
    # cuentas probadas) contra el total declarado. Se suman las celdas puntuales
    # de cada bloque con SUM (celdas de la MISMA hoja), no con '+', para no
    # chocar con la regla de direcciones calificadas.
    ws.cell(fila, COL_CODIGO, "CRUCE GLOBAL").font = FONT_TITULO_CEDULA
    fila += 1
    filas_libros = (fl_1, fl_2, fl_3)
    filas_declarado = (fd_1, fd_2, fd_3)
    fila_glob_libros = fila
    e = ws.cell(fila, COL_ETIQUETA, "Total saldos al corte según libros (sumaria DM2)")
    e.font = FONT_TOTAL
    e.fill = RELLENO_TOTAL
    v = ws.cell(fila, COL_VALOR, "=SUM(" + ",".join(f"C{r}" for r in filas_libros) + ")")
    v.font = FONT_TOTAL
    v.fill = RELLENO_TOTAL
    v.number_format = FORMATO_NUM
    v.border = BORDE
    fila += 1
    fila_glob_declarado = fila
    e = ws.cell(fila, COL_ETIQUETA, "Total según declaraciones")
    e.font = FONT_TOTAL
    e.fill = RELLENO_TOTAL
    v = ws.cell(fila, COL_VALOR, "=SUM(" + ",".join(f"C{r}" for r in filas_declarado) + ")")
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
    ws.column_dimensions[get_column_letter(COL_VALOR)].width = 16

    return {}
