# -*- coding: utf-8 -*-
"""Orquestador de la herramienta de nómina.

API pública: ``correr(rutas) -> dict[str, bytes]`` con las 15 cédulas .xlsx.
Ejecuta en orden: motor (reproceso) → series compartidas (pickles) → comprobantes
(85 PDF) → 4 cédulas nuevas (DO-2, DO-3, DO-3.1, DO-4) → 10 generadores de
referencia (contra la carpeta de la prueba, sin rutas fijas)."""
from __future__ import annotations
import os, runpy
from backend.app.aud.niif.procesadores.nomina import rutas as rutas_mod
from backend.app.aud.niif.procesadores.nomina import motor, mayores, series, comprobantes, cedulas_nuevas, hallazgos

_DIR = os.path.dirname(__file__)
# generadores de referencia (archivo del paquete -> nombre de cédula de salida)
LEGACY = ['mk_do2', 'mk_do3', 'mk_do31', 'mk_do4', 'mk_do45', 'mk_do67', 'mk_do8', 'mk_do9', 'mk_do10', 'mk_do12', 'mk_pa', 'mk_rq007', 'mk_vac', 'mk_rq004']


def correr(rutas, ficha: dict | None = None) -> dict[str, bytes]:
    ficha = ficha or {}
    os.makedirs(rutas.home, exist_ok=True)
    os.makedirs(rutas.out, exist_ok=True)
    rutas_mod.CTX = rutas

    # 1) mayores + motor
    mayores.cargar(rutas)
    R = motor.correr(rutas)

    # 2) comprobantes RQ-005 (85 PDF) -> pickle (antes de las cifras, que los usan)
    comp = None
    if rutas.comprobantes_dir and os.path.isdir(rutas.comprobantes_dir):
        comp = comprobantes.parse(rutas.comprobantes_dir)
        comp.to_pickle(f'{rutas.home}/comprobantes.pkl')

    # 3) sujetos y cifras de los hallazgos/controles (derivados de los datos)
    rutas_mod.SUJETOS = hallazgos.sujetos(R, rutas)
    rutas_mod.CIFRAS = hallazgos.cifras(R, rutas, comp)

    # 4) series compartidas -> pickles que leen los generadores de referencia
    series.exportar_pickles(R, rutas)

    # 4) cédulas nuevas
    # DO-2: lo arma el generador de referencia ``mk_do2`` (en LEGACY), que calca la
    # cédula de referencia (2 hojas) reproduciendo el layout físico del anexo RQ-002 y
    # el bloque «cuentas solo en el mayor» agrupado por concepto de ``mayores.py``.
    # ``cedulas_nuevas.build_do2`` queda disponible pero ya no se invoca.
    # DO-3: lo arma el generador de referencia ``mk_do3`` (en LEGACY), que calca la
    # cédula de referencia leyendo el Consolidado crudo. ``cedulas_nuevas.build_do3``
    # queda disponible pero ya no se invoca.
    # DO-3.1: lo arma el generador de referencia ``mk_do31`` (en LEGACY), que calca la
    # cédula de referencia (7 hojas) leyendo el rol crudo y el Consolidado.
    # ``cedulas_nuevas.build_do31`` queda disponible pero ya no se invoca.
    # DO-4: lo arma el generador de referencia ``mk_do4`` (en LEGACY), que calca la
    # cédula de referencia (6 hojas) leyendo el Consolidado, el rol «normal», las
    # exclusiones y el anexo. ``cedulas_nuevas.build_do4`` queda disponible pero ya no
    # se invoca.

    # 5) generadores de referencia (in-process, aislados por carpeta de la prueba)
    for g in LEGACY:
        runpy.run_path(os.path.join(_DIR, g + '.py'), run_name='_nomina_gen')

    # 6) recolectar las cédulas .xlsx de la carpeta de salida
    salidas = {}
    for f in sorted(os.listdir(rutas.out)):
        if f.endswith('.xlsx'):
            with open(os.path.join(rutas.out, f), 'rb') as fh:
                salidas[f] = fh.read()
    return salidas
