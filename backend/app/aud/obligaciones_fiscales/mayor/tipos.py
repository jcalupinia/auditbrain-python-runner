"""Contratos entre las capas del motor de mayores.

Deliberadamente sin dependencias de SQLAlchemy ni FastAPI: el motor se
prueba sin base de datos ni servidor.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

# Columnas mínimas para poder trabajar: sin código no hay cuenta, y sin
# debe/haber no hay importes.
COLUMNAS_MINIMAS = ("codigo", "debe", "haber")


@dataclass
class Movimiento:
    """Una fila del mayor, ya normalizada."""

    codigo: str
    cuenta: str = ""
    fecha: datetime.date | None = None
    asiento: str = ""
    documento: str = ""
    identificacion: str = ""
    persona: str = ""
    descripcion: str = ""
    debe: float = 0.0
    haber: float = 0.0
    saldo: float = 0.0
    fila: int = 0

    @property
    def neto(self) -> float:
        return round(self.debe - self.haber, 2)

    @property
    def mes(self) -> str | None:
        return f"{self.fecha.month:02d}" if self.fecha else None


@dataclass
class LecturaMayor:
    """Resultado de leer un archivo de mayor."""

    movimientos: list[Movimiento] = field(default_factory=list)
    columnas_detectadas: dict[str, int] = field(default_factory=dict)
    columnas_faltantes: list[str] = field(default_factory=list)
    hoja: str = ""
    fila_encabezado: int = 0
    filas_descartadas: int = 0
    errores: list[str] = field(default_factory=list)

    @property
    def mapeo_suficiente(self) -> bool:
        return all(c in self.columnas_detectadas for c in COLUMNAS_MINIMAS)


@dataclass
class PerfilCuenta:
    """Todo lo que sabemos de una cuenta a partir de sus movimientos."""

    codigo: str
    nombre: str
    n_movimientos: int = 0
    debe: float = 0.0
    haber: float = 0.0
    por_mes: dict[str, float] = field(default_factory=dict)
    prefijos_asiento: dict[str, int] = field(default_factory=dict)
    contrapartidas: list[tuple[str, int]] = field(default_factory=list)
    descripciones: list[str] = field(default_factory=list)

    @property
    def saldo(self) -> float:
        return round(self.debe - self.haber, 2)

    @property
    def tendencia(self) -> str:
        """deudor / acreedor / neutro.

        Las cuentas de impuestos se liquidan cada mes, así que muchas quedan
        en 'neutro' (debe == haber). En ese caso la señal no debe opinar.
        """
        if round(self.debe, 2) > round(self.haber, 2):
            return "deudor"
        if round(self.haber, 2) > round(self.debe, 2):
            return "acreedor"
        return "neutro"


@dataclass(order=True)
class Senal:
    """Aporte de una señal a una categoría, con su justificación."""

    categoria: str = field(compare=False)
    puntaje: int = 0
    motivo: str = field(default="", compare=False)


@dataclass
class ResultadoClasificacion:
    codigo: str
    nombre: str
    categoria: str | None
    confianza: str  # alta | media | baja
    origen: str  # historial | reglas | declarada | manual
    tarifa: float | None = None
    puntajes: dict[str, int] = field(default_factory=dict)
    senales: list[Senal] = field(default_factory=list)

    @property
    def justificacion(self) -> list[str]:
        return [s.motivo for s in self.senales]
