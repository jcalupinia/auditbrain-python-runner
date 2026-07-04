"""Genera libros Excel sintéticos (números inventados) que imitan la estructura
de un EEFF resumido por nombre: ESF (4 períodos: parcial + 3 anuales) y ERI
(5 períodos: 2 parciales + 3 anuales), con tipos de cabecera MEZCLADOS y un
descuadre deliberado. NO contiene datos de clientes."""
from __future__ import annotations
import io
import datetime as dt
from openpyxl import Workbook


def libro_resumido_nombre() -> bytes:
    wb = Workbook(); ws = wb.active; ws.title = "Hoja1"
    filas = [
        ["ESTADO DE SITUACIÓN FINANCIERA RESUMIDO"],
        ["Activo", dt.datetime(2026, 5, 1), "2025", "2024", 2023],   # tipos mezclados a propósito
        ["Efectivo y equivalentes de efectivo", 100, 90, 80, 70],
        ["Cuentas por cobrar comerciales", 200, 150, 160, 170],
        ["Inventario", 300, 320, 250, 240],
        ["Total activos corrientes", 600, 560, 490, 480],
        ["Propiedades y equipo", 400, 410, 420, 430],
        ["TOTAL ACTIVOS", 1000, 970, 910, 910],
        ["Pasivo y patrimonio", dt.datetime(2026, 5, 1), "2025", "2024", 2023],
        ["Cuentas por pagar comerciales", 250, 240, 300, 400],
        ["Total pasivos", 250, 240, 300, 400],
        ["Capital", 500, 500, 500, 500],
        ["Resultado del ejercicio", 250, 231, 110, 10],  # 2025: 231 -> descuadre de 1 (970 vs 971)
        ["TOTAL PASIVO + PATRIMONIO", 1000, 971, 910, 910],
        [],
        ["ESTADO DE RESULTADO INTEGRAL RESUMIDO"],
        ["Concepto", dt.datetime(2026, 5, 1), dt.datetime(2025, 5, 1), "2025", "2024", 2023],
        ["Ingresos ordinarios", 500, 450, 1200, 1500, 1400],
        ["Costo de venta", -300, -280, -700, -900, -850],
        ["De administración, ventas y otros", -150, -120, -350, -400, -380],
        ["Participación trabajadores", 0, 0, -20, -30, -25],
        ["Impuesto a la renta", 0, 0, -30, -40, -35],
        ["Resultado del ejercicio", 50, 50, 100, 130, 110],
    ]
    for r in filas:
        ws.append(r)
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def libro_esf_pasivo_desordenado() -> bytes:
    """Igual que el resumido, pero el bloque 'Pasivo y patrimonio' trae sus
    columnas de período en ORDEN DISTINTO al bloque 'Activo'. Sirve para probar
    que los valores se asignan por LABEL de período, no por posición de columna.
    Activo:  [may-26, 2025, 2024, 2023]
    Pasivo:  [2023,   2024, 2025, may-26]  (invertido)
    """
    wb = Workbook(); ws = wb.active; ws.title = "Hoja1"
    filas = [
        ["ESTADO DE SITUACIÓN FINANCIERA RESUMIDO"],
        ["Activo", dt.datetime(2026, 5, 1), "2025", "2024", 2023],
        ["Efectivo y equivalentes de efectivo", 100, 90, 80, 70],
        ["TOTAL ACTIVOS", 100, 90, 80, 70],
        # Cabecera del bloque pasivo con las columnas INVERTIDAS:
        ["Pasivo y patrimonio", 2023, "2024", "2025", dt.datetime(2026, 5, 1)],
        # cxp: en 2023=1, 2024=2, 2025=3, may-26=4 (segun la cabecera invertida)
        ["Cuentas por pagar comerciales", 1, 2, 3, 4],
        ["Capital", 10, 20, 30, 40],
    ]
    for r in filas:
        ws.append(r)
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()
