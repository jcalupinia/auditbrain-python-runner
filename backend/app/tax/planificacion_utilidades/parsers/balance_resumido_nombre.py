"""Extrae un EEFF resumido por NOMBRE de concepto (ESF + ERI), con N períodos
variables y mixtos. Contrato compatible con extract_balance_interno más
`periodos_esf`, `periodos_eri`."""
from __future__ import annotations
import pandas as pd
from ..schema import INPUT_KEYS
from ..comparaciones import build_comparaciones
from .periodos import clasificar_periodo
from .mapeo_nombres import mapear_concepto
from ._shared import _read_excel
from .balance_interno import _fix_mojibake

_TITULO_ESF = ("SITUACION FINANCIERA", "SITUACIÓN FINANCIERA", "BALANCE")
_TITULO_ERI = ("RESULTADO", "RESULTADOS", "PERDIDAS Y GANANCIAS", "P Y G")


def _read(data: bytes) -> pd.DataFrame:
    xls = _read_excel(data)
    return xls.parse(xls.sheet_names[0], header=None)


def _fila_periodos(row):
    out = []
    for i, v in enumerate(row.tolist()):
        p = clasificar_periodo(v)
        if p:
            out.append((i, p))
    return out


def extract_balance_resumido_nombre(data: bytes) -> dict:
    df = _read(data)
    n = len(df)
    # localizar cabeceras de cada bloque (col A texto no-período + >=2 periodos)
    bloques = []  # (tipo, fila_cab, [(col,period)])
    for i in range(n):
        row = df.iloc[i]
        pers = _fila_periodos(row)
        a0 = row.iloc[0]
        if len(pers) >= 2 and isinstance(a0, str) and clasificar_periodo(a0) is None:
            bloques.append([i, pers])
    # asignar tipo por el título más cercano hacia arriba
    def _tipo(fila_cab):
        for j in range(fila_cab, max(-1, fila_cab - 4), -1):
            t = str(df.iloc[j, 0]).upper()
            if any(k in t for k in _TITULO_ERI):
                return "eri"
            if any(k in t for k in _TITULO_ESF):
                return "esf"
        return "esf"
    # Un ESF puede venir partido en varias cabeceras (p.ej. 'Activo' y
    # 'Pasivo y patrimonio', cada una con sus columnas de período). Se toman
    # TODOS los bloques de cada tipo, no solo el primero.
    esf_bloques = [b for b in bloques if _tipo(b[0]) == "esf"]
    eri_bloques = [b for b in bloques if _tipo(b[0]) == "eri"]
    esf = esf_bloques[0] if esf_bloques else None
    eri = eri_bloques[0] if eri_bloques else None

    per_esf = [p for _c, p in (esf[1] if esf else [])]
    per_eri = [p for _c, p in (eri[1] if eri else [])]
    ncols = max(len(per_esf), len(per_eri), 1)
    data_out = {k: [0.0] * ncols for k in INPUT_KEYS}
    warnings: list[str] = []

    def _fin_bloque(fila_cab):
        for b in bloques:
            if b[0] > fila_cab:
                return b[0]
        return n

    # Índice canónico por LABEL de período para cada estado. Cuando un ESF viene
    # partido en varios bloques (Activo / Pasivo+Patrimonio) las columnas de cada
    # bloque pueden venir en distinto orden; se asigna cada valor al índice del
    # período que le corresponde por su label, no por su posición en el bloque.
    idx_esf = {p["label"]: k for k, p in enumerate(per_esf)}
    idx_eri = {p["label"]: k for k, p in enumerate(per_eri)}

    def _cargar(bloque, idx_canonico):
        if not bloque:
            return {}
        cab, cols = bloque
        # Mapa columna-del-bloque -> índice canónico (por label). Si un bloque
        # trae un período que no está en el estado, se avisa y se descarta.
        col_a_canon = {}
        for c, per in cols:
            lab = per["label"]
            if lab in idx_canonico:
                col_a_canon[c] = idx_canonico[lab]
            else:
                warnings.append(
                    f"Período '{lab}' del bloque en fila {cab + 1} no está en el "
                    f"estado; sus valores se ignoran para no cruzar columnas."
                )
        totales = {}  # (seccion) -> [vals por índice canónico]
        for i in range(cab + 1, _fin_bloque(cab)):
            nombre = df.iloc[i, 0]
            if not isinstance(nombre, str) or not nombre.strip():
                continue
            nombre = _fix_mojibake(nombre)
            sec, key = mapear_concepto(nombre)
            if sec is None:
                warnings.append(f"Concepto no mapeado: '{nombre.strip()}'")
                continue
            if sec == "total":
                tvals = [0.0] * ncols
                for c, _per in cols:
                    yi = col_a_canon.get(c)
                    if yi is None:
                        continue
                    cell = df.iloc[i, c]
                    v = float(cell) if pd.notna(cell) and isinstance(cell, (int, float)) else 0.0
                    tvals[yi] += v
                totales[nombre.strip().upper()] = tvals
                continue
            for c, _per in cols:
                yi = col_a_canon.get(c)
                if yi is None or yi >= ncols or key not in data_out:
                    continue
                cell = df.iloc[i, c]
                v = float(cell) if pd.notna(cell) and isinstance(cell, (int, float)) else 0.0
                data_out[key][yi] += v
        return totales

    tot_esf: dict = {}
    for b in esf_bloques:
        tot_esf.update(_cargar(b, idx_esf))
    for b in eri_bloques:
        _cargar(b, idx_eri)

    # cuadre ESF: TOTAL ACTIVOS vs TOTAL PASIVO + PATRIMONIO por período.
    # Se busca el GRAN total, no un subtotal 'corriente/no corriente': para
    # el activo se prefiere la clave que contiene 'ACTIVO' pero NO 'CORRIENTE'.
    def _gran_total(pred_incluye, pred_excluye=()):
        candidatos = [
            (k, v) for k, v in tot_esf.items()
            if pred_incluye in k and not any(x in k for x in pred_excluye)
        ]
        if not candidatos:
            candidatos = [(k, v) for k, v in tot_esf.items() if pred_incluye in k]
        return candidatos[-1][1] if candidatos else None

    ta = _gran_total("ACTIVO", ("CORRIENTE",))
    tpp = _gran_total("PATRIMONIO")
    if ta and tpp:
        for yi in range(min(len(ta), len(tpp))):
            dif = round(ta[yi] - tpp[yi], 2)
            if abs(dif) > 0.01:
                lab = per_esf[yi]["label"] if yi < len(per_esf) else str(yi)
                warnings.append(f"Descuadre en {lab}: Activo − (Pasivo+Patrimonio) = {dif:,.2f}")

    comparaciones = {
        "esf": [list(par) for par in build_comparaciones(
            [p["label"] for p in per_esf], [p["tipo"] for p in per_esf], "esf")],
        "eri": [list(par) for par in build_comparaciones(
            [p["label"] for p in per_eri], [p["tipo"] for p in per_eri], "eri")],
    }

    return {
        "data": data_out,
        "detalle": [],
        "params": {},
        "warnings": warnings,
        "comparaciones": comparaciones,
        "source": "resumido_nombre",
        "periodos_esf": per_esf,
        "periodos_eri": per_eri,
        "labels_esf": [p["label"] for p in per_esf],
        "labels_er": [p["label"] for p in per_eri],
        "anios_detectados": [p["anio"] for p in (per_esf or per_eri)],
        "anio_detectado": (per_esf or per_eri)[-1]["anio"] if (per_esf or per_eri) else None,
    }
