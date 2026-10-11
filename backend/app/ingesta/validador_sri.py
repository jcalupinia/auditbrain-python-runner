"""Validador de coherencia SRI (herramienta nueva, Fase 9).

Chequeo PREVIO al ICT: toma los formularios SRI ya ingeridos por el motor
(F-101 anual, F-103 y F-104 mensuales) y corre cruces **deterministas** entre
ellos para que el cliente detecte inconsistencias antes de generar el ICT.

**No toca el ICT ni ninguna herramienta probada**: solo lee los
`DatasetNormalizado` que produce el motor (`adapters.extraer_f101/f103/f104`,
campos `cas_XXX` con `normalized_value` Decimal) y recalcula.

Los cruces están **fundamentados** en lo que el ICT ya calcula; no se inventan
correspondencias de casilleros:

- Ventas IR vs base IVA: F-101 (6001+6005) contra Σ de los 12 F-104 cas 411.
  (Fuente: `ict/fillers/auditoria_anexos.py` análisis del anexo A2.)
- Pagos al exterior: F-103 (402+433) dispara el requisito del ATS XML.
  (Fuente: mismo archivo, análisis del anexo A8.)

Más chequeos de completitud (cuántos formularios, parser sin datos). Estilo
**informativo** (como la hoja «VERIFICACIÓN A1»): estados CUADRA / DIFERENCIA,
nunca una conclusión tributaria. Tolerancia 0.5 USD, igual que el ICT.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from backend.app.ingesta.contract import DatasetNormalizado, TipoDocumento

# Tolerancia de cuadre (idéntica a la del ICT: verification.py).
TOLERANCIA = Decimal("0.5")
# Meses esperados de los formularios mensuales.
MESES_ESPERADOS = 12


class Chequeo(BaseModel):
    """Un cruce o control de completitud, en estilo informativo."""

    codigo: str
    titulo: str
    estado: str  # "ok" | "diferencia" | "informativo" | "faltante"
    detalle: str
    casilleros: list[str] = Field(default_factory=list)
    esperado: Optional[float] = None
    encontrado: Optional[float] = None
    diferencia: Optional[float] = None


class ReporteCoherencia(BaseModel):
    """Resultado del validador: conteo de formularios + chequeos + veredicto."""

    f101: int = 0
    f103: int = 0
    f104: int = 0
    chequeos: list[Chequeo] = Field(default_factory=list)
    resumen: str = ""
    review_required: bool = True


def _cas(ds: DatasetNormalizado, num: str) -> Optional[Decimal]:
    """Valor normalizado del casillero `num` en un dataset (o None)."""
    objetivo = f"cas_{num}"
    for c in ds.campos:
        if c.field == objetivo and isinstance(c.normalized_value, Decimal):
            return c.normalized_value
    return None


def _suma(datasets: list[DatasetNormalizado], num: str) -> Decimal:
    """Suma del casillero `num` sobre una lista de datasets (ausente = 0)."""
    total = Decimal("0")
    for ds in datasets:
        v = _cas(ds, num)
        if v is not None:
            total += v
    return total


def _f(d: Optional[Decimal]) -> Optional[float]:
    return None if d is None else float(d)


def _por_tipo(datasets: list[DatasetNormalizado], tipo: TipoDocumento) -> list[DatasetNormalizado]:
    return [d for d in datasets if d.document_type is tipo]


def validar_coherencia(datasets: list[DatasetNormalizado]) -> ReporteCoherencia:
    """Corre los cruces deterministas sobre los formularios ingeridos.

    Nunca lanza: lo que no se puede cruzar (falta un formulario, un casillero
    vacío) queda como chequeo ``informativo`` o ``faltante``, no como error.
    """
    f101 = _por_tipo(datasets, TipoDocumento.F101)
    f103 = _por_tipo(datasets, TipoDocumento.F103)
    f104 = _por_tipo(datasets, TipoDocumento.F104)
    chequeos: list[Chequeo] = []

    # --- Completitud -------------------------------------------------------
    if not f101:
        chequeos.append(Chequeo(
            codigo="F101_PRESENTE", titulo="Formulario 101 (Renta)", estado="faltante",
            detalle="No se subió el F-101. El ICT lo necesita para cuadrar el balance y las ventas.",
        ))
    chequeos.append(_completitud_mensual("F103", "Formulario 103 (Retenciones)", len(f103)))
    chequeos.append(_completitud_mensual("F104", "Formulario 104 (IVA)", len(f104)))

    # Formularios que el parser no pudo leer (quedaron sin casilleros).
    sin_datos = [d.source_file for d in datasets if not d.campos]
    if sin_datos:
        chequeos.append(Chequeo(
            codigo="PARSER_SIN_DATOS", titulo="Formularios sin datos legibles", estado="faltante",
            detalle="No se extrajeron casilleros de: " + ", ".join(sin_datos)
                    + " (¿PDF escaneado o formato no estándar?).",
        ))

    # --- Cruce 1: Ventas IR (F-101) vs base de ventas gravadas IVA (Σ F-104) ---
    chequeos.append(_cruce_ventas_ir_iva(f101, f104))

    # --- Cruce 2: Pagos al exterior (F-103) → requisito ATS -----------------
    chequeos.append(_pagos_exterior(f103))

    hay_dif = any(c.estado == "diferencia" for c in chequeos)
    hay_falta = any(c.estado == "faltante" for c in chequeos)
    if hay_dif:
        resumen = "HAY DIFERENCIAS — revíselas antes de generar el ICT"
    elif hay_falta:
        resumen = "FALTAN FORMULARIOS — complételos antes de generar el ICT"
    else:
        resumen = "TODO CUADRA — la validación del auditor sigue siendo necesaria"

    return ReporteCoherencia(
        f101=len(f101), f103=len(f103), f104=len(f104),
        chequeos=chequeos, resumen=resumen,
        review_required=hay_dif or hay_falta,
    )


def _completitud_mensual(codigo: str, titulo: str, n: int) -> Chequeo:
    if n == MESES_ESPERADOS:
        return Chequeo(codigo=f"{codigo}_COMPLETO", titulo=titulo, estado="ok",
                       detalle=f"Se subieron los {MESES_ESPERADOS} meses.",
                       esperado=float(MESES_ESPERADOS), encontrado=float(n))
    estado = "faltante" if n < MESES_ESPERADOS else "informativo"
    detalle = (f"Se subieron {n} de {MESES_ESPERADOS} meses."
               if n < MESES_ESPERADOS
               else f"Se subieron {n} formularios (más de {MESES_ESPERADOS} meses; "
                    "¿hay duplicados o sustitutivas?).")
    return Chequeo(codigo=f"{codigo}_COMPLETO", titulo=titulo, estado=estado, detalle=detalle,
                   esperado=float(MESES_ESPERADOS), encontrado=float(n))


def _cruce_ventas_ir_iva(
    f101: list[DatasetNormalizado], f104: list[DatasetNormalizado]
) -> Chequeo:
    titulo = "Ventas del IR (F-101) vs base de ventas gravadas del IVA (F-104)"
    cas = ["F101:6001", "F101:6005", "F104:411"]
    if not f101 or not f104:
        return Chequeo(
            codigo="VENTAS_IR_IVA", titulo=titulo, estado="informativo", casilleros=cas,
            detalle="No se puede cruzar: falta el F-101 o los F-104.",
        )
    ds101 = f101[0]
    ventas_ir = (_cas(ds101, "6001") or Decimal("0")) + (_cas(ds101, "6005") or Decimal("0"))
    ventas_iva = _suma(f104, "411")
    if ventas_ir <= 0 or ventas_iva <= 0:
        return Chequeo(
            codigo="VENTAS_IR_IVA", titulo=titulo, estado="informativo", casilleros=cas,
            detalle="Una de las dos bases es cero; no se marca diferencia (puede faltar un "
                    "formulario o no haber ventas gravadas).",
            esperado=_f(ventas_ir), encontrado=_f(ventas_iva),
        )
    diff = ventas_iva - ventas_ir
    cuadra = abs(diff) <= TOLERANCIA
    return Chequeo(
        codigo="VENTAS_IR_IVA", titulo=titulo,
        estado="ok" if cuadra else "diferencia", casilleros=cas,
        detalle=("Las ventas declaradas para Renta concilian con la base de ventas gravadas "
                 "del IVA (dentro de 0.5)."
                 if cuadra else
                 "Las ventas para Renta (6001+6005) NO concilian con la base de ventas "
                 "gravadas del IVA (Σ cas 411 de los F-104)."),
        esperado=_f(ventas_ir), encontrado=_f(ventas_iva), diferencia=_f(diff),
    )


def _pagos_exterior(f103: list[DatasetNormalizado]) -> Chequeo:
    titulo = "Pagos al exterior (F-103) y requisito del ATS"
    cas = ["F103:402", "F103:433"]
    if not f103:
        return Chequeo(codigo="PAGOS_EXTERIOR", titulo=titulo, estado="informativo",
                       casilleros=cas, detalle="No se subieron F-103.")
    ext = _suma(f103, "402") + _suma(f103, "433")
    if ext > 0:
        return Chequeo(
            codigo="PAGOS_EXTERIOR", titulo=titulo, estado="informativo", casilleros=cas,
            detalle=f"Se declararon pagos al exterior por USD {float(ext):,.2f} (cas 402+433). "
                    "El ICT (anexo A8) requerirá el ATS XML correspondiente.",
            encontrado=_f(ext),
        )
    return Chequeo(codigo="PAGOS_EXTERIOR", titulo=titulo, estado="ok", casilleros=cas,
                   detalle="No se declararon pagos al exterior en los F-103.", encontrado=0.0)
