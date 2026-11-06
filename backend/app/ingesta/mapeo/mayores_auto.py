"""Deteccion conservadora de columnas para mayores tabulares.

No infiere la polaridad contable de importes firmados: requiere una
convencion explicitamente confirmada por el auditor.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from typing import Iterable

from backend.app.ingesta.normalizer import normalizar_monto


_ALIASES = {
    "cuenta": {"cuenta", "ncuenta", "nocuenta", "numerocuenta", "codigocuenta", "cuentacontable", "codigo"},
    "fecha": {"fecha", "fechalm", "fechacontable", "fechaasiento"},
    "debe": {"debe", "debito", "cargo", "movimientodeudor"},
    "haber": {"haber", "credito", "abono", "movimientoacreedor"},
    "importe": {"importe", "monto", "valor", "importemovimiento"},
    "glosa": {"glosa", "detalle", "concepto", "nombrealfaexplicacion"},
}


def _clave(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", texto)


def proponer_mapeo(encabezados: Iterable[object]) -> dict:
    """Propuesta sin efectos secundarios; ambiguedades impiden confirmacion."""
    candidatos = {}
    for indice, encabezado in enumerate(encabezados):
        clave = _clave(encabezado)
        for campo, alias in _ALIASES.items():
            if clave in alias:
                candidatos.setdefault(campo, []).append(indice)
    ambiguos = {k: v for k, v in candidatos.items() if len(v) > 1}
    mapeo = {k: v[0] for k, v in candidatos.items() if len(v) == 1}
    tiene_importe = "importe" in mapeo
    tiene_par = "debe" in mapeo and "haber" in mapeo
    modo = "importe_firmado" if tiene_importe and not ("debe" in mapeo or "haber" in mapeo) else (
        "debe_haber" if tiene_par and not tiene_importe else "ambiguo"
    )
    requiere_revision = bool(ambiguos) or modo == "ambiguo" or not {"cuenta", "fecha"} <= mapeo.keys()
    return {"mapeo": mapeo, "modo": modo, "ambiguos": ambiguos,
            "requiere_revision": requiere_revision or modo == "importe_firmado",
            "motivo": "Confirmar polaridad del importe firmado" if modo == "importe_firmado" else None}


def separar_importe_firmado(importe: object, *, positivo_es: str) -> tuple[Decimal, Decimal]:
    """Devuelve (debe, haber) solo con convencion explicita.

    Se conserva el importe original en el registro de origen por separado.
    """
    if positivo_es not in {"debe", "haber"}:
        raise ValueError("Debe confirmarse positivo_es='debe' o positivo_es='haber'")
    monto = normalizar_monto(importe)
    if monto is None:
        raise ValueError("Importe no normalizable")
    cero = Decimal("0")
    if positivo_es == "debe":
        return max(monto, cero), max(-monto, cero)
    return max(-monto, cero), max(monto, cero)
