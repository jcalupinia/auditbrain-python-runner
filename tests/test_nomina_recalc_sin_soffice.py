# -*- coding: utf-8 -*-
"""Regresión: el recálculo del visor de nómina NO debe romper si falta LibreOffice (`soffice`).

En la imagen de producción no está instalado `soffice`; antes, `recalcular` lanzaba
`FileNotFoundError` y tumbaba el refresco masivo de pruebas de nómina. Ahora degrada «sin visor»
(las cédulas se generan igual), igual que `servicio.recalc_nomina`.
"""
import io
import os

from openpyxl import Workbook

from backend.app.aud.niif.procesadores.nomina import recalc


def _cedula_xlsx() -> bytes:
    wb = Workbook()
    wb.active["A1"] = "=1+1"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_recalcular_degrada_si_no_hay_soffice(tmp_path, monkeypatch):
    def _sin_soffice(*a, **k):
        raise FileNotFoundError(2, "No such file or directory", "soffice")
    monkeypatch.setattr(recalc.subprocess, "run", _sin_soffice)

    # No debe lanzar: devuelve la carpeta recalc (vacía) y el proceso sigue.
    carpeta = recalc.recalcular({"cedula.xlsx": _cedula_xlsx()}, str(tmp_path))
    assert os.path.isdir(carpeta)


def test_recalcular_degrada_si_soffice_falla(tmp_path, monkeypatch):
    import subprocess

    def _falla(*a, **k):
        raise subprocess.CalledProcessError(1, "soffice")
    monkeypatch.setattr(recalc.subprocess, "run", _falla)

    carpeta = recalc.recalcular({"cedula.xlsx": _cedula_xlsx()}, str(tmp_path))
    assert os.path.isdir(carpeta)
