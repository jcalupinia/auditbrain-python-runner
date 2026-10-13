# -*- coding: utf-8 -*-
"""Genera los ejemplos «formato válido con datos FICTICIOS» de la herramienta de nómina 2.0
(``nomina_beneficios``) en ``frontend/public/ejemplos/nomina_beneficios/``.

Son un cliente sintético COHERENTE (empresa «Comercial Andina de Ejemplo S.A.», RUC ficticio):
el motor (`correr_prueba`) los procesa de punta a punta y entrega las 15 cédulas. NINGÚN dato de
cliente real (regla M34/M35): nombres, cédulas e importes son inventados.

Cubre los requerimientos que lee el motor:
  RQ-002 anexo de saldos por cuenta · RQ-003 Consolidado IESS (hoja detallePlanillaConsolidado)
  + Exclusiones · RQ-004 tres mayores (gasto, IESS por pagar, beneficios por pagar) · RQ-006 rol
  (hojas «normal» y «pasantes») · RQ-007 muestreo de décimos (modelo) · RQ-008 kárdex (modelo).
RQ-005 (comprobantes PDF del IESS) no se puede falsificar de forma útil: se entrega un ZIP con un
aviso; el motor degrada DO-9 sin comprobantes (no es obligatorio, `datos_minimos`).

Ejecutar:  python scripts/ejemplos_nomina_beneficios.py
"""
import datetime
import os
import zipfile

import openpyxl

SBU = 470.0
EJ = 2025
DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "ejemplos", "nomina_beneficios")
DIR = os.path.abspath(DIR)

# --- Empleados ficticios (relación 06 = Código del Trabajo) -------------------
# (cédula, nombre, sueldo mensual, ingreso, salida)
EMP = [
    ("1700000001", "ANDRADE LOPEZ MARIA FERNANDA", 1200.0, datetime.date(2019, 3, 1), None),
    ("1700000002", "BENAVIDES TORRES CARLOS LUIS", 900.0, datetime.date(2021, 6, 15), None),
    ("1700000003", "CEVALLOS RUIZ ANA PATRICIA", 750.0, datetime.date(2020, 1, 10), None),
    ("1700000004", "DELGADO MORA JUAN ANDRES", 600.0, datetime.date(2023, 9, 1), None),
    ("1700000005", "ESPINOZA VERA LUCIA ELENA", 550.0, datetime.date(2024, 2, 1), datetime.date(2025, 11, 30)),
]
JUB = [("1700000006", "FLORES JARAMILLO PEDRO JOSE", 300.0)]  # jubilado (pensión patronal, fuera del cruce IESS)
PAS = [("1700000007", "GUERRERO SILVA SOFIA MARIA", 200.0)]   # pasante (estipendio, aporte 100% empresa)

TASA_PAT = 0.1215   # aporte patronal (empleados)
TASA_IND = 0.0945   # aporte individual
TASA_CCC = 0.005    # CCC (IECE/SECAP aprox.)
PCT_FR = 0.0833


def _meses_activo(ingreso, salida, mes):
    """¿El empleado está activo ese mes del ejercicio?"""
    if ingreso and ingreso > datetime.date(EJ, mes, 28):
        return False
    if salida and salida < datetime.date(EJ, mes, 1):
        return False
    return True


# --- RQ-006 rol (hojas «normal» y «pasantes») --------------------------------
def rol():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "normal"
    # Encabezados en la fila 5 (los datos arrancan en la fila 6, como el rol real).
    hdr = [""] * 67
    hdr[0] = "Mes"; hdr[1] = "Nombre"; hdr[2] = "Cargo"; hdr[3] = "Ingreso"; hdr[4] = "Salida"
    hdr[5] = "Sueldo"; hdr[6] = "Vac. tomadas"; hdr[24] = "Fondo reserva"; hdr[25] = "D13 mens"
    hdr[26] = "D14 mens"; hdr[18] = "Vac. finiquito"; hdr[63] = "Prov D13"; hdr[64] = "Prov D14"
    hdr[65] = "Prov Vac"; hdr[66] = "Prov FR"
    ws.append([None])  # fila 1
    ws.append([None]); ws.append([None]); ws.append([None])  # filas 2-4
    ws.append(hdr)  # fila 5
    for mes in range(1, 13):
        for idx, (ced, nom, sue, ing, sal) in enumerate(EMP):
            if not _meses_activo(ing, sal, mes):
                continue
            # Los dos primeros ACUMULAN los décimos (d13/d14 mensualizados = 0): forman la
            # población de acumulación (DO-4 V08) que verifica el muestreo. El resto mensualiza.
            acumula = idx < 2
            base = sue
            antiguo = ing and (datetime.date(EJ, mes, 1) - ing).days > 365
            row = [0.0] * 67
            row[0] = mes; row[1] = nom; row[2] = "EMPLEADO"
            row[3] = datetime.datetime(ing.year, ing.month, ing.day) if ing else None
            row[4] = datetime.datetime(sal.year, sal.month, sal.day) if (sal and sal.month == mes and sal.year == EJ) else None
            row[5] = sue
            row[24] = round(base * PCT_FR, 2) if antiguo else 0.0   # FR en rol (mensualizado)
            row[25] = 0.0 if acumula else round(base / 12, 2)   # D13 mensualizado (0 = acumula)
            row[26] = 0.0 if acumula else round(SBU / 12, 2)    # D14 mensualizado (0 = acumula)
            row[63] = round(base / 12, 2)   # provisión D13
            row[64] = round(SBU / 12, 2)    # provisión D14
            row[65] = round(base / 24, 2)   # provisión vacaciones
            row[66] = round(base * PCT_FR, 2) if antiguo else 0.0   # provisión FR
            if sal and sal.month == mes and sal.year == EJ:
                row[18] = round(base / 24 * 2, 2)  # vac. finiquito (pago de no gozadas a la salida)
            ws.append(row)
        # jubilado: pensión en col 21
        for ced, nom, pen in JUB:
            row = [0.0] * 67
            row[0] = mes; row[1] = nom; row[2] = "JUBILADO PATRONAL"; row[5] = 0.0
            row[21] = pen
            ws.append(row)
    # hoja pasantes
    wp = wb.create_sheet("pasantes")
    wp.append([None])  # fila 1
    wp.append(["Mes", "Nombre", "Total INGRESOS"])  # fila 2 (encabezado)
    for mes in range(1, 13):
        for ced, nom, est in PAS:
            wp.append([mes, nom, est])
    wb.save(os.path.join(DIR, "RQ-006_rol_de_pagos_normal_y_pasantes.xlsx"))


# --- RQ-003 Consolidado IESS (hoja detallePlanillaConsolidado) ---------------
def consolidado():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "detallePlanillaConsolidado"
    ws.append([None])  # fila 1
    ws.append([None, "Mes", "Cédula", "Nombre", "Relación", "Base", "Días", "Patronal",
               "Individual", None, None, None, "CCC", "Total"])  # fila 2 (encabezado)
    for mes in range(1, 13):
        for ced, nom, sue, ing, sal in EMP:
            if not _meses_activo(ing, sal, mes):
                continue
            base = sue
            pat = round(base * TASA_PAT, 2); ind = round(base * TASA_IND, 2)
            ccc = round(base * TASA_CCC, 2); tot = round(pat + ind + ccc, 2)
            ws.append([None, mes, ced, nom, "06", base, 30, pat, ind, None, None, None, ccc, tot])
        for ced, nom, est in PAS:   # pasante: aporte patronal 100% empresa sobre SBU
            pat = round(SBU * 0.176, 2)
            ws.append([None, mes, ced, nom, "16", SBU, 30, pat, 0.0, None, None, None, 0.0, pat])
    # hoja de exclusiones (opcional): vacía con encabezado
    we = wb.create_sheet("Exclusiones")
    for _ in range(4):
        we.append([None])
    we.append(["N°", "Cédula", "Nombre", "D13", "D14", "Vac", "FR", "Motivo"])  # fila 5
    we.append([None, "(opcional)", "(copie de la hoja «Nombres del IESS»)", None, None, None, None, None])
    wb.save(os.path.join(DIR, "RQ-003_consolidado_iess_por_region_y_exclusiones.xlsx"))


# --- RQ-004 mayores (gasto, IESS por pagar, beneficios por pagar) ------------
# Columnas unificadas (las que leen _load, mk_do9 y cargar): Fecha L/M, Nºcuenta, Descripción,
# Importe, Explicación -observación- (concepto del mayor de beneficios), Nombre alfa explicación
# (categoría del mayor IESS: «CANCELACION» = pago), REF (clase del mayor IESS: PROVISION/PAGOS).
_COLS = ["Fecha L/M", "Nºcuenta", "Descripción", "Importe", "Explicación -observación-",
         "Nombre alfa explicación", "REF"]


def _mayor(filas, nombre):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(_COLS)
    for f in filas:
        ws.append(f)
    wb.save(os.path.join(DIR, nombre))


def mayores():
    base_mes = sum(e[2] for e in EMP)
    pat_m = round(base_mes * TASA_PAT, 2); ind_m = round(base_mes * TASA_IND, 2)
    fr_m = round(base_mes * PCT_FR, 2)
    # Gasto de nómina: una fila por concepto y mes (concepto = Descripción, vía GKEY).
    GAS = [
        ("5PYG.51010.001", "Sueldos", base_mes),
        ("5PYG.51020.001", "Horas Extras", round(base_mes * 0.05, 2)),
        ("5PYG.51030.001", "Aporte Patronal", pat_m),
        ("5PYG.51040.001", "Décimo Tercer Sueldo", round(base_mes / 12, 2)),
        ("5PYG.51050.001", "Décimo Cuarto Sueldo", round(SBU * len(EMP) / 12, 2)),
        ("5PYG.51060.001", "Fondos de Reserva", fr_m),
        # Vacaciones en dos centros de costo (la prorrata del ajuste DO-12 necesita ≥2 cuentas).
        ("5PYG.51070.001", "Vacaciones", round(base_mes / 24 * 0.6, 2)),
        ("5PYG.51070.002", "Vacaciones", round(base_mes / 24 * 0.4, 2)),
        ("5PYG.51080.001", "Bono Desempeño", 50.0),
        ("5PYG.51090.001", "Comisiones", 40.0),
        ("5PYG.51100.001", "Premios", 20.0),
        ("5PYG.51110.001", "Estipendio Pasantes", PAS[0][2]),
        ("5PYG.51120.001", "Aporte Patronal Pasantes", round(SBU * 0.176, 2)),
    ]
    fg = []
    for mes in range(1, 13):
        fecha = datetime.datetime(EJ, mes, 28)
        for cta, desc, imp in GAS:
            fg.append([fecha, cta, desc, imp, desc, desc, "GASTO"])
    _mayor(fg, "RQ-004_mayor_de_gasto_de_nomina.xlsx")

    # IESS por pagar: provisión (crédito, importe negativo, REF=PROVISION) y pago del IESS
    # (débito, importe positivo, REF=PAGOS, «CANCELACION» = PAGO IESS en mk_do9).
    IE = [("5BS.21203.001", "Aporte patronal por pagar", pat_m),
          ("5BS.21203.002", "Aporte individual por pagar", ind_m),
          ("5BS.21203.004", "Fondos de reserva por pagar", fr_m)]
    fi = []
    for mes in range(1, 13):
        fecha = datetime.datetime(EJ, mes, 28)
        for cta, desc, imp in IE:
            fi.append([fecha, cta, desc, -imp, desc, desc, "PROVISION"])          # provisión del mes
            fi.append([fecha, cta, desc, imp, desc, "CANCELACION PLANILLA", "PAGOS"])  # pago al IESS
    _mayor(fi, "RQ-004_mayor_de_iess_por_pagar.xlsx")

    # Beneficios sociales por pagar (D13/D14/vacaciones: provisión, transferencias y goces).
    # El concepto va en «Explicación -observación-» (mapeado por _cat_bs a PROVISION/PAGOS/GOCES).
    BS = [("5BS.21204.001", round(base_mes / 12, 2), "DECIMO 13"),
          ("5BS.21204.002", round(SBU * len(EMP) / 12, 2), "DECIMO 14 S"),
          ("5BS.21204.003", round(base_mes / 24, 2), "VACACIONES"),
          ("5BS.21204.001", round(base_mes / 12, 2), "TRANSF DECIMO 13"),
          ("5BS.21204.003", round(base_mes / 48, 2), "VAC TOMADAS")]
    fb = []
    for mes in range(1, 13):
        fecha = datetime.datetime(EJ, mes, 28)
        for cta, imp, concepto in BS:
            signo = -1 if concepto in ("DECIMO 13", "DECIMO 14 S", "VACACIONES") else 1
            fb.append([fecha, cta, concepto, round(signo * imp, 2), concepto, concepto, "BS"])
    _mayor(fb, "RQ-004_mayor_de_beneficios_sociales_por_pagar.xlsx")


# --- RQ-002 anexo de saldos por cuenta (header=None, datos desde la fila 4) ---
def anexo():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Anexo"
    base_mes = sum(e[2] for e in EMP)
    # Filas 1-3: título/encabezado (el motor lee desde iloc[3:], o sea la fila 4).
    ws.append(["Anexo de nómina — saldos por cuenta (ejemplo ficticio)"])
    ws.append(["Comercial Andina de Ejemplo S.A."])
    ws.append(["Cuenta", "Descripción", "Saldo 2024", None, None, "Saldo 2025"])
    # cuenta(col0) · desc(col1) · saldo24(col2) · ... · saldo25(col5)
    CTAS = [
        ("5BS.21203.001", "Aporte patronal por pagar", round(base_mes * TASA_PAT, 2)),
        ("5BS.21203.002", "Aporte individual por pagar", round(base_mes * TASA_IND, 2)),
        ("5BS.21203.003", "Préstamos quirografarios por pagar", 120.0),
        ("5BS.21203.004", "Fondos de reserva por pagar", round(base_mes * PCT_FR, 2)),
        ("5BS.21203.005", "Préstamos hipotecarios por pagar", 80.0),
        ("5BS.21204.001", "Décimo tercer sueldo por pagar", round(base_mes / 12, 2)),
        ("5BS.21204.002", "Décimo cuarto sueldo por pagar", round(SBU * len(EMP) / 12, 2)),
        ("5BS.21204.003", "Vacaciones por pagar", round(base_mes / 24 * 11, 2)),
        ("5BS.21204.004", "Sueldos por pagar", round(EMP[0][2], 2)),
        ("5PYG.51010.001", "Sueldos", round(base_mes * 12, 2)),
        ("5PYG.51030.001", "Aporte Patronal", round(base_mes * TASA_PAT * 12, 2)),
        ("5PYG.51040.001", "Décimo Tercer Sueldo", round(base_mes, 2)),
    ]
    for cta, desc, s25 in CTAS:
        s24 = round(s25 * 0.9, 2)
        ws.append([cta, desc, s24, None, None, s25])
    wb.save(os.path.join(DIR, "RQ-002_anexo_de_nomina_saldos_por_cuenta.xlsx"))


# --- RQ-007 muestreo décimos y RQ-008 kárdex (modelos simples) ---------------
def modelos():
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Solicitudes"
    ws.append(["Cédula", "Nombre", "¿Solicitó acumular D13?", "¿Solicitó acumular D14?", "Fecha solicitud", "Observación"])
    for ced, nom, *_ in EMP:
        ws.append([ced, nom, "Sí", "Sí", datetime.datetime(EJ, 1, 15), "Solicitud escrita en expediente"])
    wb.save(os.path.join(DIR, "RQ-007_muestreo_solicitudes_acumulacion_decimos.xlsx"))

    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Kardex"
    ws.append(["Cédula", "Nombre", "Días devengados", "Días gozados", "Días pagados", "Saldo días"])
    for ced, nom, *_ in EMP:
        ws.append([ced, nom, 15, 8, 0, 7])
    wb.save(os.path.join(DIR, "RQ-008_kardex_de_vacaciones.xlsx"))


# --- RQ-005 comprobantes de pago del IESS (PDF ficticios, legibles por pdftotext) ---
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _pdf_comprobante(ruta, no, mes, concepto, valor):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    c = canvas.Canvas(ruta, pagesize=A4)
    y = [790]

    def line(s):
        c.drawString(40, y[0], s); y[0] -= 15

    vig = f"{EJ}-{mes:02d}-15"
    line("INSTITUTO ECUATORIANO DE SEGURIDAD SOCIAL")
    line("Comprobante de pago (ejemplo ficticio — no es un documento oficial)")
    line(f"No. Comprobante:  {no}")
    line(f"Periodo de Pago:  {EJ}-{mes:02d}")
    line(f"Concepto:  {concepto},  Emitido")
    line(f"Emitido en:  {EJ}-{mes:02d}-10")
    line(f"Fecha de Vigencia de Pago:  {vig}")
    line(f"Valor       {valor:,.2f}")
    line("Intereses por mora (+)       0.00")
    line(f"Subtotal(=)       {valor:,.2f}")
    line("Notas de Crédito(-)       0.00")
    line(f"Total(=)       {valor:,.2f}")
    line(f"     {_MESES[mes - 1]} 15 del {EJ} 10:30")
    c.showPage()
    c.save()


def comprobantes_pdf():
    """Genera comprobantes PDF ficticios (Aportes y Fondos de reserva por mes) y los deja en un
    .zip. Son legibles por pdftotext (el parser RQ-005) para que la cédula DO-9 corra con datos."""
    base_mes = sum(e[2] for e in EMP)
    aportes = round(base_mes * (TASA_PAT + TASA_IND + TASA_CCC), 2)
    fr = round(base_mes * PCT_FR, 2)
    tmp = os.path.join(DIR, "_comp_tmp")
    os.makedirs(tmp, exist_ok=True)
    rutas_pdf = []
    no = 1000
    for mes in range(1, 13):
        no += 1
        p1 = os.path.join(tmp, f"comprobante_aportes_{EJ}{mes:02d}.pdf")
        _pdf_comprobante(p1, no, mes, "APORTES AL SEGURO GENERAL OBLIGATORIO", aportes)
        no += 1
        p2 = os.path.join(tmp, f"comprobante_fondos_reserva_{EJ}{mes:02d}.pdf")
        _pdf_comprobante(p2, no, mes, "FONDOS DE RESERVA", fr)
        rutas_pdf += [p1, p2]
    ruta_zip = os.path.join(DIR, "RQ-005_comprobantes_de_pago_iess.zip")
    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in rutas_pdf:
            z.write(p, os.path.basename(p))
    for p in rutas_pdf:
        os.remove(p)
    os.rmdir(tmp)


def main():
    os.makedirs(DIR, exist_ok=True)
    # Limpia los ejemplos de la versión 1.0 (actuarial) antes de escribir los de la 2.0.
    for f in os.listdir(DIR):
        if f.startswith("RQ-") and ("actuarial" in f or "empleados" in f or "roles_de_pago_mensuales" in f
                                    or "planillas_y_comprobantes" in f or "informe_actuarial" in f
                                    or "mayores_de_gasto_de_nomina_y_de_pasivos" in f
                                    or "registro_de_vacaciones" in f):
            os.remove(os.path.join(DIR, f))
    rol(); consolidado(); mayores(); anexo(); modelos(); comprobantes_pdf()
    print("Ejemplos de nómina 2.0 escritos en", DIR)
    for f in sorted(os.listdir(DIR)):
        print("  -", f)


if __name__ == "__main__":
    main()
