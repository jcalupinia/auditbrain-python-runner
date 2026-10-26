"""Transformador incremental del reporte de mayor por cuentas (MANACRIPEX).

El XLSX conserva filas de encabezado de cuenta, saldo inicial/final y total
general. El resultado CSV contiene exclusivamente movimientos, con cuenta
heredada de la seccion. Nunca agrega saldos a debe/haber.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook


def _numero(valor):
    if valor is None or str(valor).strip() == "":
        return Decimal("0")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    limpio = str(valor).strip().replace(" ", "")
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(",", "") if limpio.rfind(".") > limpio.rfind(",") else limpio.replace(".", "").replace(",", ".")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    try:
        return Decimal(limpio)
    except InvalidOperation as exc:
        raise ValueError("Importe contable invalido") from exc


def transformar_mayor_secciones(archivo, destino, *, hoja=None):
    """Devuelve conteos y sumas de control; streaming sobre workbook read_only.

    Reconoce encabezado de cuenta por 'Saldo Inicial--->' en columna 3,
    movimientos por fecha en columna 1 y totales por 'Totales  -------->'.
    No interpreta ni modifica registros desconocidos: los cuenta como excepciones.
    """
    wb = load_workbook(archivo, read_only=True, data_only=True)
    cuentas = set()
    movimientos = 0
    excepciones = 0
    debe = haber = Decimal("0")
    total_reportado = None
    cuenta_actual = None
    try:
        ws = wb[hoja] if hoja else wb.active
        with Path(destino).open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["cuenta", "fecha", "debe", "haber", "asiento", "comprobante", "referencia"])
            for row in ws.iter_rows(values_only=True):
                v = list(row) + [None] * max(0, 10 - len(row))
                a, b, c, d, e, f, g, h, i, j = v[:10]
                if str(c or "").strip().startswith("Saldo Inicial"):
                    cuenta_actual = str(a).strip() if a is not None else None
                    if not cuenta_actual:
                        excepciones += 1
                    else:
                        cuentas.add(cuenta_actual)
                    continue
                if str(g or "").strip().startswith("Totales"):
                    total_reportado = (_numero(h), _numero(i))
                    continue
                if str(a or "").strip().startswith("Saldo Final"):
                    continue
                # La primera columna de un asiento es una fecha genuina en el reporte.
                import datetime
                fecha = a if isinstance(a, (datetime.date, datetime.datetime)) else None
                if fecha is None and isinstance(a, str):
                    try:
                        fecha = datetime.date.fromisoformat(a.strip()[:10])
                    except ValueError:
                        pass
                if fecha is None:
                    continue
                if not cuenta_actual:
                    excepciones += 1
                    continue
                try:
                    monto_debe, monto_haber = _numero(g), _numero(h)
                except ValueError:
                    excepciones += 1
                    continue
                writer.writerow([cuenta_actual, fecha.isoformat()[:10], str(monto_debe),
                                 str(monto_haber), str(b or ""), str(c or ""), str(f or "")])
                movimientos += 1
                debe += monto_debe
                haber += monto_haber
    finally:
        wb.close()
    return {
        "cuentas": len(cuentas), "movimientos": movimientos,
        "debe": str(debe), "haber": str(haber),
        "total_reportado_debe": str(total_reportado[0]) if total_reportado else None,
        "total_reportado_haber": str(total_reportado[1]) if total_reportado else None,
        "cuadra_reporte": bool(total_reportado and (debe, haber) == total_reportado),
        "excepciones": excepciones,
    }
