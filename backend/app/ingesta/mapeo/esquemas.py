"""Esquemas canónicos de la Capa de Mapeo Universal (Fase A3).

Un esquema describe los campos que una prueba espera de una tabla contable
(mayor, asiento de diario, balance, ventas, compras), con sus sinónimos para
que el mapeador determinista reconozca la columna venga como venga nombrada.

Regla: los sinónimos de **una sola palabra** (débito, cargo, crédito…) son
fuertes (match alto → HIGH); las **frases** de varias palabras ("movimiento
deudor") son pistas más débiles (match bajo → a la cola de revisión). Así la
máquina propone con confianza calibrada y el auditor confirma (M07).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.ingesta.contract import TipoDato, TipoDocumento


@dataclass(frozen=True)
class CampoCanonico:
    nombre: str
    tipo: TipoDato
    obligatorio: bool = False
    sinonimos: tuple[str, ...] = ()
    descripcion: str = ""


@dataclass(frozen=True)
class EsquemaCanonico:
    tipo_documento: TipoDocumento
    campos: tuple[CampoCanonico, ...]

    @property
    def obligatorios(self) -> list[CampoCanonico]:
        return [c for c in self.campos if c.obligatorio]

    def campo(self, nombre: str) -> CampoCanonico | None:
        for c in self.campos:
            if c.nombre == nombre:
                return c
        return None


# Abreviaturas de tipo para legibilidad.
_T = TipoDato.TEXTO
_M = TipoDato.MONEDA
_F = TipoDato.FECHA
_R = TipoDato.RUC


MAYOR = EsquemaCanonico(
    tipo_documento=TipoDocumento.MAYOR,
    campos=(
        CampoCanonico("cuenta", _T, True, ("codigo", "código", "cuenta contable", "código contable")),
        CampoCanonico("fecha", _F, True, ("fecha", "fecha asiento")),
        CampoCanonico("debe", _M, True, ("debito", "débito", "cargo", "movimiento deudor")),
        CampoCanonico("haber", _M, True, ("credito", "crédito", "abono", "movimiento acreedor")),
        CampoCanonico("glosa", _T, False, ("concepto", "detalle", "descripcion", "descripción", "observacion")),
        CampoCanonico("saldo", _M, False, ("saldo final", "saldo actual")),
    ),
)

ASIENTO_DIARIO = EsquemaCanonico(
    tipo_documento=TipoDocumento.ASIENTO_DIARIO,
    campos=(
        CampoCanonico("num_asiento", _T, True, ("asiento", "num asiento", "no asiento", "numero", "número", "comprobante")),
        CampoCanonico("fecha", _F, True, ("fecha", "fecha asiento")),
        CampoCanonico("cuenta", _T, True, ("codigo", "código", "cuenta contable")),
        CampoCanonico("debe", _M, True, ("debito", "débito", "cargo", "movimiento deudor")),
        CampoCanonico("haber", _M, True, ("credito", "crédito", "abono", "movimiento acreedor")),
        CampoCanonico("concepto", _T, False, ("glosa", "detalle", "descripcion", "descripción")),
        CampoCanonico("tercero", _T, False, ("razon social", "razón social", "beneficiario", "cliente", "proveedor")),
        CampoCanonico("documento", _T, False, ("num documento", "referencia", "doc")),
    ),
)

BALANCE = EsquemaCanonico(
    tipo_documento=TipoDocumento.BALANCE,
    campos=(
        CampoCanonico("cuenta", _T, True, ("codigo", "código", "cuenta contable", "código contable")),
        CampoCanonico("saldo", _M, True, ("saldo final", "valor", "monto")),
        CampoCanonico("descripcion", _T, False, ("nombre", "descripción", "concepto")),
    ),
)

VENTAS = EsquemaCanonico(
    tipo_documento=TipoDocumento.VENTAS,
    campos=(
        CampoCanonico("fecha", _F, True, ("fecha", "fecha emision", "fecha emisión")),
        CampoCanonico("tercero", _T, True, ("cliente", "razon social", "razón social", "adquirente")),
        CampoCanonico("base_imponible", _M, True, ("base", "subtotal", "base gravada")),
        CampoCanonico("ruc_cliente", _R, False, ("ruc", "ruc cliente", "identificacion", "identificación")),
        CampoCanonico("num_comprobante", _T, False, ("comprobante", "num comprobante", "factura", "secuencial")),
        CampoCanonico("tipo_comprobante", _T, False, ("tipo comprobante", "tipo documento")),
        CampoCanonico("iva", _M, False, ("iva", "impuesto", "valor iva")),
        CampoCanonico("total", _M, False, ("total", "valor total", "importe total")),
    ),
)

COMPRAS = EsquemaCanonico(
    tipo_documento=TipoDocumento.COMPRAS,
    campos=(
        CampoCanonico("fecha", _F, True, ("fecha", "fecha emision", "fecha emisión")),
        CampoCanonico("proveedor", _T, True, ("razon social", "razón social", "emisor")),
        CampoCanonico("base_imponible", _M, True, ("base", "subtotal", "base gravada")),
        CampoCanonico("ruc_proveedor", _R, False, ("ruc", "ruc proveedor", "identificacion", "identificación")),
        CampoCanonico("num_comprobante", _T, False, ("comprobante", "num comprobante", "factura", "secuencial")),
        CampoCanonico("iva", _M, False, ("iva", "impuesto", "valor iva")),
        CampoCanonico("total", _M, False, ("total", "valor total", "importe total")),
        CampoCanonico("sustento_tributario", _T, False, ("sustento", "codigo sustento", "código sustento")),
    ),
)

# Catálogo indexado por TipoDocumento (los 5 esquemas iniciales de la Fase A3).
CATALOGO_ESQUEMAS: dict[TipoDocumento, EsquemaCanonico] = {
    MAYOR.tipo_documento: MAYOR,
    ASIENTO_DIARIO.tipo_documento: ASIENTO_DIARIO,
    BALANCE.tipo_documento: BALANCE,
    VENTAS.tipo_documento: VENTAS,
    COMPRAS.tipo_documento: COMPRAS,
}


def resolver_esquema(tipo_documento) -> EsquemaCanonico:
    """Devuelve el esquema para un ``TipoDocumento`` o su valor string.

    Lanza ``KeyError`` con un mensaje claro si el tipo no tiene esquema (la
    capa de mapeo solo cubre tablas contables, no los formularios SRI rígidos).
    """
    if isinstance(tipo_documento, TipoDocumento):
        clave = tipo_documento
    else:
        clave = TipoDocumento(str(tipo_documento))  # ValueError si no existe
    if clave not in CATALOGO_ESQUEMAS:
        raise KeyError(
            f"No hay esquema de mapeo para {clave.value!r}. "
            f"Disponibles: {sorted(e.value for e in CATALOGO_ESQUEMAS)}."
        )
    return CATALOGO_ESQUEMAS[clave]
