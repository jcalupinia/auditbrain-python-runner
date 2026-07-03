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
