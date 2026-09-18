"""Pérdida esperada de cartera comercial bajo NIIF 9 (enfoque simplificado).

Qué exige la norma y cómo se refleja aquí:

- 5.5.15  Cartera comercial sin componente financiero significativo: pérdida
          esperada durante toda la vida, siempre. No hay etapas.
- B5.5.35 Matriz de provisiones por días de mora aplicada al importe en libros
          bruto (el saldo pendiente, no el valor facturado).
- B5.5.51 Las tasas históricas se ajustan por condiciones actuales y previsiones
  y 52    razonables y sustentables. Aquí ese ajuste es explícito y exige una
          justificación escrita: sin ella el cálculo se detiene.
- 5.5.17  Importe no sesgado, ponderado por probabilidad y que considera el valor
          del dinero en el tiempo.
- B5.5.44 El descuento se hace con la tasa de interés efectiva original. En
          cartera comercial de corto plazo esa tasa es cero, así que por defecto
          NO se descuenta; descontar exige tasa y horizonte por tramo.
- 5.4.4   El castigo es una baja en cuentas cuando no hay expectativa razonable
          de recuperación; no es un parámetro de horizonte.
- Los saldos con deterioro crediticio o individualmente significativos (litigios,
  concursos) se miden uno por uno y salen de la matriz colectiva.

El motor no inventa parámetros: cada tasa, LGD y ajuste entra desde afuera y se
guarda junto con el resultado para dejar trazabilidad.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# Límites del artículo 10 numeral 11 de la LORTI (Ecuador): la provisión del
# ejercicio deducible es el 1 % de los créditos comerciales pendientes, con un
# tope acumulado del 10 % de la cartera. Es un límite tributario, nunca un piso
# ni un techo de la estimación contable.
TASA_PROVISION_EJERCICIO = 0.01
TOPE_PROVISION_ACUMULADA = 0.10


def redondear(valor: float) -> float:
    """Dos decimales, medio hacia arriba (criterio contable, no bancario)."""
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _es_numero(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---------------------------------------------------------------------------
# Tasas de pérdida a partir de la experiencia histórica (cohortes)
# ---------------------------------------------------------------------------

def tasa_perdida(inicial: float, castigado: float) -> float:
    """Proporción de una cohorte que terminó impaga o castigada.

    Se sigue la cartera de un corte anterior hasta su cobro o su castigo, que es
    como deben construirse las tasas de la matriz.
    """
    if not _es_numero(inicial) or inicial <= 0:
        raise ValueError("La cohorte no tiene cartera inicial: no hay tasa que calcular")
    tasa = float(castigado) / float(inicial)
    if tasa < 0:
        # Diferencias de centésimas de centavo por coma flotante no son pérdidas.
        return 0.0 if abs(castigado) < 0.01 else tasa
    return tasa


def promediar_tasas(cohortes: list[dict[str, float]]) -> dict[str, float]:
    """Promedia la tasa de cada tramo entre varias cohortes observadas."""
    if not cohortes:
        raise ValueError("Se requiere al menos una cohorte observada")
    tramos = {t for c in cohortes for t in c}
    promedio = {}
    for tramo in tramos:
        valores = [c[tramo] for c in cohortes if tramo in c]
        promedio[tramo] = sum(valores) / len(valores)
    return promedio


# ---------------------------------------------------------------------------
# Parámetros aprobados por el auditor
# ---------------------------------------------------------------------------

@dataclass
class ParametrosECL:
    tasas_perdida: dict[str, float]
    lgd: float | dict[str, float] = 1.0
    ajuste_prospectivo: float = 0.0
    justificacion_ajuste: str = ""
    tasa_descuento: float | None = None
    horizontes: dict[str, float] | None = None
    fuente_tasas: str = ""
    notas: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for tramo, t in self.tasas_perdida.items():
            if not _es_numero(t) or not 0 <= float(t) <= 1:
                raise ValueError(f"Tasa de pérdida inválida en '{tramo}': {t!r}")
        for tramo, l in (self.lgd.items() if isinstance(self.lgd, dict) else [("todos", self.lgd)]):
            if not _es_numero(l) or not 0 <= float(l) <= 1:
                raise ValueError(f"LGD inválida en '{tramo}': {l!r}. Debe estar entre 0 y 1")
        if self.ajuste_prospectivo and not self.justificacion_ajuste.strip():
            raise ValueError(
                "El ajuste prospectivo exige justificación escrita (NIIF 9 B5.5.51-52)"
            )
        if self.tasa_descuento is not None:
            if not self.horizontes:
                raise ValueError(
                    "Descontar exige el horizonte de cada tramo; en cartera comercial de "
                    "corto plazo la tasa efectiva es cero y no se descuenta (B5.5.44)"
                )
            if not _es_numero(self.tasa_descuento) or self.tasa_descuento < 0:
                raise ValueError(f"Tasa de descuento inválida: {self.tasa_descuento!r}")

    def lgd_de(self, tramo: str) -> float:
        if isinstance(self.lgd, dict):
            if tramo not in self.lgd:
                raise ValueError(f"Falta la LGD aprobada del tramo '{tramo}'")
            return float(self.lgd[tramo])
        return float(self.lgd)


# ---------------------------------------------------------------------------
# Medición colectiva (matriz de provisiones)
# ---------------------------------------------------------------------------

def medir_ecl(exposiciones: dict[str, float], parametros: ParametrosECL) -> dict[str, Any]:
    """Aplica la matriz a la exposición de cada tramo.

    El total es la suma de los tramos ya redondeados, para que el papel de
    trabajo cuadre con lo que se ve en pantalla.
    """
    filas = []
    total = 0.0
    exposicion_total = 0.0
    sin_medir = 0.0
    for tramo, saldo in exposiciones.items():
        saldo = float(saldo or 0)
        exposicion_total += saldo
        tasa = parametros.tasas_perdida.get(tramo)
        if tasa is None:
            # Sin historia no se inventa una tasa: la banda queda sin medir y su
            # exposición se informa aparte, en vez de afirmar (con una tasa cero)
            # que no hay pérdida.
            sin_medir += saldo
            filas.append({
                "tramo": tramo,
                "exposicion": redondear(saldo),
                "tasa_perdida": None,
                "tasa_ajustada": None,
                "lgd": None,
                "horizonte": None,
                "factor_descuento": None,
                "ecl": None,
            })
            continue
        tasa_ajustada = float(tasa) * (1 + parametros.ajuste_prospectivo)
        lgd = parametros.lgd_de(tramo)
        if parametros.tasa_descuento is None:
            factor = 1.0
            t = None
        else:
            t = parametros.horizontes.get(tramo)
            if t is None:
                raise ValueError(f"Falta el horizonte del tramo '{tramo}' para descontar")
            factor = 1 / (1 + parametros.tasa_descuento) ** float(t)
        ecl = redondear(saldo * tasa_ajustada * lgd * factor)
        total += ecl
        filas.append({
            "tramo": tramo,
            "exposicion": redondear(saldo),
            "tasa_perdida": float(tasa),
            "tasa_ajustada": tasa_ajustada,
            "lgd": lgd,
            "horizonte": t,
            "factor_descuento": factor,
            "ecl": ecl,
        })

    return {
        "tramos": filas,
        "exposicion_total": redondear(exposicion_total),
        "exposicion_sin_medir": redondear(sin_medir),
        "ecl_total": redondear(total),
        "descuento_aplicado": parametros.tasa_descuento is not None,
        "ajuste_prospectivo": parametros.ajuste_prospectivo,
        "justificacion_ajuste": parametros.justificacion_ajuste,
        "fuente_tasas": parametros.fuente_tasas,
    }


# ---------------------------------------------------------------------------
# Medición individual (deterioro crediticio: litigios, concursos, acuerdos)
# ---------------------------------------------------------------------------

def evaluar_individual(casos: list[dict[str, Any]]) -> dict[str, Any]:
    """Mide uno por uno los saldos que no pueden agruparse en la matriz."""
    detalle = []
    saldo_total = 0.0
    ecl_total = 0.0
    for caso in casos:
        saldo = float(caso.get("saldo") or 0)
        recuperacion = caso.get("recuperacion_estimada")
        if recuperacion is None:
            raise ValueError(
                f"El caso '{caso.get('identificacion')}' no tiene recuperación estimada: "
                "no se puede medir sin ese dato"
            )
        recuperacion = float(recuperacion)
        if recuperacion < 0 or recuperacion > saldo:
            raise ValueError(
                f"Recuperación estimada fuera de rango en '{caso.get('identificacion')}': "
                f"{recuperacion} sobre un saldo de {saldo}"
            )
        ecl = redondear(saldo - recuperacion)
        saldo_total += saldo
        ecl_total += ecl
        detalle.append({
            "identificacion": caso.get("identificacion"),
            "tramo": caso.get("tramo"),
            "saldo": redondear(saldo),
            "recuperacion_estimada": redondear(recuperacion),
            "sustento": caso.get("sustento", ""),
            "ecl": ecl,
        })
    return {
        "casos": detalle,
        "saldo_total": redondear(saldo_total),
        "ecl_total": redondear(ecl_total),
    }


# ---------------------------------------------------------------------------
# Resumen del papel de trabajo
# ---------------------------------------------------------------------------

def resumen_deterioro(
    exposiciones: dict[str, float],
    parametros: ParametrosECL,
    casos_individuales: list[dict[str, Any]] | None = None,
    saldo_contable: float | None = None,
) -> dict[str, Any]:
    """Junta la matriz colectiva, los casos individuales, la conciliación y el
    cuadro tributario. Los saldos evaluados individualmente se descuentan de su
    tramo para no medirlos dos veces."""
    casos_individuales = casos_individuales or []
    individual = evaluar_individual(casos_individuales)

    exposiciones_colectivas = dict(exposiciones)
    for caso in individual["casos"]:
        tramo = caso.get("tramo")
        if tramo is None:
            continue
        if tramo not in exposiciones_colectivas:
            raise ValueError(f"El caso individual apunta a un tramo inexistente: '{tramo}'")
        restante = float(exposiciones_colectivas[tramo]) - caso["saldo"]
        if restante < -0.01:
            raise ValueError(
                f"Los casos individuales del tramo '{tramo}' superan su exposición"
            )
        exposiciones_colectivas[tramo] = max(restante, 0.0)

    colectivo = medir_ecl(exposiciones_colectivas, parametros)
    exposicion_total = redondear(colectivo["exposicion_total"] + individual["saldo_total"])
    ecl_total = redondear(colectivo["ecl_total"] + individual["ecl_total"])
    # Los casos individuales siempre se miden (evaluar_individual exige la
    # recuperación estimada), así que lo sin medir viene solo de la matriz
    # colectiva: bandas sin tasa aprobada.
    exposicion_sin_medir = redondear(colectivo["exposicion_sin_medir"])
    exposicion_medida = redondear(exposicion_total - exposicion_sin_medir)

    resultado: dict[str, Any] = {
        "colectivo": colectivo,
        "individual": individual,
        "exposicion_total": exposicion_total,
        "exposicion_sin_medir": exposicion_sin_medir,
        "exposicion_medida": exposicion_medida,
        "medicion_completa": exposicion_sin_medir < 0.01,
        "ecl_total": ecl_total,
        # Sobre lo medido, no sobre el total: si se calculara sobre el total,
        # una banda sin tasa diluiría el porcentaje justo cuando hay algo sin
        # medir (la misma dilución silenciosa que esta tarea evita).
        "porcentaje_sobre_cartera": (ecl_total / exposicion_medida) if exposicion_medida else 0.0,
        "tributario": {
            "limite_ejercicio_1pct": redondear(exposicion_total * TASA_PROVISION_EJERCICIO),
            "tope_acumulado_10pct": redondear(exposicion_total * TOPE_PROVISION_ACUMULADA),
            "excede_limite_ejercicio": ecl_total > exposicion_total * TASA_PROVISION_EJERCICIO,
            "nota": "Límite de deducción (LORTI art. 10 num. 11). No condiciona la "
                    "estimación contable; la diferencia es temporaria.",
        },
        "asiento_propuesto": {
            "debe": "Gasto por deterioro de cartera",
            "haber": "Provisión por pérdidas crediticias esperadas",
            "importe": ecl_total,
        },
    }
    if saldo_contable is not None:
        diferencia = redondear(exposicion_total - float(saldo_contable))
        resultado["conciliacion"] = {
            # Se compara contra el saldo contable, que es el total de la
            # cartera (medida y sin medir), no solo la parte medida.
            "cartera_total": exposicion_total,
            "saldo_contable": redondear(float(saldo_contable)),
            "diferencia": diferencia,
            "cuadra": abs(diferencia) < 0.01,
        }
    return resultado


# ---------------------------------------------------------------------------
# Registro en el motor determinístico
# ---------------------------------------------------------------------------

def ejecutar_ecl_niif9(data: dict[str, float], parameters: dict[str, Any]) -> dict[str, Any]:
    p = ParametrosECL(
        tasas_perdida=parameters["tasas_perdida"],
        lgd=parameters.get("lgd", 1.0),
        ajuste_prospectivo=parameters.get("ajuste_prospectivo", 0.0),
        justificacion_ajuste=parameters.get("justificacion_ajuste", ""),
        tasa_descuento=parameters.get("tasa_descuento"),
        horizontes=parameters.get("horizontes"),
        fuente_tasas=parameters.get("fuente_tasas", ""),
    )
    return resumen_deterioro(
        exposiciones=data,
        parametros=p,
        casos_individuales=parameters.get("casos_individuales"),
        saldo_contable=parameters.get("saldo_contable"),
    )


def registrar_en_motor(motor) -> None:
    motor.register("ECL_CXC_NIIF9", ejecutar_ecl_niif9)
