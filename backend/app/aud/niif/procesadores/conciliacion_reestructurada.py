# -*- coding: utf-8 -*-
"""Reestructuración de la conciliación bancaria (recálculo del mes auditado).

Cruza el LIBRO BANCOS con el ESTADO DE CUENTA del mes al que se realiza la
auditoría (p. ej. visita preliminar al 30-sep) para identificar las PARTIDAS
CONCILIATORIAS: los movimientos que están en una fuente y no en la otra. Arrastra
las partidas del mes anterior que aún no se depuran y mide su antigüedad al corte.

El motor solo IDENTIFICA y CLASIFICA las partidas; los signos de la conciliación
los aplica la cédula DA-3 (ver `caja_bancos_papel.py`, columnas por SUMIFS). Así
la reestructuración es independiente de la convención de signos de la firma.

Convención de datos (transcritos/revisados por el auditor, en perspectiva del
efectivo del cliente): cada movimiento es ``{fecha, documento, ingreso, egreso}``
donde ``ingreso`` aumenta el efectivo del cliente y ``egreso`` lo disminuye. Para
libros o extractos que vienen en columnas débito/crédito, use `desde_debito_credito`.

Clasificación (categorías de `caja_bancos_papel.CATEGORIAS`):
  - Ingreso en LIBROS no en extracto  → «Consignación no registrada» (depósito en tránsito)
  - Egreso  en LIBROS no en extracto  → «Cheque sin cobrar»
  - Ingreso en EXTRACTO no en libros  → «NC pendiente contabilizar» (nota de crédito bancaria)
  - Egreso  en EXTRACTO no en libros  → «Nota débito en tránsito» (nota de débito bancaria)
"""
from __future__ import annotations

import datetime

from backend.app.aud.niif.procesadores.caja_bancos_papel import (
    CHEQUE, CONSIGNACION, NC_PENDIENTE, ND_TRANSITO,
)

CENTAVO = 0.005  # tolerancia de igualdad de importes (medio centavo)


def _num(v) -> float:
    try:
        return round(float(str(v).replace(",", "")), 2)
    except (TypeError, ValueError):
        return 0.0


def _fecha(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    try:
        return datetime.date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def desde_debito_credito(filas, fuente: str):
    """Normaliza filas ``{fecha, documento, debito, credito}`` a la perspectiva del
    efectivo del cliente ``{fecha, documento, ingreso, egreso}``.

    - ``fuente="libro"``: en el libro bancos (activo) el débito aumenta el efectivo
      (ingreso) y el crédito lo disminuye (egreso).
    - ``fuente="extracto"``: el estado de cuenta viene desde la óptica del banco
      (el depósito del cliente es un crédito para el banco), así que se invierte:
      crédito → ingreso del cliente, débito → egreso del cliente.
    """
    if fuente not in ("libro", "extracto"):
        raise ValueError("fuente debe ser 'libro' o 'extracto'")
    out = []
    for f in filas:
        deb, cred = _num(f.get("debito")), _num(f.get("credito"))
        if fuente == "libro":
            ingreso, egreso = deb, cred
        else:
            ingreso, egreso = cred, deb
        out.append({"fecha": f.get("fecha"), "documento": f.get("documento") or f.get("referencia") or "",
                    "beneficiario": f.get("beneficiario") or "", "ingreso": ingreso, "egreso": egreso})
    return out


def _lados(movimientos):
    """Desdobla cada movimiento en (naturaleza, valor, mov) con valor > 0."""
    lados = []
    for m in movimientos:
        ing, egr = _num(m.get("ingreso")), _num(m.get("egreso"))
        if ing > 0:
            lados.append(("ingreso", ing, m))
        if egr > 0:
            lados.append(("egreso", egr, m))
    return lados


def _emparejar(libro_lados, extracto_lados, ventana_dias):
    """Empareja por (naturaleza, importe, |fecha| ≤ ventana). Devuelve los índices
    NO emparejados de cada lado. Emparejamiento voraz uno a uno."""
    usados_ext = set()
    libres_libro = []
    for il, (nat_l, val_l, ml) in enumerate(libro_lados):
        fl = _fecha(ml.get("fecha"))
        match = None
        for ie, (nat_e, val_e, me) in enumerate(extracto_lados):
            if ie in usados_ext or nat_e != nat_l or abs(val_e - val_l) > CENTAVO:
                continue
            fe = _fecha(me.get("fecha"))
            if fl and fe and abs((fe - fl).days) > ventana_dias:
                continue
            match = ie
            break
        if match is None:
            libres_libro.append(il)
        else:
            usados_ext.add(match)
    libres_ext = [ie for ie in range(len(extracto_lados)) if ie not in usados_ext]
    return libres_libro, libres_ext


def _categoria(fuente: str, naturaleza: str) -> str:
    if fuente == "libro":
        return CONSIGNACION if naturaleza == "ingreso" else CHEQUE
    return NC_PENDIENTE if naturaleza == "ingreso" else ND_TRANSITO


def reestructurar(libro_bancos, estado_cuenta, corte, banco="", *,
                  ventana_dias=5, partidas_previas=None):
    """Identifica las partidas conciliatorias del mes para una cuenta bancaria.

    Parámetros:
      libro_bancos, estado_cuenta: movimientos ``{fecha, documento, ingreso, egreso}``
        (use `desde_debito_credito` si vienen en débito/crédito).
      corte: fecha de corte (para antigüedad de las partidas).
      banco: nombre de la cuenta/banco (se copia a cada partida).
      ventana_dias: tolerancia de fecha para considerar dos movimientos el mismo.
      partidas_previas: partidas del mes anterior aún abiertas ``{fecha, documento,
        beneficiario, categoria, valor, observacion}``; las que no aparezcan
        emparejadas este mes se arrastran.

    Devuelve ``{"partidas": [...], "resumen": {...}}`` con las partidas en el mismo
    formato que consume `caja_bancos_papel.construir`.
    """
    corte = _fecha(corte)
    libro_lados = _lados(libro_bancos)
    ext_lados = _lados(estado_cuenta)
    libres_libro, libres_ext = _emparejar(libro_lados, ext_lados, ventana_dias)

    partidas = []

    def _agregar(fuente, idx_list, lados):
        for i in idx_list:
            nat, val, mov = lados[i]
            f = _fecha(mov.get("fecha"))
            partidas.append({
                "fecha": f, "banco": banco, "categoria": _categoria(fuente, nat),
                "documento": mov.get("documento") or "", "beneficiario": mov.get("beneficiario") or "",
                "valor": val,
                "observacion": ("En libros, pendiente en el banco" if fuente == "libro"
                                else "En el banco, pendiente de registrar"),
                "dias_vencidos": ((corte - f).days if (corte and f) else None),
            })

    _agregar("libro", libres_libro, libro_lados)
    _agregar("extracto", libres_ext, ext_lados)

    # Arrastre de partidas del mes anterior aún no depuradas: se conservan las que
    # NO se emparejaron con un movimiento de este mes (mismo importe y categoría).
    if partidas_previas:
        emparejadas = {(p["categoria"], round(p["valor"], 2)) for p in partidas}
        for pv in partidas_previas:
            clave = (pv.get("categoria"), round(_num(pv.get("valor")), 2))
            if clave in emparejadas:
                continue  # se depuró este mes
            f = _fecha(pv.get("fecha"))
            partidas.append({
                "fecha": f, "banco": banco, "categoria": pv.get("categoria"),
                "documento": pv.get("documento") or "", "beneficiario": pv.get("beneficiario") or "",
                "valor": _num(pv.get("valor")),
                "observacion": (pv.get("observacion") or "") + " · arrastrada del mes anterior",
                "dias_vencidos": ((corte - f).days if (corte and f) else None),
            })

    resumen = {"total_partidas": len(partidas),
               "por_categoria": {c: round(sum(p["valor"] for p in partidas if p["categoria"] == c), 2)
                                 for c in {p["categoria"] for p in partidas}},
               "emparejadas_libro": len(libro_lados) - len(libres_libro),
               "emparejadas_extracto": len(ext_lados) - len(libres_ext)}
    return {"partidas": partidas, "resumen": resumen}
