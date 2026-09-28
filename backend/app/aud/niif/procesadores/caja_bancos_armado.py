# -*- coding: utf-8 -*-
"""Puente entre el registro de la prueba «efectivo_equivalentes» y el papel formulado.

Toma el `registro` de una prueba (engagement + los datasets ya cargados: `cuentas`
= RQ-001 y `partidas` = RQ-002) y arma el papel de trabajo DA con fórmulas vivas
(`caja_bancos_papel.construir`). No requiere anexos nuevos: reutiliza la información
que la prueba ya recibió y validó.
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores import caja_bancos_papel as papel

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


def hay_datos(reg: dict) -> bool:
    """True si la prueba tiene al menos el anexo de cuentas para armar el papel."""
    return bool(_cuentas(reg))


def armar_desde_registro(reg: dict) -> bytes:
    """Devuelve los bytes del papel de trabajo DA formulado desde el registro."""
    cuentas = _cuentas(reg)
    partidas = _partidas(reg, cuentas)
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
    return papel.construir({
        "engagement": _engagement(reg),
        "cuentas": cuentas,
        "partidas": partidas,
        "hallazgos": hallazgos,
    })
