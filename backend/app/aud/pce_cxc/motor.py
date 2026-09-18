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
        if not _es_numero(self.ajuste_prospectivo):
            raise ValueError(
                f"Ajuste prospectivo inválido: {self.ajuste_prospectivo!r}. Indique el factor "
                "prospectivo como un número (1,00 = sin ajuste; 1,10 = 10 % más de pérdida)."
            )
        if 1 + float(self.ajuste_prospectivo) < 0:
            raise ValueError(
                f"El factor prospectivo no puede ser negativo: se pidió "
                f"{1 + float(self.ajuste_prospectivo):.3f}. Un factor negativo invertiría el signo "
                "de la pérdida esperada. Indique un factor mayor o igual a 0,000 "
                "(1,000 = sin ajuste)."
            )
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

    Dos cotas de la norma se aplican tramo a tramo y se declaran, nunca se
    aplican en silencio:

    - PISO CERO: la corrección de valor no puede ser negativa. Una nota de
      crédito deja la banda con exposición negativa, y sin piso su "pérdida"
      negativa neutralizaría la pérdida medida en las demás bandas del mismo
      segmento (una NC no genera "ganancia esperada").
    - TECHO DEL IMPORTE EN LIBROS BRUTO (B5.5.35): ni la tasa ajustada por el
      factor prospectivo puede superar el 100 %, ni la PCE de la banda puede
      superar su exposición.

    Cada tramo lleva `tasa_ajustada_sin_acotar`, `ecl_sin_acotar` y `acotado`
    (`None`, `"piso_cero"`, `"tasa_maxima"` o `"techo_exposicion"`), y el
    resultado totaliza `exposicion_negativa`, `ecl_acotada_por_piso` y
    `ecl_acotada_por_techo`.
    """
    filas = []
    total = 0.0
    exposicion_total = 0.0
    sin_medir = 0.0
    exposicion_negativa = 0.0
    acotada_piso = 0.0
    acotada_techo = 0.0
    for tramo, saldo in exposiciones.items():
        saldo = float(saldo or 0)
        exposicion_total += saldo
        if saldo < 0:
            exposicion_negativa += saldo
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
                "tasa_ajustada_sin_acotar": None,
                "lgd": None,
                "horizonte": None,
                "factor_descuento": None,
                "ecl": None,
                "ecl_sin_acotar": None,
                "acotado": None,
            })
            continue
        tasa_ajustada_bruta = float(tasa) * (1 + parametros.ajuste_prospectivo)
        tasa_ajustada = min(tasa_ajustada_bruta, 1.0)
        lgd = parametros.lgd_de(tramo)
        if parametros.tasa_descuento is None:
            factor = 1.0
            t = None
        else:
            t = parametros.horizontes.get(tramo)
            if t is None:
                raise ValueError(f"Falta el horizonte del tramo '{tramo}' para descontar")
            factor = 1 / (1 + parametros.tasa_descuento) ** float(t)
        # `ecl_sin_acotar` conserva lo que daría el cálculo puro; `ecl` aplica
        # el piso y el techo de la norma, y `acotado` dice cuál actuó.
        ecl_sin_acotar = redondear(saldo * tasa_ajustada_bruta * lgd * factor)
        techo = max(redondear(saldo), 0.0)
        ecl = min(max(redondear(saldo * tasa_ajustada * lgd * factor), 0.0), techo)
        acotado = None
        if ecl_sin_acotar < ecl - 0.0001:
            acotado = "piso_cero"
            acotada_piso += ecl - ecl_sin_acotar
        elif ecl_sin_acotar > ecl + 0.0001:
            acotado = "tasa_maxima" if tasa_ajustada_bruta > 1.0 else "techo_exposicion"
            acotada_techo += ecl_sin_acotar - ecl
        total += ecl
        filas.append({
            "tramo": tramo,
            "exposicion": redondear(saldo),
            "tasa_perdida": float(tasa),
            "tasa_ajustada": tasa_ajustada,
            "tasa_ajustada_sin_acotar": tasa_ajustada_bruta,
            "lgd": lgd,
            "horizonte": t,
            "factor_descuento": factor,
            "ecl": ecl,
            "ecl_sin_acotar": ecl_sin_acotar,
            "acotado": acotado,
        })

    return {
        "tramos": filas,
        "exposicion_total": redondear(exposicion_total),
        "exposicion_sin_medir": redondear(sin_medir),
        "exposicion_negativa": redondear(exposicion_negativa),
        "ecl_acotada_por_piso": redondear(acotada_piso),
        "ecl_acotada_por_techo": redondear(acotada_techo),
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
    """Mide uno por uno los saldos que no pueden agruparse en la matriz.

    Cada caso llega con su recuperación estimada (`recuperacion_estimada`) o,
    si el llamador ya midió la pérdida, con ella directamente (`ecl`, que manda
    sobre la recuperación).

    Rigen las mismas cotas que en la matriz: la corrección de valor de un caso
    no puede ser negativa ni superar su importe en libros bruto. Un cliente con
    saldo neto acreedor (una nota de crédito mayor que sus facturas), o cuya
    pérdida provisional salió negativa por esa misma nota de crédito, se mide en
    0,00 y se declara con `acotado`, en vez de abortar la corrida. Lo que sí
    sigue siendo un error es una recuperación estimada MAYOR que el saldo: ese
    dato lo carga una persona y no tiene lectura válida.
    """
    detalle = []
    saldo_total = 0.0
    ecl_total = 0.0
    acotada_piso = 0.0
    acotada_techo = 0.0
    sin_tasa_total = 0.0
    for caso in casos:
        saldo = float(caso.get("saldo") or 0)
        techo = max(redondear(saldo), 0.0)
        if caso.get("ecl") is not None:
            ecl_sin_acotar = redondear(float(caso["ecl"]))
        else:
            recuperacion = caso.get("recuperacion_estimada")
            if recuperacion is None:
                raise ValueError(
                    f"El caso '{caso.get('identificacion')}' no tiene recuperación estimada: "
                    "no se puede medir sin ese dato"
                )
            recuperacion = float(recuperacion)
            ecl_sin_acotar = redondear(saldo - recuperacion)
            if ecl_sin_acotar < -0.005:
                raise ValueError(
                    f"Recuperación estimada fuera de rango en '{caso.get('identificacion')}': "
                    f"{recuperacion:,.2f} sobre un saldo de {saldo:,.2f}. La recuperación estimada "
                    f"no puede superar el saldo del cliente: indique un importe entre 0,00 y "
                    f"{techo:,.2f}."
                )
        ecl = min(max(ecl_sin_acotar, 0.0), techo)
        acotado = None
        if ecl_sin_acotar < ecl - 0.0001:
            acotado = "piso_cero"
            acotada_piso += ecl - ecl_sin_acotar
        elif ecl_sin_acotar > ecl + 0.0001:
            acotado = "techo_saldo"
            acotada_techo += ecl_sin_acotar - ecl
        saldo_total += saldo
        ecl_total += ecl
        # Parte del saldo del caso que no se pudo medir (banda sin tasa y sin
        # estimación propia justificada). Va como campo propio, no solo dentro
        # del texto de `sustento`, para que se pueda sumar sin tener que
        # parsear una frase.
        sin_tasa = redondear(float(caso.get("saldo_sin_tasa") or 0.0))
        sin_tasa_total += sin_tasa
        detalle.append({
            "identificacion": caso.get("identificacion"),
            "tramo": caso.get("tramo"),
            "saldo": redondear(saldo),
            "recuperacion_estimada": redondear(saldo - ecl),
            "sustento": caso.get("sustento", ""),
            "saldo_sin_tasa": sin_tasa,
            "ecl": ecl,
            "ecl_sin_acotar": ecl_sin_acotar,
            "acotado": acotado,
        })
    return {
        "casos": detalle,
        "saldo_total": redondear(saldo_total),
        "ecl_total": redondear(ecl_total),
        "ecl_acotada_por_piso": redondear(acotada_piso),
        "ecl_acotada_por_techo": redondear(acotada_techo),
        # Saldo evaluado individualmente que quedó SIN MEDIR: su pérdida
        # provisional es 0,00 porque su banda no tiene tasa, no porque no haya
        # pérdida. Se totaliza aquí para que el resumen lo descuente de la
        # cartera medida en vez de darla por medida.
        "saldo_sin_tasa_total": redondear(sin_tasa_total),
    }


# ---------------------------------------------------------------------------
# Resumen del papel de trabajo
# ---------------------------------------------------------------------------

def _consolidar_colectivo(
    medidos: dict[str, dict[str, Any]],
    parametros: dict[str, ParametrosECL],
) -> dict[str, Any]:
    """Une las matrices de todos los segmentos en un solo cuadro colectivo.

    Cada fila conserva su segmento, y los agregados (exposición, pérdida,
    acotamientos) se suman. `ajuste_prospectivo` sale como diccionario
    segmento -> FACTOR (1,00 = sin ajuste), que es la forma que consume
    `01-Parametros` del papel de trabajo.
    """
    tramos: list[dict[str, Any]] = []
    totales = {"exposicion_total": 0.0, "exposicion_sin_medir": 0.0, "exposicion_negativa": 0.0,
               "ecl_acotada_por_piso": 0.0, "ecl_acotada_por_techo": 0.0, "ecl_total": 0.0}
    for segmento, medido in medidos.items():
        for t in medido["tramos"]:
            tramos.append({**t, "segmento": segmento})
        for clave in totales:
            totales[clave] += medido[clave]
    primero = next(iter(parametros.values()))
    return {
        "tramos": tramos,
        **{clave: redondear(valor) for clave, valor in totales.items()},
        "descuento_aplicado": any(m["descuento_aplicado"] for m in medidos.values()),
        "ajuste_prospectivo": {s: p.ajuste_prospectivo + 1.0 for s, p in parametros.items()},
        "justificacion_ajuste": primero.justificacion_ajuste,
        "fuente_tasas": primero.fuente_tasas,
    }


def _deducir_casos_individuales(
    exposiciones: dict[str, dict[str, float]],
    casos_entrada: list[dict[str, Any]],
    casos_medidos: list[dict[str, Any]],
    segmentado: bool,
) -> dict[str, dict[str, float]]:
    """Saca de la matriz colectiva los saldos que se miden caso por caso.

    Un caso puede repartirse en varias bandas (`bandas`), que es lo normal
    cuando el cliente entero sale de la matriz por superar el umbral de
    evaluación individual; si no trae ese desglose se usa su `tramo`.

    La guarda -«Los casos individuales del tramo X superan su exposición»-
    solo se evalúa cuando tanto la exposición de la banda como el saldo del
    caso son deudores: con un saldo acreedor (una nota de crédito) el resto
    puede quedar negativo sin que nadie mida dos veces, y abortar ahí
    convertiría una nota de crédito en un error inaccionable.
    """
    restantes = {s: dict(bandas) for s, bandas in exposiciones.items()}
    for entrada, medido in zip(casos_entrada, casos_medidos):
        segmento = entrada.get("segmento") if segmentado else None
        if segmento not in restantes:
            raise ValueError(
                f"El caso individual '{medido.get('identificacion')}' apunta a un segmento "
                f"inexistente: '{segmento}'"
            )
        bandas = entrada.get("bandas")
        if not bandas:
            tramo = medido.get("tramo")
            if tramo is None:
                continue
            bandas = {tramo: medido["saldo"]}
        for tramo, monto in bandas.items():
            if tramo not in restantes[segmento]:
                raise ValueError(f"El caso individual apunta a un tramo inexistente: '{tramo}'")
            expuesto = float(restantes[segmento][tramo])
            monto = float(monto)
            restante = expuesto - monto
            if monto >= 0 and expuesto >= 0:
                if restante < -0.01:
                    ubicacion = f"'{tramo}'" + (f" de {segmento}" if segmento else "")
                    raise ValueError(
                        f"Los casos individuales del tramo {ubicacion} superan su exposición: "
                        f"USD {monto:,.2f} sobre USD {expuesto:,.2f}. Revise que los saldos "
                        "evaluados individualmente salgan de la misma cartera que la matriz."
                    )
                restante = max(restante, 0.0)
            restantes[segmento][tramo] = restante
    return restantes


def resumen_deterioro(
    exposiciones: dict[str, Any],
    parametros: ParametrosECL | dict[str, ParametrosECL],
    casos_individuales: list[dict[str, Any]] | None = None,
    saldo_contable: float | None = None,
) -> dict[str, Any]:
    """Junta la matriz colectiva, los casos individuales, la conciliación y el
    cuadro tributario. Los saldos evaluados individualmente se descuentan de su
    tramo para no medirlos dos veces.

    Admite dos formas, y esta es la única entrada al resumen (el servicio no
    reimplementa ninguna de las dos):

    - Un solo universo: `exposiciones = {tramo: saldo}` y un `ParametrosECL`.
    - Por segmento: `exposiciones = {segmento: {tramo: saldo}}` y
      `parametros = {segmento: ParametrosECL}`. Terceros y relacionadas tienen
      comportamiento de pago distinto y no pueden compartir matriz
      (NIIF 9 B5.5.35), así que cada segmento se mide con sus propias tasas y
      su propio factor prospectivo, y después se consolidan los tramos.
    """
    casos_individuales = casos_individuales or []
    individual = evaluar_individual(casos_individuales)

    segmentado = isinstance(parametros, dict)
    por_segmento: dict[str, dict[str, float]] = (
        {s: dict(e) for s, e in exposiciones.items()} if segmentado else {None: dict(exposiciones)}
    )
    restantes = _deducir_casos_individuales(
        por_segmento, casos_individuales, individual["casos"], segmentado)

    if segmentado:
        medidos = {s: medir_ecl(restantes[s], parametros[s]) for s in restantes}
        colectivo = _consolidar_colectivo(medidos, parametros)
    else:
        colectivo = medir_ecl(restantes[None], parametros)

    exposicion_total = redondear(colectivo["exposicion_total"] + individual["saldo_total"])
    ecl_total = redondear(colectivo["ecl_total"] + individual["ecl_total"])
    # Lo sin medir viene de dos lados y ninguno se rellena con cero: las bandas
    # de la matriz que no tienen tasa aprobada, y los saldos evaluados
    # individualmente que caen en una banda sin tasa y sin estimación propia
    # justificada.
    exposicion_sin_medir = redondear(
        colectivo["exposicion_sin_medir"] + individual["saldo_sin_tasa_total"])
    exposicion_medida = redondear(exposicion_total - exposicion_sin_medir)
    tope_acumulado = redondear(exposicion_total * TOPE_PROVISION_ACUMULADA)

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
        # LORTI art. 10 num. 11 pone DOS límites distintos y sobre magnitudes
        # distintas: el 1 % limita la provisión DEL EJERCICIO (un flujo) y el
        # 10 % la provisión ACUMULADA (un stock). La PCE que se mide aquí es
        # acumulada, así que el único límite comparable es el del 10 %. El del
        # 1 % exige el movimiento de la provisión del período, que la
        # herramienta no recibe: se declara que no se puede verificar, en vez
        # de restar un flujo de un stock.
        "tributario": {
            "limite_ejercicio_1pct": redondear(exposicion_total * TASA_PROVISION_EJERCICIO),
            "tope_acumulado_10pct": tope_acumulado,
            "excede_tope_acumulado": ecl_total > tope_acumulado,
            "exceso_sobre_tope_acumulado": redondear(max(ecl_total - tope_acumulado, 0.0)),
            "provision_del_ejercicio": None,
            "limite_ejercicio_verificable": False,
            "nota": "Límites de deducción (LORTI art. 10 num. 11): el 1 % limita la provisión DEL "
                    "EJERCICIO y el 10 % la ACUMULADA. La pérdida esperada medida aquí es "
                    "acumulada, así que se contrasta contra el tope del 10 %; el límite anual del "
                    "1 % no se puede verificar sin el movimiento de la provisión del ejercicio. "
                    "Ninguno de los dos condiciona la estimación contable: el tratamiento "
                    "tributario concilia, no sustituye la medición de NIIF 9, y la diferencia es "
                    "temporaria.",
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
