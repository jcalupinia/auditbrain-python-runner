# -*- coding: utf-8 -*-
"""Juego de datos FICTICIO para la herramienta de nómina 2.0 («Comercial Andina de Ejemplo S.A.»).

NO contiene ningún dato de cliente real. Genera, en un directorio temporal, los cuatro
insumos mínimos que el motor exige (anexo RQ-002, Consolidado del IESS RQ-003, mayores RQ-004
y rol de pagos RQ-006) con la estructura EXACTA que leen ``motor.leer_consolidado``,
``motor.leer_rol_normal`` y ``mayores.cargar``. Sirve para probar el motor de punta a punta en
CI sin LibreOffice ni datos privados. Las cifras son triviales y consistentes; la prueba
verifica que las 15 cédulas se generan y abren sin reparaciones, no la paridad contable.
"""
from __future__ import annotations

import datetime
import os

import openpyxl

# 3 trabajadores ficticios (uno con salida a mitad de año → finiquito).
TRABAJADORES = [
    {"ced": "1700000011", "nombre": "ANDES VILLACIS MARIA FERNANDA", "sueldo": 1200.0, "salida_mes": None},
    {"ced": "1700000029", "nombre": "BAZANTES MORA LUIS ALBERTO", "sueldo": 900.0, "salida_mes": None},
    {"ced": "1700000037", "nombre": "CEVALLOS PROANO DIANA CAROLINA", "sueldo": 1500.0, "salida_mes": 6},
]
SBU = 460.0


def _rol(path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "normal"
    # Encabezado mínimo (el motor lee desde la fila 6; las 5 primeras son rótulos).
    for i in range(5):
        ws.append(["Rol de pagos (ejemplo ficticio)"])
    for t in TRABAJADORES:
        ing = datetime.date(2020, 1, 15)
        for mes in range(1, 13):
            if t["salida_mes"] and mes > t["salida_mes"]:
                continue
            fila = [0.0] * 67
            fila[0] = float(mes)
            fila[1] = t["nombre"]
            fila[2] = "Empleado"
            fila[3] = ing
            fila[4] = datetime.date(2025, t["salida_mes"], 28) if (t["salida_mes"] and mes == t["salida_mes"]) else None
            fila[5] = t["sueldo"]                 # SUELDO (gravado)
            fila[6] = 0.0                         # VAC TOMADAS
            fila[24] = round(t["sueldo"] * 0.0833, 2)  # FOND.RESERV. (desde el mes 13)
            fila[25] = 0.0                        # D13 mensualizado
            fila[26] = 0.0                        # D14 mensualizado
            if t["salida_mes"] and mes == t["salida_mes"]:
                fila[18] = round(t["sueldo"] / 24 * 15, 2)   # VAC.FINIQUIT
            if mes == 12:
                fila[63] = round(t["sueldo"], 2)             # prov. D13
                fila[64] = SBU                               # prov. D14
                fila[65] = round(t["sueldo"] / 24 * 15, 2)   # prov. vacaciones
                fila[66] = round(t["sueldo"] * 0.0833, 2)    # prov. fondo de reserva
            ws.append(fila)
    # Pestaña de pasantes vacía (con el encabezado «Total INGRESOS» que busca series.py).
    wp = wb.create_sheet("pasantes")
    wp.append(["Pasantes (ejemplo ficticio)"])
    wp.append(["Mes", "Nombre", "Total INGRESOS"])
    wb.save(path)


def _consolidado(path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "detallePlanillaConsolidado"
    ws.append(["Consolidado de planillas del IESS (ejemplo ficticio)"])
    ws.append(["", "Mes", "Cédula", "Nombre", "Relación", "Base", "Días",
               "Aporte patronal", "Aporte individual", "", "", "", "CCC", "Total"])
    for t in TRABAJADORES:
        for mes in range(1, 13):
            if t["salida_mes"] and mes > t["salida_mes"]:
                continue
            base = t["sueldo"]
            pat = round(base * 0.1115, 2)
            ind = round(base * 0.0945, 2)
            ccc = round(base * 0.005, 2)
            ws.append(["", float(mes), t["ced"], t["nombre"], "06", base, 30.0,
                       pat, ind, "", "", "", ccc, round(pat + ind + ccc, 2)])
    wb.save(path)


# Cuentas de gasto por concepto (nombre que lee `mayores.cuentas_por_concepto`).
_GASTO = [
    ("5.1.01.001", "Sueldos", lambda t: t["sueldo"] * 12),
    ("5.1.01.002", "Horas Extras", lambda t: 50.0),
    ("5.1.01.003", "Bono Desempeño", lambda t: 100.0),
    ("5.1.01.004", "Comisiones", lambda t: 80.0),
    ("5.1.01.005", "Premios", lambda t: 30.0),
    ("5.1.02.001", "Décimo Tercer Sueldo", lambda t: t["sueldo"]),
    ("5.1.02.002", "Décimo Cuarto Sueldo", lambda _t: SBU),
    ("5.1.02.003", "Vacaciones", lambda t: t["sueldo"] / 24 * 15),
    ("5.1.02.004", "Fondos de Reserva", lambda t: t["sueldo"] * 0.0833 * 12),
    ("5.1.03.001", "Aporte Patronal", lambda t: t["sueldo"] * 0.1115 * 12),
]


def _mayor(path: str, filas: list[dict]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fecha L/M", "Nºcuenta", "Descripción", "Importe", "Explicación -observación-",
               "REF", "Nombre alfa explicación"])
    for f in filas:
        ws.append([f.get("fecha"), f.get("cta"), f.get("desc"), f.get("importe"),
                   f.get("exp", ""), f.get("ref", ""), f.get("nae", "")])
    wb.save(path)


def _lm_gasto(path: str) -> None:
    filas = []
    fecha = datetime.datetime(2025, 6, 30)
    for cta, desc, fn in _GASTO:
        total = round(sum(fn(t) for t in TRABAJADORES), 2)
        filas.append({"fecha": fecha, "cta": cta, "desc": desc, "importe": total})
    _mayor(path, filas)


def _lm_iess(path: str) -> None:
    # 5BS.21203 (IESS por pagar). `REF` da la clase (PROVISION, PAGOS, FINIQUITOS); la
    # columna «Nombre alfa explicación» sub-clasifica los pagos (CANCELACION → PAGO IESS).
    filas = []
    for mes in range(1, 13):
        fecha = datetime.datetime(2025, mes, 28)
        # Provisión del aporte, fondo de reserva y préstamos (crédito = negativo).
        filas.append({"fecha": fecha, "cta": "5BS.21203.001", "desc": "Aporte patronal",
                      "importe": -600.0, "exp": "APORTE", "ref": "PROVISION"})
        filas.append({"fecha": fecha, "cta": "5BS.21203.004", "desc": "Fondos de reserva",
                      "importe": -250.0, "exp": "FR", "ref": "PROVISION"})
        # Pago al IESS del período anterior (débito = positivo), sub-clase PAGO IESS.
        if mes > 1:
            filas.append({"fecha": fecha, "cta": "5BS.21203.001", "desc": "Pago IESS",
                          "importe": 600.0, "exp": "PAGO", "ref": "PAGOS", "nae": "CANCELACION PLANILLA IESS"})
    _mayor(path, filas)


def _lm_bs(path: str) -> None:
    # 5BS.21204 (beneficios por pagar). La clase sale de la «Explicación».
    filas = []
    fecha = datetime.datetime(2025, 12, 31)
    for cta, exp in (("5BS.21204.001", "DECIMO 13"), ("5BS.21204.002", "DECIMO 14 S"),
                     ("5BS.21204.003", "VACACIONES"), ("5BS.21204.004", "DECIMO 13")):
        filas.append({"fecha": fecha, "cta": cta, "desc": exp, "importe": 300.0, "exp": exp})
    _mayor(path, filas)


def _anexo(path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(3):
        ws.append(["Anexo de nómina (ejemplo ficticio)"])
    # Fila con el casillero (col0 '5...'), saldo anterior (col2) y saldo actual (col5).
    for cta in ("5BS.21203.001", "5BS.21204.001", "5BS.21204.002", "5BS.21204.003", "5BS.21204.004"):
        ws.append([cta, "Pasivo laboral", 0.0, None, None, 500.0])
    wb.save(path)


def generar(destino: str) -> list[dict]:
    """Crea los insumos ficticios en ``destino`` y devuelve la lista ``archivos`` del resolver."""
    os.makedirs(destino, exist_ok=True)
    rutas = {
        "RQ-002": ("Anexo_Nomina.xlsx", _anexo),
        "RQ-003": ("Consolidado_IESS.xlsx", _consolidado),
        "RQ-006": ("Rol_de_Pagos.xlsx", _rol),
    }
    archivos = []
    for rq, (nombre, fn) in rutas.items():
        p = os.path.join(destino, nombre)
        fn(p)
        archivos.append({"requerimiento": rq, "componente": "", "nombre": nombre, "ruta": p})
    # RQ-004: tres mayores (gasto, IESS, beneficios), reconocidos por el nombre del archivo.
    for nombre, fn in (("LM_GASTO_NOMINA.xlsx", _lm_gasto), ("LM_PASIVO_IESS_POR_PAGAR.xlsx", _lm_iess),
                       ("LM_PASIVO_BENEFICIOS_SOCIALES.xlsx", _lm_bs)):
        p = os.path.join(destino, nombre)
        fn(p)
        archivos.append({"requerimiento": "RQ-004", "componente": "", "nombre": nombre, "ruta": p})
    return archivos


FICHA = {
    "client": "Comercial Andina de Ejemplo S.A.", "ruc": "1790000000001", "year": 2025,
    "cutoff": "2025-12-31", "visit": "Final", "preparer": "[auditor]", "reviewer": "[socio]",
    "framework": "NIIF para las PYMES", "firm": "AuditConsulting",
}
