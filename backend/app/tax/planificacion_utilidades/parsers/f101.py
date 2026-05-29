"""Extractor del Formulario 101 (Impuesto a la Renta Sociedades, SRI Ecuador).

Lee el PDF, extrae los casilleros del mapeo F101_MAP y los agrega a las claves
ESF/ER. El F-101 es de UN ejercicio: el valor se coloca en la columna del año
detectado (si cae dentro de ANIOS) o, por defecto, en la última columna.
"""

from __future__ import annotations

from io import BytesIO

import pdfplumber

from backend.app.tax.planificacion_utilidades import schema
from backend.app.tax.planificacion_utilidades.mapping import F101_MAP
from backend.app.tax.planificacion_utilidades.parsers import sri_text


def extract_f101(pdf_bytes: bytes) -> dict:
    """Devuelve {data, params, warnings, casilleros_leidos, source}.

    - data: {key: [y0, y1, y2]} con None donde no hay dato (el frontend
      fusiona solo los valores no nulos).
    - params: {empresa, ruc} detectados (vacío si no se hallan).
    - warnings: avisos para validación humana.
    - casilleros_leidos: {casillero: valor} efectivamente leídos del PDF.
    """
    warnings: list[str] = [
        "Mapeo de casilleros F-101 es un DEFAULT editable: la numeración varía "
        "por versión del formulario. Verifique las celdas azules antes de usar.",
    ]

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return _empty_result(["No se pudo abrir el PDF del Formulario 101."])
    if not text.strip():
        return _empty_result(["El PDF no contiene texto extraíble (¿escaneado?)."])

    anio = sri_text.find_anio(text)
    col = schema.ANIOS.index(anio) if anio in schema.ANIOS else len(schema.ANIOS) - 1

    casilleros_leidos: dict[str, float] = {}
    data: dict[str, list] = {k: [None, None, None] for k in schema.INPUT_KEYS}
    sin_dato: list[str] = []

    for key, casilleros in F101_MAP.items():
        total = 0.0
        encontrado = False
        for cas in casilleros:
            val = sri_text.find_casillero_value(text, cas)
            if val is not None:
                casilleros_leidos[cas] = val
                total += val
                encontrado = True
        if encontrado:
            data[key][col] = round(total, 2)
        elif casilleros:
            sin_dato.append(key)

    if sin_dato:
        warnings.append(
            "Sin valor detectado para: "
            + ", ".join(schema.LABELS.get(k, k) for k in sin_dato)
            + ". Complete a mano si corresponde."
        )

    params: dict[str, str] = {}
    ruc = sri_text.find_ruc(text)
    if ruc:
        params["ruc"] = ruc
    razon = sri_text.find_label_value(text, "Razón Social") or \
        sri_text.find_label_value(text, "Razon Social")
    if razon:
        params["empresa"] = razon

    return {
        "data": data,
        "params": params,
        "warnings": warnings,
        "casilleros_leidos": casilleros_leidos,
        "source": "f101",
        "anio_detectado": anio,
    }


def _empty_result(warnings: list[str]) -> dict:
    return {
        "data": {k: [None, None, None] for k in schema.INPUT_KEYS},
        "params": {},
        "warnings": warnings,
        "casilleros_leidos": {},
        "source": "f101",
        "anio_detectado": None,
    }
