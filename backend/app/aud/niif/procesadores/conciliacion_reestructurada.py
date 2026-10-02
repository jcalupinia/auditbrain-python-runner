# -*- coding: utf-8 -*-
"""Reestructuración de la conciliación bancaria (reproceso independiente del mes auditado).

Cruza el LIBRO BANCOS (mayor) con el ESTADO DE CUENTA del mes al que se realiza la
auditoría (p. ej. visita preliminar al 30-sep) para reconstruir la conciliación sin
depender de los cálculos de la compañía. Identifica las COINCIDENCIAS por un motor de
matching por niveles y las PARTIDAS CONCILIATORIAS (los movimientos que están en una
fuente y no en la otra). Arrastra las partidas del mes anterior que aún no se depuran y
mide su antigüedad al corte.

MATCHING POR NIVELES (cascada; cada nivel corre sobre lo aún no emparejado; todos exigen
la misma naturaleza —ingreso/egreso— y, salvo el nivel de diferencia de valor, el mismo
importe dentro de la tolerancia):
  N1  valor + fecha + referencia (exacto)
  N2  valor + fecha
  N3  valor + referencia
  N4  valor + fecha con tolerancia (ventana de días); si a un lado le falta la fecha,
      empareja solo por valor (compatibilidad con el motor 1:1 anterior)
  N5  1:N  — un movimiento del extracto = suma de varios del libro (dentro de la ventana)
  N6  N:1  — un movimiento del libro = suma de varios del extracto
  N7  fecha + referencia con DIFERENCIA de valor → coincidencia marcada «diferencia de valor»

Lo que queda sin emparejar se clasifica (categorías de `caja_bancos_papel.CATEGORIAS`):
  - Ingreso en LIBROS no en extracto  → «Consignación no registrada» (depósito en tránsito)
  - Egreso  en LIBROS no en extracto  → «Cheque sin cobrar»
  - Ingreso en EXTRACTO no en libros  → «NC pendiente contabilizar» (nota de crédito bancaria)
  - Egreso  en EXTRACTO no en libros  → «Nota débito en tránsito» (nota de débito bancaria)

El motor solo IDENTIFICA, EMPAREJA y CLASIFICA; los signos del cuadre los aplica la cédula
DA-3 (ver `caja_bancos_papel.py`, columnas por SUMIFS) y la reconstrucción numérica
(saldo banco ± partidas = saldo ajustado vs saldo mayor) la hace `reconstruir(...)`.

Todo es determinista (sin IA). Convención de datos (transcritos/revisados por el auditor,
en perspectiva del efectivo del cliente): cada movimiento es ``{fecha, documento, ingreso,
egreso}`` donde ``ingreso`` aumenta el efectivo y ``egreso`` lo disminuye. Para libros o
extractos en columnas débito/crédito, use `desde_debito_credito`.
"""
from __future__ import annotations

import datetime
import itertools
import re

from backend.app.aud.niif.procesadores.caja_bancos_papel import (
    CHEQUE, CONSIGNACION, NC_PENDIENTE, ND_TRANSITO,
)

CENTAVO = 0.005      # tolerancia de igualdad de importes (medio centavo)
VENTANA_DIAS = 5     # tolerancia de fecha por defecto
MAX_GRUPO = 5        # tamaño máximo de una agrupación 1:N / N:1
_MAX_CANDIDATOS = 25  # cota de costo para la búsqueda combinatoria de grupos


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


def _norm_ref(v) -> str:
    """Referencia normalizada para comparar documentos (sin acentos ni símbolos)."""
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())


def _dias(a, b):
    return None if (a is None or b is None) else abs((a - b).days)


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


def emparejar(libro_lados, ext_lados, ventana_dias=VENTANA_DIAS, tol=CENTAVO, max_grupo=MAX_GRUPO):
    """Motor de matching por niveles entre los lados del libro y del extracto.

    Devuelve ``(matches, libres_libro, libres_ext)`` donde cada match es
    ``{"libro":[idx...], "ext":[idx...], "nivel":int, "criterio":str, "tipo":"n:m",
       "diff_valor":float, "diff_dias":int|None}``.
    """
    n_l, n_e = len(libro_lados), len(ext_lados)
    libre_l, libre_e = [True] * n_l, [True] * n_e
    fL = [_fecha(m[2].get("fecha")) for m in libro_lados]
    fE = [_fecha(m[2].get("fecha")) for m in ext_lados]
    rL = [_norm_ref(m[2].get("documento")) for m in libro_lados]
    rE = [_norm_ref(m[2].get("documento")) for m in ext_lados]
    matches: list[dict] = []

    def _registrar(il_list, ie_list, nivel, criterio):
        vL = sum(libro_lados[i][1] for i in il_list)
        vE = sum(ext_lados[j][1] for j in ie_list)
        difs = [d for i in il_list for j in ie_list if (d := _dias(fL[i], fE[j])) is not None]
        matches.append({"libro": list(il_list), "ext": list(ie_list), "nivel": nivel, "criterio": criterio,
                        "tipo": f"{len(il_list)}:{len(ie_list)}", "diff_valor": round(vE - vL, 2),
                        "diff_dias": (max(difs) if difs else None)})
        for i in il_list:
            libre_l[i] = False
        for j in ie_list:
            libre_e[j] = False

    def _compatibles(i, j) -> bool:
        return libro_lados[i][0] == ext_lados[j][0] and abs(libro_lados[i][1] - ext_lados[j][1]) <= tol

    # --- Niveles 1:1 (N1–N4) -------------------------------------------------------------
    predicados = [
        (1, "valor + fecha + referencia", lambda i, j: bool(fL[i]) and fL[i] == fE[j] and bool(rL[i]) and rL[i] == rE[j]),
        (2, "valor + fecha", lambda i, j: bool(fL[i]) and fL[i] == fE[j]),
        (3, "valor + referencia", lambda i, j: bool(rL[i]) and rL[i] == rE[j]),
        (4, "valor + fecha (tolerancia)",
         lambda i, j: (fL[i] is None or fE[j] is None) or (_dias(fL[i], fE[j]) <= ventana_dias)),
    ]
    for nivel, crit, pred in predicados:
        for i in range(n_l):
            if not libre_l[i]:
                continue
            for j in range(n_e):
                if libre_e[j] and _compatibles(i, j) and pred(i, j):
                    _registrar([i], [j], nivel, crit)
                    break

    # --- Niveles de agrupación (N5 1:N, N6 N:1) ------------------------------------------
    def _grupo(uno_lados, uno_f, uno_libre, muchos_lados, muchos_f, muchos_libre, nivel, crit, uno_es_ext):
        for iu in range(len(uno_lados)):
            if not uno_libre[iu]:
                continue
            nat, valor, _ = uno_lados[iu]
            cand = [k for k in range(len(muchos_lados)) if muchos_libre[k] and muchos_lados[k][0] == nat
                    and muchos_lados[k][1] <= valor + tol
                    and ((d := _dias(uno_f[iu], muchos_f[k])) is None or d <= ventana_dias)][:_MAX_CANDIDATOS]
            combo = None
            for r in range(2, min(max_grupo, len(cand)) + 1):
                for c in itertools.combinations(cand, r):
                    if abs(sum(muchos_lados[k][1] for k in c) - valor) <= tol:
                        combo = c
                        break
                if combo:
                    break
            if combo:
                if uno_es_ext:
                    _registrar(list(combo), [iu], nivel, crit)   # N5: varios libro = un extracto
                else:
                    _registrar([iu], list(combo), nivel, crit)   # N6: un libro = varios extracto

    _grupo(ext_lados, fE, libre_e, libro_lados, fL, libre_l, 5, "1:N (un extracto = varios del libro)", uno_es_ext=True)
    _grupo(libro_lados, fL, libre_l, ext_lados, fE, libre_e, 6, "N:1 (un libro = varios del extracto)", uno_es_ext=False)

    # --- N7: misma fecha + referencia con DIFERENCIA de valor ----------------------------
    for i in range(n_l):
        if not libre_l[i]:
            continue
        for j in range(n_e):
            if (libre_e[j] and libro_lados[i][0] == ext_lados[j][0] and bool(rL[i]) and rL[i] == rE[j]
                    and fL[i] and fL[i] == fE[j]):
                _registrar([i], [j], 7, "fecha + referencia (diferencia de valor)")
                break

    return matches, [i for i in range(n_l) if libre_l[i]], [j for j in range(n_e) if libre_e[j]]


def _categoria(fuente: str, naturaleza: str) -> str:
    if fuente == "libro":
        return CONSIGNACION if naturaleza == "ingreso" else CHEQUE
    return NC_PENDIENTE if naturaleza == "ingreso" else ND_TRANSITO


def _duplicados(lados) -> int:
    vistos, dup = {}, 0
    for nat, val, m in lados:
        clave = (nat, round(val, 2), _fecha(m.get("fecha")), _norm_ref(m.get("documento")))
        vistos[clave] = vistos.get(clave, 0) + 1
        if vistos[clave] > 1:
            dup += 1
    return dup


def reestructurar(libro_bancos, estado_cuenta, corte, banco="", *,
                  ventana_dias=VENTANA_DIAS, tolerancia=CENTAVO, max_grupo=MAX_GRUPO, partidas_previas=None):
    """Identifica las partidas conciliatorias del mes para una cuenta bancaria.

    Parámetros:
      libro_bancos, estado_cuenta: movimientos ``{fecha, documento, ingreso, egreso}``
        (use `desde_debito_credito` si vienen en débito/crédito).
      corte: fecha de corte (para antigüedad de las partidas).
      banco: nombre de la cuenta/banco (se copia a cada partida).
      ventana_dias, tolerancia, max_grupo: parámetros del matching por niveles.
      partidas_previas: partidas del mes anterior aún abiertas; las que no aparezcan
        emparejadas este mes se arrastran.

    Devuelve ``{"partidas": [...], "resumen": {...}, "matches": [...]}``; ``partidas``
    conserva el formato que consume `caja_bancos_papel.construir`.
    """
    corte = _fecha(corte)
    libro_lados = _lados(libro_bancos)
    ext_lados = _lados(estado_cuenta)
    matches, libres_libro, libres_ext = emparejar(libro_lados, ext_lados, ventana_dias, tolerancia, max_grupo)

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

    emparejados_libro = sum(len(m["libro"]) for m in matches)
    emparejados_ext = sum(len(m["ext"]) for m in matches)
    resumen = {
        "total_partidas": len(partidas),
        "por_categoria": {c: round(sum(p["valor"] for p in partidas if p["categoria"] == c), 2)
                          for c in {p["categoria"] for p in partidas}},
        "emparejadas_libro": emparejados_libro,
        "emparejadas_extracto": emparejados_ext,
        "coincidencias": len(matches),
        "por_nivel": {n: sum(1 for m in matches if m["nivel"] == n) for n in sorted({m["nivel"] for m in matches})},
        "solo_libros": len(libres_libro),
        "solo_banco": len(libres_ext),
        "con_diferencia_fecha": sum(1 for m in matches if (m["diff_dias"] or 0) > 0),
        "con_diferencia_valor": sum(1 for m in matches if abs(m["diff_valor"]) > tolerancia),
        "duplicados_libro": _duplicados(libro_lados),
        "duplicados_extracto": _duplicados(ext_lados),
    }
    return {"partidas": partidas, "resumen": resumen, "matches": matches}


def reconstruir(saldo_extracto, saldo_libros, partidas, *, tolerancia=CENTAVO):
    """Reconstruye el cuadre de la conciliación desde las partidas (determinista).

    Aplica los signos de la conciliación bancaria clásica sobre el saldo del extracto:
      saldo s/auditoría = saldo extracto + consignaciones no registradas (depósitos en
      tránsito) − cheques sin cobrar + notas de crédito pendientes − notas de débito en
      tránsito.
    Compara contra el saldo según libros y devuelve la diferencia y el estado.
    """
    por = {c: 0.0 for c in (CONSIGNACION, CHEQUE, NC_PENDIENTE, ND_TRANSITO)}
    for p in partidas:
        por[p["categoria"]] = round(por.get(p["categoria"], 0.0) + _num(p.get("valor")), 2)
    saldo_auditoria = round(_num(saldo_extracto) + por[CONSIGNACION] - por[CHEQUE]
                            + por[NC_PENDIENTE] - por[ND_TRANSITO], 2)
    diferencia = round(saldo_auditoria - _num(saldo_libros), 2)
    return {
        "saldo_extracto": _num(saldo_extracto), "saldo_libros": _num(saldo_libros),
        "consignaciones": por[CONSIGNACION], "cheques": por[CHEQUE],
        "notas_credito": por[NC_PENDIENTE], "notas_debito": por[ND_TRANSITO],
        "saldo_auditoria": saldo_auditoria, "diferencia": diferencia,
        "estado": "CONCILIADA" if abs(diferencia) <= tolerancia else "DIFERENCIA DE REPROCESO",
    }


def comparar_con_compania(partidas_reproceso, partidas_compania, *, tolerancia=CENTAVO):
    """Compara la conciliación reprocesada por AUDIT-IA contra la que presentó la
    compañía (dataset `partidas`/RQ-002). Empareja por (categoría, importe) e informa
    las partidas omitidas por la compañía, las adicionales y las coincidentes.
    """
    def _clave(p):
        cat = p.get("categoria") or p.get("tipo") or ""
        return (str(cat), round(_num(p.get("valor") if p.get("valor") is not None else p.get("importe")), 2))

    comp = {}
    for p in (partidas_compania or []):
        comp.setdefault(_clave(p), []).append(p)
    omitidas, coincidentes = [], []
    for p in (partidas_reproceso or []):
        k = _clave(p)
        if comp.get(k):
            comp[k].pop()
            coincidentes.append(p)
        else:
            omitidas.append(p)   # AUDIT-IA la identificó y la compañía no
    adicionales = [p for resto in comp.values() for p in resto]  # la compañía la puso y el reproceso no
    return {"omitidas_por_la_compania": omitidas, "adicionales_de_la_compania": adicionales,
            "coincidentes": coincidentes,
            "total_omitidas": len(omitidas), "total_adicionales": len(adicionales),
            "total_coincidentes": len(coincidentes)}
