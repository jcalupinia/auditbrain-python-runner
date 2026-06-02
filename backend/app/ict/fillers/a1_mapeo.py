"""Filler for MAPEO A1 sheet usando Balance Mapeado (casillero pre-asignado).

Metodología REPLICADA del anexo oficial ICT 2024 del SRI:

  - Cada casillero F-101 ocupa una o más filas (una por cada cuenta
    contable que mapea a él).
  - PRIMERA fila del casillero:
      A: número de casillero       B: nombre del casillero
      C: valor declarado F-101     D/E/F: primera cuenta del balance
      G: fórmula DIFERENCIA:
         · 1 sola cuenta  → "=F<row>-C<row>"
         · N cuentas      → "=SUM(F<row>:F<row+N-1>)-C<row>"
      H: observaciones (vacío)
  - FILAS SIGUIENTES del mismo casillero:
      Solo D/E/F (código, descripción, saldo de cada cuenta adicional).
      Cols A, B, C, G, H quedan en BLANCO — la fórmula G de la primera
      fila YA suma todo el rango.
  - Casilleros SIN cuentas en el balance: G = "=F<row>-C<row>" (apunta
    a su propia fila, donde F<row> está vacío → fórmula evaluará a
    -C<row>, evidenciando que falta el saldo contable).
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a1 import (
    A1_CASILLEROS_ORDERED,
    A1_FIRST_DATA_ROW,
    A1_HEADER_MAP,
    A1_SHEET,
)


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Wrapper local: delega al central que protege MergedCells + fórmulas
    y registra la escritura en el trace log para la hoja Trazabilidad."""
    from backend.app.ict.fillers.base import safe_set
    return safe_set(ws, cell_addr, value, anexo="A1",
                    origen="A1 Mapeo (F-101 + Balance Mapeado)")


def _safe_set_formula(ws, cell_addr: str, formula: str, *, casillero: str | None = None) -> bool:
    """Wrapper local para fórmulas DELIBERADAS (sobreescribe fórmulas
    viejas del template cuando es necesario, p. ej. =SUM(F13:F25)-C13).
    El parámetro casillero opcional permite registrar el casillero referenciado
    para la sección de COBERTURA del dashboard de VERIFICACIÓN."""
    from backend.app.ict.fillers.base import safe_set_formula
    return safe_set_formula(ws, cell_addr, formula, anexo="A1",
                            casillero=casillero,
                            origen="A1 Mapeo (fórmula referencial)")


class A1Filler:
    anexo_code = "A1"

    # Casilleros que marcan FIN de bloque mayor — después de ellos
    # se inserta una fila en blanco como separador visual.
    BLOQUE_BREAKS = {"361", "499", "550", "599", "698", "699", "1005", "6999", "7999"}
    # Casilleros que son TOTAL (formato negrita + borde doble)
    TOTAL_CASILLEROS = {"361", "449", "499", "550", "589", "599", "698", "699",
                        "1005", "1045", "6999", "7991", "7992", "7999"}

    # Casilleros que F-101 declara como (-) NEGATIVOS (deterioros, depreciaciones,
    # pérdidas, inventarios finales). Sus saldos en el balance del cliente vienen
    # con signo CONTABLE NEGATIVO mientras F-101 los expresa positivos. Para que
    # la fórmula de diferencia dé 0 al cuadrar usamos ABS() sobre el sumatorio.
    NEGATIVE_CASILLEROS = {
        "314", "317", "324", "327", "329",  # deterioros cuentas por cobrar
        "347",                                 # deterioro inventarios
        "384", "385", "386",                  # depreciación acumulada PPE
        "392", "393",                          # amortización acumulada intangibles
        "602",                                 # capital no pagado
        "612", "616",                          # pérdidas acumuladas / del ejercicio
        "7010", "7022", "7028", "7034",       # inventarios finales (restan en CoGS)
    }

    # Mapping de TOTAL → identificador de bloque para que F<row_total> tenga
    # fórmula SUM del rango del bloque que totaliza.
    # PRIMARIOS suman cuentas individuales; COMPUESTOS suman sub-totales.
    PRIMARY_TOTAL_BLOCKS = {
        "361": "ACT_CORR",      "449": "ACT_NO_CORR",
        "550": "PAS_CORR",      "589": "PAS_NO_CORR",
        "698": "PATRIMONIO",
        "1005": "ING_ORD",      "1045": "ING_NO_OP",
        "6999": "INGRESOS",
        "7991": "COSTOS_OP",    "7992": "GASTOS",
    }
    COMPOSITE_TOTALS = {
        # cas_total → (sub_total_1, sub_total_2)
        "499": ("361", "449"),
        "599": ("550", "589"),
        "699": ("599", "698"),
        "7999": ("7991", "7992"),
    }
    # En qué bloque empieza cada casillero PRIMARIO. Lookup directo por casillero
    # del primer casillero del bloque para resetear block_start_row.
    # IMPORTANTE: estos valores deben coincidir EXACTAMENTE con los primeros
    # casilleros de cada bloque en A1_CASILLEROS_ORDERED.
    BLOCK_FIRST_CAS = {
        "ACT_CORR":    "311",   "ACT_NO_CORR": "362",
        "PAS_CORR":    "511",   "PAS_NO_CORR": "555",   # 555 es el primero en cell_map
        "PATRIMONIO":  "601",
        "ING_ORD":     "6001",  "ING_NO_OP":   "6033",
        "INGRESOS":    "6001",
        "COSTOS_OP":   "7001",  "GASTOS":      "7173",
    }

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[A1_SHEET]
        filled = 0
        warnings: list[str] = []

        # ⚠ FIX BUG MERGED CELLS:
        # El template del SRI tiene merged cells PRE-DEFINIDAS en el rango de
        # datos (filas 13+) para algunos casilleros. Cuando el filler hace
        # `ws.insert_rows()` para cuentas extra de un casillero con múltiples
        # cuentas (ej. cas 311 con 7 bancos), todos los merges del template
        # se DESPLAZAN hacia abajo. Esto causa que safe_set() omita silenciosa-
        # mente la escritura de A/B/C en otros casilleros (cas 321, 322, 325,
        # 327, etc.) porque la celda destino quedó dentro de un rango merged
        # heredado del template. RESULTADO visible: el A1 muestra el número
        # del casillero (A) pero el nombre (B) y el valor (C) vacíos.
        #
        # SOLUCIÓN: un-merge TODOS los rangos por debajo del header. El filler
        # tendrá libertad total para escribir; el formatter al final crea las
        # merges DESEADAS (A:A, C:C por grupo de casillero).
        for mr in list(ws.merged_cells.ranges):
            if mr.min_row >= A1_FIRST_DATA_ROW:
                ws.unmerge_cells(str(mr))

        # Header
        for cell_addr, key in A1_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        f101 = anexo_data.get("f101", {})
        # balance_mapeado is a list of {casillero_sri, codigo, descripcion, saldo}
        balance_mapeado = anexo_data.get("balance_mapeado", [])

        # Lookups a las hojas DATOS — permiten que C y F sean FÓRMULAS
        # referenciales en vez de valores literales.
        f101_lookup: dict[str, int] = anexo_data.get("_f101_lookup", {}) or {}
        # balance_lookup[i] = row donde se escribió la cuenta i en DATOS BALANCE
        balance_lookup: list[int] = anexo_data.get("_balance_lookup", []) or []

        # Group balance items by casillero_sri + recordar su índice original
        # para poder generar la fórmula =DATOS BALANCE!D<row> correcta.
        by_casillero: dict[str, list[dict]] = {}
        for idx, item in enumerate(balance_mapeado):
            cas = str(item.get("casillero_sri", "")).strip()
            if cas:
                item_with_idx = dict(item)
                item_with_idx["_source_row"] = (
                    balance_lookup[idx] if idx < len(balance_lookup) else None
                )
                by_casillero.setdefault(cas, []).append(item_with_idx)

        # Tracking de grupos para formatting posterior
        casillero_groups: list[dict] = []
        current_row = A1_FIRST_DATA_ROW

        # Tracking de bloques para que los TOTALES tengan fórmulas =SUM correctas
        # en la columna F (saldos contables), igualando lo que pasa en C (declarado).
        # block_start_rows[bloque_id] = fila donde empieza el bloque
        # total_rows[casillero_total] = fila donde se escribió ese TOTAL
        block_start_rows: dict[str, int] = {}
        total_rows: dict[str, int] = {}

        for casillero, casillero_nombre in A1_CASILLEROS_ORDERED:
            valor_declarado = f101.get(casillero)
            matching = by_casillero.get(casillero, [])
            n_accounts = len(matching)
            is_total = casillero in self.TOTAL_CASILLEROS
            is_negative = casillero in self.NEGATIVE_CASILLEROS
            row_start = current_row

            # Detectar inicio de bloque (primer casillero de cada bloque PRIMARIO)
            for bloque_id, first_cas in self.BLOCK_FIRST_CAS.items():
                if casillero == first_cas and bloque_id not in block_start_rows:
                    block_start_rows[bloque_id] = current_row

            # === Casillero + nombre (cols A, B) ===
            if _safe_set(ws, f"A{current_row}", casillero):
                filled += 1
            if _safe_set(ws, f"B{current_row}", casillero_nombre):
                filled += 1

            # === C — Valor declarado (REFERENCIA a 'DATOS F-101' o fórmula compuesta) ===
            if is_total and casillero in self.COMPOSITE_TOTALS:
                sub1, sub2 = self.COMPOSITE_TOTALS[casillero]
                if sub1 in total_rows and sub2 in total_rows:
                    _safe_set_formula(ws, f"C{current_row}",
                                      f"=C{total_rows[sub1]}+C{total_rows[sub2]}")
                    filled += 1
                elif casillero in f101_lookup:
                    # Si no hay subtotales, referenciar DATOS F-101
                    _safe_set_formula(
                        ws, f"C{current_row}",
                        f"='DATOS F-101'!C{f101_lookup[casillero]}",
                    )
                    filled += 1
                elif valor_declarado is not None:
                    if _safe_set(ws, f"C{current_row}", valor_declarado): filled += 1
            elif casillero in f101_lookup:
                # Caso típico: referenciar la celda de DATOS F-101 → trazabilidad
                _safe_set_formula(
                    ws, f"C{current_row}",
                    f"='DATOS F-101'!C{f101_lookup[casillero]}",
                    casillero=casillero,
                )
                filled += 1
            elif valor_declarado is not None:
                # Fallback: si el casillero no está en F-101 lookup (raro), escribir literal
                if _safe_set(ws, f"C{current_row}", valor_declarado): filled += 1
            else:
                if not is_total:
                    warnings.append(f"Casillero {casillero} no encontrado en F-101")

            # === F (saldos contables) — fórmula SUM si es TOTAL ===
            f_formula_for_total = None
            if is_total:
                if casillero in self.PRIMARY_TOTAL_BLOCKS:
                    # TOTAL primario: suma del rango del bloque actual
                    bloque_id = self.PRIMARY_TOTAL_BLOCKS[casillero]
                    if bloque_id in block_start_rows:
                        f_formula_for_total = (
                            f"=SUM(F{block_start_rows[bloque_id]}:F{current_row-1})"
                        )
                        # Reset del bloque para que el siguiente bloque arranque limpio
                        del block_start_rows[bloque_id]
                elif casillero in self.COMPOSITE_TOTALS:
                    # TOTAL compuesto: suma de los sub-totales previos
                    sub1, sub2 = self.COMPOSITE_TOTALS[casillero]
                    if sub1 in total_rows and sub2 in total_rows:
                        f_formula_for_total = (
                            f"=F{total_rows[sub1]}+F{total_rows[sub2]}"
                        )

                if f_formula_for_total:
                    _safe_set_formula(ws, f"F{current_row}", f_formula_for_total)
                    filled += 1
                total_rows[casillero] = current_row

            if n_accounts == 0:
                # Sin cuentas contables.
                # Para TOTAL con fórmula F, su diferencia G = F - C automáticamente.
                # Para casillero normal sin cuentas, G también es F - C (apunta a sí mismo).
                # IMPORTANTE: NO usar ABS aquí para totales (sus saldos son sumas con signo)
                if is_negative:
                    _safe_set_formula(ws, f"G{current_row}", f"=ABS(F{current_row})-C{current_row}")
                else:
                    _safe_set_formula(ws, f"G{current_row}", f"=F{current_row}-C{current_row}")

                if (not is_total and valor_declarado is not None and
                    valor_declarado != 0):
                    warnings.append(
                        f"Casillero {casillero} ({casillero_nombre}): declarado "
                        f"{valor_declarado:,.2f} pero el Balance Mapeado no aporta "
                        f"cuentas contables — diferencia será -{valor_declarado:,.2f}"
                    )
                # Trackear grupo (1 fila)
                casillero_groups.append({
                    "casillero": casillero, "row_start": row_start,
                    "row_end": current_row, "is_total": is_total,
                })
                current_row += 1
                # Separador después de bloques mayores
                if casillero in self.BLOQUE_BREAKS:
                    current_row += 1  # fila en blanco
                continue

            # === Primera fila: primera cuenta en D/E/F + fórmula G en SUM range ===
            first = matching[0]
            if _safe_set(ws, f"D{current_row}", first.get("codigo", "")): filled += 1
            if _safe_set(ws, f"E{current_row}", first.get("descripcion", "")): filled += 1
            # F = REFERENCIA a 'DATOS BALANCE'!D<row_idx> para que el auditor
            # vea de qué cuenta exacta proviene el saldo. Fallback a literal si
            # no hay lookup (caso edge).
            src_row = first.get("_source_row")
            if src_row:
                _safe_set_formula(ws, f"F{current_row}",
                                  f"='DATOS BALANCE'!D{src_row}")
                filled += 1
            elif _safe_set(ws, f"F{current_row}", first.get("saldo", 0)):
                filled += 1

            # Fórmula G — metodología oficial 2024:
            #   N cuentas → "=SUM(F<row>:F<row+N-1>)-C<row>"
            #   1 cuenta  → "=F<row>-C<row>"
            # Si el casillero es NEGATIVO en F-101, envolvemos en ABS() para que
            # los saldos negativos del balance den cuadre 0 contra el declarado positivo.
            if n_accounts > 1:
                end_row = current_row + n_accounts - 1
                if is_negative:
                    formula = f"=ABS(SUM(F{current_row}:F{end_row}))-C{current_row}"
                else:
                    formula = f"=SUM(F{current_row}:F{end_row})-C{current_row}"
            else:
                if is_negative:
                    formula = f"=ABS(F{current_row})-C{current_row}"
                else:
                    formula = f"=F{current_row}-C{current_row}"
            _safe_set_formula(ws, f"G{current_row}", formula)

            # === Filas adicionales: cuentas extra del mismo casillero ===
            # Sólo D/E/F. NO se pone fórmula en G (queda en blanco) porque la
            # fórmula SUM de la primera fila YA suma todo este rango.
            # F referencia 'DATOS BALANCE'!D<row_src> (trazabilidad).
            for offset, item in enumerate(matching[1:], start=1):
                row_n = current_row + offset
                ws.insert_rows(row_n)
                if _safe_set(ws, f"D{row_n}", item.get("codigo", "")): filled += 1
                if _safe_set(ws, f"E{row_n}", item.get("descripcion", "")): filled += 1
                src_row = item.get("_source_row")
                if src_row:
                    _safe_set_formula(ws, f"F{row_n}",
                                      f"='DATOS BALANCE'!D{src_row}")
                    filled += 1
                elif _safe_set(ws, f"F{row_n}", item.get("saldo", 0)):
                    filled += 1

            # Trackear grupo (N filas)
            casillero_groups.append({
                "casillero": casillero,
                "row_start": row_start,
                "row_end": current_row + n_accounts - 1,
                "is_total": is_total,
            })

            current_row += n_accounts
            # Separador después de bloques mayores
            if casillero in self.BLOQUE_BREAKS:
                current_row += 1  # fila en blanco entre bloques

        # === Reporte de cobertura para warnings ===
        casilleros_a1_set = {c for c, _ in A1_CASILLEROS_ORDERED}

        # Casilleros del balance que NO aparecen en el A1 (quedan disponibles
        # para otros anexos via shared_context, pero son útiles de listar):
        extra_casilleros = set(by_casillero.keys()) - casilleros_a1_set
        if extra_casilleros:
            cuentas_huerfanas = sum(len(by_casillero[c]) for c in extra_casilleros)
            warnings.append(
                f"Balance Mapeado: {len(extra_casilleros)} casilleros con "
                f"{cuentas_huerfanas} cuentas NO mapean al A1 (se trasladan a "
                f"A2-A9 vía shared_context): {sorted(extra_casilleros)[:10]}"
                f"{'...' if len(extra_casilleros) > 10 else ''}"
            )

        # === REGLA RUNTIME: cada TOTAL DEBE tener fórmula en F y valor en C ===
        # Si esta validación falla, significa que en algún punto el filler
        # NO escribió la fórmula SUM en F<row_total> o no recibió el valor
        # declarado en C, y la VERIFICACIÓN A1 saldrá con columnas vacías
        # (el bug que reportó el usuario). Esto NO falla el job — sólo
        # agrega warnings explícitos al output para que el auditor sepa.
        # El test en tests/test_ict_a1_totales_regla.py es la guardia
        # estática que evita la regresión en CI.
        totales_sin_F = []
        totales_sin_C = []
        for grp in casillero_groups:
            cas = grp["casillero"]
            if not grp.get("is_total"):
                continue
            r = grp["row_start"]
            f_val = ws[f"F{r}"].value
            if not (isinstance(f_val, str) and f_val.startswith("=")):
                totales_sin_F.append(f"cas {cas} (fila {r})")
            c_val = ws[f"C{r}"].value
            if c_val is None or c_val == "":
                totales_sin_C.append(f"cas {cas} (fila {r})")

        if totales_sin_F:
            warnings.append(
                f"⚠ REGLA TOTAL: {len(totales_sin_F)} casilleros TOTAL sin "
                f"fórmula SUM en F (saldo contable): {totales_sin_F}. "
                f"Revisar PRIMARY_TOTAL_BLOCKS y COMPOSITE_TOTALS en "
                f"a1_mapeo.py."
            )
        if totales_sin_C:
            warnings.append(
                f"⚠ REGLA TOTAL: {len(totales_sin_C)} casilleros TOTAL sin "
                f"valor en C (declarado F-101): {totales_sin_C}. "
                f"El F-101 del cliente no declaró estos totales o el parser "
                f"f101_pdf.py los está perdiendo."
            )

        # === Aplicar formato profesional al A1 ===
        # REGLA (CLAUDE.md): los anexos del ICT deben verse correctamente
        # presentados, equivalentes al formato oficial del SRI Ecuador.
        try:
            from backend.app.ict.fillers.formatting import format_a1_sheet
            format_a1_sheet(ws, casillero_groups=casillero_groups,
                            first_data_row=A1_FIRST_DATA_ROW)
        except Exception:
            import logging
            logging.exception("format_a1_sheet falló")

        return {"filled_cells": filled, "warnings": warnings}
