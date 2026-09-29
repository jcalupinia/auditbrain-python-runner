# -*- coding: utf-8 -*-
"""Puente entre el registro de la prueba «efectivo_equivalentes» y el papel formulado.

Toma el `registro` de una prueba (engagement + los datasets ya cargados: `cuentas`
= RQ-001 y `partidas` = RQ-002) y arma el papel de trabajo DA con fórmulas vivas
(`caja_bancos_papel.construir`). No requiere anexos nuevos: reutiliza la información
que la prueba ya recibió y validó.
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores import caja_bancos_papel as papel
from backend.app.aud.niif.procesadores import conciliacion_reestructurada as cr

# El «tipo» de partida del procesador (efectivo_equivalentes) → categoría del papel.
_TIPO_A_CATEGORIA = {
    "Depósito en tránsito": papel.CONSIGNACION,
    "Cheque pendiente": papel.CHEQUE,
    "Nota de crédito": papel.NC_PENDIENTE,
    "Nota de débito": papel.ND_TRANSITO,
    "Otra partida": papel.OTRA,
}


def _cuentas(reg: dict) -> list[dict]:
    filas = ((reg.get("datasets") or {}).get("cuentas")) or reg.get("rows") or []
    out = []
    for f in filas:
        out.append({
            "cuenta": f.get("id") or f.get("cuenta") or "",
            "descripcion": f.get("nombre") or f.get("descripcion") or "",
            "saldo_anterior": f.get("saldo_anterior") or 0,
            "saldo_actual": f.get("saldo_libros") or f.get("saldo_actual") or 0,
            "ncuenta": f.get("ncuenta") or "",
            "extracto": f.get("saldo_banco") or f.get("extracto") or 0,
        })
    return out


def _partidas(reg: dict, cuentas: list[dict]) -> list[dict]:
    filas = ((reg.get("datasets") or {}).get("partidas")) or []
    # código de cuenta → nombre, para poner el banco legible en la partida.
    nombre_por_codigo = {str(c["cuenta"]): c["descripcion"] for c in cuentas}
    out = []
    for f in filas:
        cod = str(f.get("cuenta") or "")
        tipo = f.get("tipo") or ""
        out.append({
            "fecha": f.get("fecha_origen") or f.get("fecha"),
            "banco": nombre_por_codigo.get(cod, cod),
            "categoria": _TIPO_A_CATEGORIA.get(tipo, papel.clasificar(f.get("referencia"), "")),
            "documento": f.get("referencia") or f.get("documento") or "",
            "beneficiario": f.get("beneficiario") or "",
            "valor": f.get("importe") or f.get("valor") or 0,
            "observacion": f.get("observacion") or "",
        })
    return out


def _engagement(reg: dict) -> dict:
    e = reg.get("engagement") or {}
    return {
        "client": e.get("client", ""),
        "period": e.get("period") or e.get("cutoff", ""),
        "cutoff": e.get("cutoff", ""),
        "preparer": e.get("preparer", ""),
        "reviewer": e.get("reviewer", ""),
    }


def _num(v) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _libro_mayor(reg: dict):
    """Devuelve (filas_para_hoja, totales_por_cuenta) desde el anexo Libro Mayor (RQ-009).

    filas_para_hoja: filas listas para la hoja «Libro Mayor» del papel.
    totales_por_cuenta: {código: {"debitos": x, "creditos": y}} para el Movimiento.
    """
    filas = ((reg.get("datasets") or {}).get("libro_mayor")) or []
    hoja, totales = [], {}
    for f in filas:
        cod = str(f.get("cuenta") or "")
        deb, cred = _num(f.get("debito")), _num(f.get("credito"))
        t = totales.setdefault(cod, {"debitos": 0.0, "creditos": 0.0})
        t["debitos"] += deb
        t["creditos"] += cred
        hoja.append([cod, f.get("descripcion") or "", "", "", f.get("fecha") or "",
                     f.get("comprobante") or "", f.get("detalle") or "", f.get("tercero") or "",
                     deb, cred])
    return hoja, totales


def _reestructurar(reg: dict, cuentas: list[dict]):
    """Si hay estado de cuenta (RQ-010), recalcula las partidas conciliatorias por
    cuenta cruzando el libro mayor con el estado de cuenta y arrastrando la
    conciliación del mes anterior (RQ-011). Devuelve None si no hay estado de cuenta."""
    ds = reg.get("datasets") or {}
    estado = ds.get("estado_cuenta")
    if not estado:
        return None
    corte = (reg.get("engagement") or {}).get("cutoff")
    mayor = ds.get("libro_mayor") or []
    previas = ds.get("conciliacion_anterior") or []
    nombre = {str(c["cuenta"]): c["descripcion"] for c in cuentas}
    partidas = []
    codigos = {str(f.get("cuenta") or "") for f in estado} | {str(f.get("cuenta") or "") for f in mayor}
    for cod in sorted(c for c in codigos if c):
        libro = cr.desde_debito_credito([f for f in mayor if str(f.get("cuenta")) == cod], "libro")
        extracto = cr.desde_debito_credito([f for f in estado if str(f.get("cuenta")) == cod], "extracto")
        prev = [{"fecha": p.get("fecha"), "documento": p.get("documento"), "categoria": p.get("categoria"),
                 "valor": p.get("valor"), "observacion": p.get("observacion")}
                for p in previas if str(p.get("cuenta")) == cod]
        r = cr.reestructurar(libro, extracto, corte, banco=nombre.get(cod, cod), partidas_previas=prev)
        partidas.extend(r["partidas"])
    return partidas


def matriz_reproceso(reg: dict):
    """Reproceso independiente del último mes por cuenta (salida del botón «Reproceso»).

    Para cada cuenta con estado de cuenta (RQ-010): cruza el estado bancario contra el
    libro mayor (RQ-009) con el motor de matching por niveles, reconstruye el cuadre
    (saldo extracto ± partidas = saldo s/auditoría vs saldo libros → diferencia) y compara
    contra la conciliación de la compañía (RQ-002). Determinista, sin IA. Devuelve la
    matriz de resultados (una fila por cuenta) o ``None`` si no se cargó estado de cuenta.
    """
    ds = reg.get("datasets") or {}
    estado = ds.get("estado_cuenta")
    if not estado:
        return None
    cuentas = _cuentas(reg)
    corte = (reg.get("engagement") or {}).get("cutoff")
    mayor = ds.get("libro_mayor") or []
    previas = ds.get("conciliacion_anterior") or []
    compania = ds.get("partidas") or []
    saldos = {str(c["cuenta"]): c for c in cuentas}
    nombre = {str(c["cuenta"]): c["descripcion"] for c in cuentas}
    # La caja física se audita por arqueo (DA-5), no por conciliación bancaria: se excluye del reproceso.
    caja = {str(f.get("id") or f.get("cuenta") or "") for f in (ds.get("cuentas") or [])
            if str(f.get("tipo") or "").strip().lower().startswith(("caja", "fondo"))}
    codigos = {str(f.get("cuenta") or "") for f in estado} | {str(f.get("cuenta") or "") for f in mayor}
    filas = []
    for cod in sorted(c for c in codigos if c and c not in caja):
        libro = cr.desde_debito_credito([f for f in mayor if str(f.get("cuenta")) == cod], "libro")
        extracto = cr.desde_debito_credito([f for f in estado if str(f.get("cuenta")) == cod], "extracto")
        prev = [{"fecha": p.get("fecha"), "documento": p.get("documento"), "categoria": p.get("categoria"),
                 "valor": p.get("valor"), "observacion": p.get("observacion")}
                for p in previas if str(p.get("cuenta")) == cod]
        r = cr.reestructurar(libro, extracto, corte, banco=nombre.get(cod, cod), partidas_previas=prev)
        c = saldos.get(cod, {})
        rec = cr.reconstruir(c.get("extracto") or 0, c.get("saldo_actual") or 0, r["partidas"])
        # La conciliación de la compañía (RQ-002) usa el vocabulario `tipo`; se traduce a las
        # categorías del papel para que la comparación sea homogénea.
        comp = [{"categoria": _TIPO_A_CATEGORIA.get(p.get("tipo") or "", papel.OTRA),
                 "valor": _num(p.get("importe") if p.get("importe") is not None else p.get("valor"))}
                for p in compania if str(p.get("cuenta")) == cod]
        cmp = cr.comparar_con_compania(r["partidas"], comp)
        filas.append({
            "cuenta": cod, "banco": nombre.get(cod, cod),
            "saldo_extracto": rec["saldo_extracto"], "saldo_libros": rec["saldo_libros"],
            "consignaciones": rec["consignaciones"], "cheques": rec["cheques"],
            "notas_credito": rec["notas_credito"], "notas_debito": rec["notas_debito"],
            "saldo_auditoria": rec["saldo_auditoria"], "diferencia": rec["diferencia"], "estado": rec["estado"],
            "n_partidas_reproceso": len(r["partidas"]), "n_partidas_compania": len(comp),
            "omitidas_por_la_compania": cmp["total_omitidas"], "adicionales_de_la_compania": cmp["total_adicionales"],
            "coincidencias": r["resumen"]["coincidencias"], "por_nivel": r["resumen"]["por_nivel"],
        })
    return filas


def _arqueo(reg: dict):
    """Filas del arqueo de caja (RQ-012) para la cédula DA-5, o None si no se cargó."""
    filas = ((reg.get("datasets") or {}).get("arqueo"))
    if not filas:
        return None
    return [{"denominacion": f.get("denominacion") or "", "cantidad": f.get("cantidad") or 0,
             "valor_unitario": f.get("valor_unitario") or 0} for f in filas]


def hay_datos(reg: dict) -> bool:
    """True si la prueba tiene al menos el anexo de cuentas para armar el papel."""
    return bool(_cuentas(reg))


def armar_desde_registro(reg: dict) -> bytes:
    """Devuelve los bytes del papel de trabajo DA formulado desde el registro."""
    cuentas = _cuentas(reg)
    # Partidas: recalculadas por reestructuración si hay estado de cuenta; si no,
    # las cargadas manualmente (RQ-002).
    partidas = _reestructurar(reg, cuentas)
    if partidas is None:
        partidas = _partidas(reg, cuentas)
    hoja_mayor, totales_mayor = _libro_mayor(reg)
    # Si hay Libro Mayor (RQ-009), el Movimiento usa débitos/créditos reales del período.
    for c in cuentas:
        t = totales_mayor.get(str(c["cuenta"]))
        if t:
            c["debitos"], c["creditos"] = t["debitos"], t["creditos"]
    hallazgos = []
    # Hallazgo automático: partidas conciliatorias antiguas (si las hubiera se ven en DA-4).
    if partidas:
        hallazgos.append({
            "observacion": "Revisar la antigüedad de las partidas conciliatorias (ver DA-4, «Días vencidos»).",
            "criterio": "NIC 7 / política de conciliaciones",
            "efecto": "Posible sobre/subvaluación del efectivo",
            "ref": "DA-4",
            "recomendacion": "Depurar las partidas antiguas y registrar los ajustes que correspondan.",
        })
    entrada = {
        "engagement": _engagement(reg),
        "cuentas": cuentas,
        "partidas": partidas,
        "hallazgos": hallazgos,
        "libro_mayor": hoja_mayor,
    }
    arqueo = _arqueo(reg)
    if arqueo is not None:
        entrada["arqueo"] = arqueo   # si no viene, el papel usa su plantilla de denominaciones
    entrada["dias_prescripcion"] = (reg.get("parameters") or {}).get("diasPrescripcion", 390)
    return papel.construir(entrada)
