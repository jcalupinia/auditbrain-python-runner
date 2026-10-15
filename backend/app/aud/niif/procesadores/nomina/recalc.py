# -*- coding: utf-8 -*-
"""Recálculo de las cédulas de nómina con LibreOffice (valores en caché).

El visor del panel (``visor.py``) lee el valor de cada fórmula desde el libro en modo
``data_only``; sin recalcular, ese valor viene vacío (openpyxl no evalúa fórmulas). Este
módulo toma las cédulas que produjo el motor (``nomina_beneficios.correr_prueba`` →
``{nombre: bytes}``), fuerza el recálculo al abrir (``fullCalcOnLoad``) y las convierte con
``soffice`` headless, igual que el repo recalcula en ``scripts/verificar_datos_cliente.py``.

Deja las cédulas recalculadas en una carpeta (``<destino>/recalc``) que se pasa a
``nomina_panel_html.render(..., carpeta_cedulas=...)``.
"""
from __future__ import annotations

import io
import logging
import os
import subprocess

import openpyxl

log = logging.getLogger(__name__)


def _forzar_recalculo(data: bytes) -> bytes:
    """Marca el libro para que LibreOffice recalcule todas las fórmulas al abrirlo."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data))
        wb.calculation.fullCalcOnLoad = True
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
    except Exception:  # noqa: BLE001 (si el libro no se puede reabrir, se recalcula igual al convertir)
        return data


def recalcular(cedulas: dict[str, bytes], destino: str, timeout: int = 300) -> str:
    """Escribe las cédulas, las recalcula con LibreOffice y devuelve la carpeta recalculada.

    ``cedulas``: ``{nombre_cédula.xlsx: bytes}`` (lo que devuelve ``correr_prueba``).
    ``destino``: carpeta de trabajo; las originales van a ``<destino>/orig`` y las
    recalculadas a ``<destino>/recalc`` (la que usa el visor).
    """
    orig = os.path.join(destino, "orig")
    recalc = os.path.join(destino, "recalc")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(recalc, exist_ok=True)

    rutas = []
    for nombre, data in cedulas.items():
        if not nombre.lower().endswith(".xlsx"):
            continue
        ruta = os.path.join(orig, nombre)
        with open(ruta, "wb") as fh:
            fh.write(_forzar_recalculo(data))
        rutas.append(ruta)
    if not rutas:
        return recalc

    # Un perfil de usuario propio evita choques entre corridas concurrentes de soffice.
    perfil = os.path.join(destino, "_lo")
    try:
        subprocess.run(
            ["soffice", f"-env:UserInstallation=file://{perfil}", "--headless", "--calc",
             "--convert-to", "xlsx", "--outdir", recalc, *rutas],
            check=True, capture_output=True, timeout=timeout)
    except FileNotFoundError:
        # LibreOffice no está instalado en esta imagen (p. ej. la de producción). No se puede
        # recalcular el visor, pero el papel/cédulas sí se generan: se degrada «sin visor» en vez
        # de romper, igual que ``servicio.recalc_nomina``. El Excel descargado recalcula al abrirse.
        log.warning("soffice no está instalado: el panel de nómina se mostrará sin visor "
                    "(las cédulas se generan igual; Excel recalcula al abrir).")
        return recalc  # vacío: el visor queda sin valores precalculados, pero nada rompe
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log.warning("soffice falló al recalcular el visor de nómina (%s): se muestra sin visor.",
                    type(e).__name__)
        return recalc
    return recalc
