"""Capa de Mapeo Universal (Fase A3) — 10 casos + mutación (M20).

Datos ficticios (M14/M35): ninguna cifra de cliente entra al repo. Cubre el
flujo determinista proponer → [confirmar] → aplicar, la detección de encabezado
generalizada, los formatos regionales y las reglas duras (M22).
"""
from __future__ import annotations

import io
from dataclasses import replace
from decimal import Decimal

import pytest

from backend.app.ingesta.confidence import NivelConfianza, requiere_revision
from backend.app.ingesta.contract import MetodoExtraccion, TipoDocumento
from backend.app.ingesta.mapeo import (
    aplicar_mapeo,
    cola_revision_mapeo,
    perfilar,
    preparar_mapeo,
    proponer_mapeo,
)
from backend.app.ingesta.mapeo.esquemas import ASIENTO_DIARIO, MAYOR, resolver_esquema


def _xlsx(filas) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for fila in filas:
        ws.append(list(fila))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _confirmar(prop):
    """Deriva el mapeo confirmado de la propuesta (el auditor acepta tal cual)."""
    return {p.campo_canonico: p.columna_indice for p in prop.propuestas}


def _prop(prop, campo):
    return next((p for p in prop.propuestas if p.campo_canonico == campo), None)


MAYOR_OK = [
    ["Cuenta", "Fecha", "Debe", "Haber"],
    ["1.1.01.001", "2025-01-05", "100.00", "0"],
    ["4.1.01.001", "2025-01-05", "0", "100.00"],
    ["1.1.02.001", "2025-02-10", "250.50", "0"],
]


# --------------------------------------------------------------------------- #
# 1 · Mayor estándar → propuesta HIGH, cola vacía
# --------------------------------------------------------------------------- #
def test_caso1_mayor_estandar_high_sin_cola():
    perfil, prop = preparar_mapeo(_xlsx(MAYOR_OK), "mayor.xlsx", TipoDocumento.MAYOR)
    assert perfil.fila_encabezado == 0
    for campo in ("cuenta", "fecha", "debe", "haber"):
        p = _prop(prop, campo)
        assert p is not None and p.confianza is NivelConfianza.HIGH, campo
    assert prop.campos_sin_cubrir == []
    assert prop.review_required is False
    assert cola_revision_mapeo(prop) == []


# --------------------------------------------------------------------------- #
# 2 · "Movimiento Deudor/Acreedor" → LOW a la cola; tras confirmar, dataset OK
# --------------------------------------------------------------------------- #
def test_caso2_sinonimos_frase_van_a_cola_y_luego_ok():
    filas = [
        ["Cuenta", "Fecha", "Movimiento Deudor", "Movimiento Acreedor"],
        ["1.1.01.001", "2025-01-05", "100.00", "0"],
        ["4.1.01.001", "2025-01-05", "0", "100.00"],
    ]
    perfil, prop = preparar_mapeo(_xlsx(filas), "mayor.xlsx", TipoDocumento.MAYOR)
    debe, haber = _prop(prop, "debe"), _prop(prop, "haber")
    assert debe is not None and haber is not None
    assert requiere_revision(debe.confianza) and requiere_revision(haber.confianza)
    assert prop.review_required is True
    assert {it.field for it in cola_revision_mapeo(prop)} >= {"debe", "haber"}

    ds = aplicar_mapeo(perfil.filas, perfil, _confirmar(prop), MAYOR,
                       source_file="mayor.xlsx", document_type=TipoDocumento.MAYOR)
    assert ds.row_count == 2
    assert ds.mapping["debe"] == "Movimiento Deudor"
    assert ds.sello and ds.sello.sha256


# --------------------------------------------------------------------------- #
# 3 · Columnas en otro orden → mismo resultado (no depende del orden)
# --------------------------------------------------------------------------- #
def test_caso3_orden_de_columnas_indiferente():
    filas = [
        ["Debe", "Haber", "Cuenta", "Fecha"],
        ["100.00", "0", "1.1.01.001", "2025-01-05"],
    ]
    _perfil, prop = preparar_mapeo(_xlsx(filas), "mayor.xlsx", TipoDocumento.MAYOR)
    assert _prop(prop, "debe").columna_indice == 0
    assert _prop(prop, "haber").columna_indice == 1
    assert _prop(prop, "cuenta").columna_indice == 2
    assert _prop(prop, "fecha").columna_indice == 3
    assert prop.review_required is False


# --------------------------------------------------------------------------- #
# 4 · Asiento de diario → esquema ASIENTO; mapea los 5 obligatorios
# --------------------------------------------------------------------------- #
def test_caso4_asiento_de_diario():
    filas = [
        ["Asiento", "Fecha", "Cuenta", "Debe", "Haber", "Concepto"],
        ["A-001", "2025-01-05", "1.1.01.001", "100.00", "0", "Compra"],
        ["A-001", "2025-01-05", "2.1.01.001", "0", "100.00", "Compra"],
    ]
    perfil, prop = preparar_mapeo(_xlsx(filas), "asiento.xlsx", TipoDocumento.ASIENTO_DIARIO)
    for campo in ("num_asiento", "fecha", "cuenta", "debe", "haber"):
        assert _prop(prop, campo) is not None, campo
    assert prop.campos_sin_cubrir == []
    ds = aplicar_mapeo(perfil.filas, perfil, _confirmar(prop), ASIENTO_DIARIO,
                       source_file="asiento.xlsx", document_type=TipoDocumento.ASIENTO_DIARIO)
    assert ds.document_type is TipoDocumento.ASIENTO_DIARIO
    assert ds.row_count == 2


# --------------------------------------------------------------------------- #
# 5 · Falta columna obligatoria (sin "haber") → sin_cubrir + review, no avanza
# --------------------------------------------------------------------------- #
def test_caso5_falta_obligatoria():
    filas = [
        ["Cuenta", "Fecha", "Debe"],
        ["1.1.01.001", "2025-01-05", "100.00"],
    ]
    _perfil, prop = preparar_mapeo(_xlsx(filas), "mayor.xlsx", TipoDocumento.MAYOR)
    assert "haber" in prop.campos_sin_cubrir
    assert prop.review_required is True
    assert any(it.field == "haber" for it in cola_revision_mapeo(prop))


# --------------------------------------------------------------------------- #
# 6 · Celda de monto vacía → normalized_value=None, revisión, NUNCA cero (M22)
# --------------------------------------------------------------------------- #
def test_caso6_celda_vacia_no_es_cero_m22():
    filas = [
        ["Cuenta", "Fecha", "Debe", "Haber"],
        ["1.1.01.001", "2025-01-05", "", "0"],   # Debe vacío
    ]
    perfil, prop = preparar_mapeo(_xlsx(filas), "mayor.xlsx", TipoDocumento.MAYOR)
    ds = aplicar_mapeo(perfil.filas, perfil, _confirmar(prop), MAYOR,
                       source_file="mayor.xlsx", document_type=TipoDocumento.MAYOR)
    debe = [c for c in ds.campos if c.field == "debe"][0]
    assert debe.normalized_value is None          # NO cero
    assert debe.normalized_value != 0
    assert debe.confidence is NivelConfianza.REVIEW_REQUIRED
    assert any("M22" in w for w in debe.warnings)
    assert ds.rows[0]["debe"] is None
    assert ds.review_required is True


# --------------------------------------------------------------------------- #
# 7 · Encabezado en fila 8 (precedido de logos/títulos) → fila correcta
# --------------------------------------------------------------------------- #
def test_caso7_encabezado_en_fila_8():
    filas = [
        ["ACME AUDITORES S.A."],
        ["Libro Mayor General"],
        ["RUC: 9999999999001"],
        [""],
        ["Ejercicio 2025"],
        ["Expresado en USD"],
        [""],
        ["Cuenta", "Fecha", "Debe", "Haber"],   # índice 7 = fila 8
        ["1.1.01.001", "2025-01-05", "100.00", "0"],
        ["4.1.01.001", "2025-01-05", "0", "100.00"],
    ]
    perfil = perfilar(_xlsx(filas), "mayor.xlsx")
    assert perfil.fila_encabezado == 7
    assert [c.nombre_crudo for c in perfil.columnas] == ["Cuenta", "Fecha", "Debe", "Haber"]


# --------------------------------------------------------------------------- #
# 8 · CSV con ';' y coma decimal → lee bien; montos normalizados
# --------------------------------------------------------------------------- #
def test_caso8_csv_delimitador_y_coma_decimal():
    csv_bytes = (
        "Cuenta;Fecha;Debe;Haber\n"
        "1101;05/01/2025;1.234,56;0,00\n"
        "4101;05/01/2025;0,00;1.234,56\n"
    ).encode("utf-8")
    perfil, prop = preparar_mapeo(csv_bytes, "mayor.csv", TipoDocumento.MAYOR)
    assert len(perfil.columnas) == 4
    ds = aplicar_mapeo(perfil.filas, perfil, _confirmar(prop), MAYOR,
                       source_file="mayor.csv", document_type=TipoDocumento.MAYOR)
    assert float(ds.rows[0]["debe"]) == 1234.56
    assert float(ds.rows[1]["haber"]) == 1234.56


# --------------------------------------------------------------------------- #
# 9 · Export de BD con headers técnicos → perfila; lo que no, a la cola
# --------------------------------------------------------------------------- #
def test_caso9_export_bd_headers_tecnicos():
    filas = [
        ["COD_CTA", "FEC_MOV", "VAL_DEB", "VAL_HAB"],
        ["110101", "2025-01-05", "100.00", "0"],
    ]
    perfil, prop = preparar_mapeo(_xlsx(filas), "export.xlsx", TipoDocumento.MAYOR)
    assert len(perfil.columnas) == 4              # perfila igual
    assert prop.review_required is True           # no reconoce todo con confianza
    assert len(prop.campos_sin_cubrir) > 0        # obligatorios sin columna clara


# --------------------------------------------------------------------------- #
# 10 · MUTACIÓN (M20): quitar un sinónimo cambia el resultado → el caso 2 caería
# --------------------------------------------------------------------------- #
def test_caso10_mutacion_sinonimo_rompe_el_caso2():
    filas = [
        ["Cuenta", "Fecha", "Movimiento Deudor", "Movimiento Acreedor"],
        ["1.1.01.001", "2025-01-05", "100.00", "0"],
    ]
    perfil = perfilar(_xlsx(filas), "mayor.xlsx")

    # Esquema REAL: "movimiento deudor/acreedor" son sinónimos → debe/haber se proponen.
    real = proponer_mapeo(perfil, MAYOR)
    assert _prop(real, "debe") is not None and _prop(real, "haber") is not None

    # Esquema MUTADO: se elimina el sinónimo de frase. Si la suite NO lo nota,
    # no está verificando nada. DEBE cambiar: debe/haber quedan sin cubrir.
    campos_mut = tuple(
        replace(c, sinonimos=tuple(s for s in c.sinonimos if "movimiento" not in s))
        if c.nombre in ("debe", "haber") else c
        for c in MAYOR.campos
    )
    esquema_mut = replace(MAYOR, campos=campos_mut)
    mutado = proponer_mapeo(perfil, esquema_mut)
    assert _prop(mutado, "debe") is None and _prop(mutado, "haber") is None
    assert "debe" in mutado.campos_sin_cubrir and "haber" in mutado.campos_sin_cubrir
    # La mutación cambia el veredicto: prueba de que el sinónimo importa (M20).
    assert mutado.campos_sin_cubrir != real.campos_sin_cubrir


# --------------------------------------------------------------------------- #
# Extra · método TABLA y resolver_esquema
# --------------------------------------------------------------------------- #
def test_metodo_tabla_y_resolver_esquema():
    assert resolver_esquema("mayor") is MAYOR
    assert resolver_esquema(TipoDocumento.ASIENTO_DIARIO) is ASIENTO_DIARIO
    with pytest.raises((KeyError, ValueError)):
        resolver_esquema("f101")  # los formularios rígidos no son del mapeo
    perfil, prop = preparar_mapeo(_xlsx(MAYOR_OK), "mayor.xlsx", TipoDocumento.MAYOR)
    ds = aplicar_mapeo(perfil.filas, perfil, _confirmar(prop), MAYOR,
                       source_file="mayor.xlsx", document_type=TipoDocumento.MAYOR)
    assert all(c.extraction_method is MetodoExtraccion.TABLA for c in ds.campos)
