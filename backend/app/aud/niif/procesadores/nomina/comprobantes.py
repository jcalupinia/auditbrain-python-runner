# -*- coding: utf-8 -*-
"""RQ-005 — Lectura de los comprobantes de pago del IESS (PDF, texto extraíble).
Usa ``pdftotext -layout`` (poppler-utils). Refactor del script de referencia a
``parse(carpeta) -> DataFrame`` sin rutas fijas."""
import re, subprocess, glob, os
import pandas as pd


def _num(pat, t):
    m = re.search(pat + r'\s+(-?[\d,]*\.\d+)', t)
    return float(m.group(1).replace(',', '')) if m else None


def parse(carpeta: str) -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(os.path.join(carpeta, '**', '*.pdf'), recursive=True)):
        t = subprocess.run(['pdftotext', '-layout', f, '-'], capture_output=True, text=True).stdout
        g = lambda p: (re.search(p, t).group(1).strip() if re.search(p, t) else None)
        per = g(r'Periodo de Pago:\s+([^\n]+)')
        m = re.search(r'(\d{4})\s*-\s*(\d{2})', per or '') or re.search(r'Desde:\s*(\d{4})-(\d{2})', per or '')
        con = g(r'Concepto:\s+(.+?),?\s{2,}Emitido') or ''
        cl = con.upper(); fn = os.path.basename(f).lower()
        if 'FONDOS DE RESERVA' in cl: tipo = 'Fondos de reserva'
        elif 'HIPOTECARIO' in cl: tipo = 'Préstamo hipotecario'
        elif 'PAG.DIV.PRESTAMOS' in cl: tipo = 'Préstamo quirografario'
        elif 'conyu' in fn or 'conye' in fn or 'EXTENSI' in cl: tipo = 'Extensión de salud cónyuges'
        else: tipo = 'Aportes'
        rows.append(dict(
            archivo=os.path.relpath(f, carpeta), tipo=tipo, comprobante=g(r'No\. Comprobante:\s+(\d+)'), concepto=con,
            emitido=g(r'Emitido en:\s+(\S+)'), vigencia=g(r'Fecha de Vigencia de Pago:\s+(\S+)'), periodo=per,
            anio=int(m.group(1)) if m else None, mes=int(m.group(2)) if m else None,
            valor=_num(r'Valor', t), intereses=_num(r'Intereses por mora \(\+\)', t),
            seguro_tp=_num(r'Seguro Salud Tiempo Parcial\(\+\)', t), honorarios=_num(r'Honorarios Abogado\(\+\)', t),
            gastos_adm=_num(r'Gastos Administrativos\(\+\)', t), subtotal=_num(r'Subtotal\(=\)', t),
            notas_credito=_num(r'Notas de Crédito\(-\)', t), total=_num(r'Total\(=\)', t),
            impreso=g(r'\n\s+(\w+ \d+ del \d{4} \d{2}:\d{2})'), paginas=t.count('\f') or 1))
    return pd.DataFrame(rows)
