"""Validador de coherencia SRI (Fase 9) — lógica pura de cruces.

Verifica los cruces FUNDAMENTADOS (ventas IR vs base IVA, pagos al exterior) y
los controles de completitud, con datasets sintéticos del contrato del motor.
No toca el ICT ni ninguna herramienta existente.
"""
from __future__ import annotations

from decimal import Decimal

from backend.app.ingesta.contract import CampoExtraido, DatasetNormalizado, TipoDocumento
from backend.app.ingesta.validador_sri import validar_coherencia


def _ds(tipo: TipoDocumento, cas: dict[str, str], nombre: str) -> DatasetNormalizado:
    campos = [
        CampoExtraido(document_id=nombre, document_type=tipo, field=f"cas_{n}",
                      raw_value=v, normalized_value=Decimal(v))
        for n, v in cas.items()
    ]
    return DatasetNormalizado(dataset_id=nombre, source_file=nombre, document_type=tipo, campos=campos)


def _f101(c6001, c6005, nombre="F101_2025.pdf"):
    return _ds(TipoDocumento.F101, {"6001": c6001, "6005": c6005}, nombre)


def _f104(c411, mes):
    return _ds(TipoDocumento.F104, {"411": c411}, f"F104_2025_{mes:02d}.pdf")


def _f103(c402="0", c433="0", mes=1):
    return _ds(TipoDocumento.F103, {"402": c402, "433": c433}, f"F103_2025_{mes:02d}.pdf")


def _ch(rep, codigo):
    return next(c for c in rep.chequeos if c.codigo == codigo)


class TestVentasIrIva:
    def test_cuadra_dentro_de_tolerancia(self):
        f101 = _f101("100000.00", "50000.00")           # ventas IR = 150000
        f104 = [_f104("12500.00", m) for m in range(1, 13)]  # Σ411 = 150000
        rep = validar_coherencia([f101, *f104])
        ch = _ch(rep, "VENTAS_IR_IVA")
        assert ch.estado == "ok"
        assert ch.esperado == 150000.0 and ch.encontrado == 150000.0

    def test_diferencia_fuera_de_tolerancia(self):
        f101 = _f101("100000.00", "50000.00")           # 150000
        f104 = [_f104("12000.00", m) for m in range(1, 13)]  # 144000
        rep = validar_coherencia([f101, *f104])
        ch = _ch(rep, "VENTAS_IR_IVA")
        assert ch.estado == "diferencia"
        assert ch.diferencia == -6000.0
        assert rep.review_required is True
        assert "DIFERENCIAS" in rep.resumen

    def test_una_base_en_cero_no_marca_diferencia(self):
        f101 = _f101("0", "0")
        f104 = [_f104("12500.00", m) for m in range(1, 13)]
        rep = validar_coherencia([f101, *f104])
        assert _ch(rep, "VENTAS_IR_IVA").estado == "informativo"

    def test_sin_f104_no_cruza(self):
        rep = validar_coherencia([_f101("100000", "0")])
        assert _ch(rep, "VENTAS_IR_IVA").estado == "informativo"


class TestCompletitud:
    def test_doce_meses_ok(self):
        f104 = [_f104("1", m) for m in range(1, 13)]
        rep = validar_coherencia([_f101("1", "0"), *f104])
        assert _ch(rep, "F104_COMPLETO").estado == "ok"
        assert rep.f104 == 12

    def test_faltan_meses(self):
        f104 = [_f104("1", m) for m in range(1, 6)]  # 5 de 12
        rep = validar_coherencia([_f101("1", "0"), *f104])
        ch = _ch(rep, "F104_COMPLETO")
        assert ch.estado == "faltante"
        assert ch.encontrado == 5.0
        assert "FALTAN" in rep.resumen or rep.review_required

    def test_falta_f101(self):
        rep = validar_coherencia([_f104("1", 1)])
        assert _ch(rep, "F101_PRESENTE").estado == "faltante"
        assert rep.review_required is True

    def test_parser_sin_datos(self):
        vacio = DatasetNormalizado(dataset_id="x.pdf", source_file="x.pdf",
                                   document_type=TipoDocumento.F104, campos=[])
        rep = validar_coherencia([_f101("1", "0"), vacio])
        assert _ch(rep, "PARSER_SIN_DATOS").estado == "faltante"


class TestPagosExterior:
    def test_pagos_exterior_recuerda_ats(self):
        f103 = [_f103(c402="3000.00", c433="1000.00", mes=m) for m in range(1, 13)]
        rep = validar_coherencia([_f101("1", "0"), *f103])
        ch = _ch(rep, "PAGOS_EXTERIOR")
        assert ch.estado == "informativo"
        assert ch.encontrado == 48000.0  # (3000+1000) * 12
        assert "ATS" in ch.detalle

    def test_sin_pagos_exterior_ok(self):
        f103 = [_f103(mes=m) for m in range(1, 13)]
        rep = validar_coherencia([_f101("1", "0"), *f103])
        assert _ch(rep, "PAGOS_EXTERIOR").estado == "ok"
