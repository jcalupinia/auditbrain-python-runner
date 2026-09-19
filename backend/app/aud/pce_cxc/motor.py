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
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any

# Límites del artículo 10 numeral 11 de la LORTI (Ecuador): la provisión del
# ejercicio deducible es el 1 % de los créditos comerciales pendientes, con un
# tope acumulado del 10 % de la cartera. Es un límite tributario, nunca un piso
# ni un techo de la estimación contable.
TASA_PROVISION_EJERCICIO = 0.01
TOPE_PROVISION_ACUMULADA = 0.10


def redondear(valor: float) -> float:
    """Dos decimales, medio hacia arriba (criterio contable, no bancario).

    El cero negativo se normaliza a 0,00: `-0,00` no es un importe y el papel
    de trabajo no puede imprimirlo (sale, por ejemplo, de multiplicar una banda
    con saldo acreedor por una tasa de política del 0 %).
    """
    redondeado = float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return 0.0 if redondeado == 0 else redondeado


def _es_numero(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---------------------------------------------------------------------------
# Cotas: la ÚNICA forma de recortar un importe en este módulo
#
# La regla del módulo tiene dos mitades y las dos se han roto una vez por
# ronda, siempre por el mismo sitio:
#
#   1. El papel de trabajo se recalcula desde SUS PROPIAS celdas y da
#      exactamente lo que archiva la corrida. Cada vez que una cota nueva se
#      puso en el motor y no en la fórmula del Excel, el papel empezó a decir
#      otra cosa que la pantalla (pasó con `05-Matriz` y volvió a pasar con
#      `08-Conciliacion`).
#   2. Ninguna cota actúa en silencio: si un número se recorta, el resultado
#      dice que se recortó, y eso llega al papel y a la pantalla.
#
# `acotar` es lo que impide repetir el patrón: devuelve SIEMPRE el par
# (valor, motivo), así que no se puede obtener el valor recortado sin recibir
# también el motivo, y `COTAS` obliga a que cada cota tenga su celda en el
# papel. `tests/test_pce_cotas.py` comprueba las dos cosas: que no haya
# ningún recorte fuera de este helper y que cada entrada de `COTAS` tenga un
# escenario donde ACTÚE, una celda que la recalcule al centavo y una celda que
# declare que actuó.
# ---------------------------------------------------------------------------

#: Motivos de acotamiento. Son los valores que viajan en `acotado` y los que
#: el papel traduce a texto.
PISO_CERO = "piso_cero"
TASA_MAXIMA = "tasa_maxima"
TECHO_SALDO = "techo_saldo"
TECHO_CARTERA = "techo_cartera"


def acotar(valor: float, *, piso: float | None = None, techo: float | None = None,
           motivo_piso: str = PISO_CERO,
           motivo_techo: str = TECHO_SALDO) -> tuple[float, str | None]:
    """Recorta un importe entre `piso` y `techo` y DEVUELVE TAMBIÉN EL MOTIVO.

    Devolver el par obliga a quien acota a hacer algo con el motivo: no existe
    la forma "solo el número", que es como las cotas anteriores terminaron
    aplicándose en silencio. `motivo` es `None` cuando ninguna cota mordió.

    El piso se evalúa antes que el techo, y se exige `piso <= techo`: con el
    orden invertido el resultado dependería de cuál se mirara primero, y una
    cota cuyo resultado depende del orden no es una cota, es un accidente.
    """
    if piso is not None and techo is not None and piso > techo:
        raise ValueError(
            f"Cota mal formada: el piso ({piso}) supera al techo ({techo}). Una cota cuyo "
            "resultado depende de cuál se evalúe primero no es una cota."
        )
    if piso is not None and valor < piso:
        return piso, motivo_piso
    if techo is not None and valor > techo:
        return techo, motivo_techo
    return valor, None


def acotar_saldo_sin_medir(saldo_sin_tasa: float, saldo: float) -> float:
    """Lo que de un caso no se pudo medir, acotado a su propia exposición.

    Un cliente evaluado individualmente reparte su cartera entre varias bandas,
    y su exposición es el NETO de todas ellas. El saldo que no se pudo medir
    -las bandas sin tasa aprobada- se acumulaba sumando SOLO las bandas
    positivas, así que un cliente con 300.000 en una banda sin tasa y una nota
    de crédito de 100.000 en otra declaraba 300.000 sin medir sobre una
    exposición de 200.000. De ahí salía una «cartera medida» NEGATIVA sobre una
    cartera positiva, y una cobertura negativa en la pantalla.

    La cota es la misma idea que el techo de la pérdida esperada: nada de un
    caso puede superar su importe en libros bruto. Y como toda cota de este
    módulo, cuando actúa se declara (`saldo_sin_tasa_acotado`), nunca en
    silencio: quien necesite saber si mordió usa `acotar_saldo_sin_medir_con_motivo`.
    """
    return acotar_saldo_sin_medir_con_motivo(saldo_sin_tasa, saldo)[0]


def acotar_saldo_sin_medir_con_motivo(saldo_sin_tasa: float,
                                      saldo: float) -> tuple[float, str | None]:
    """Igual que `acotar_saldo_sin_medir`, devolviendo también qué cota mordió."""
    techo, _ = acotar(redondear(saldo), piso=0.0)
    return acotar(redondear(saldo_sin_tasa), piso=0.0, techo=techo,
                  motivo_techo=TECHO_SALDO)


@dataclass(frozen=True)
class CotaDelModulo:
    """Una cota del módulo y dónde tiene que aparecer en el papel de trabajo.

    Este registro es la otra mitad de la regla: `acotar` obliga a recibir el
    motivo, y esto obliga a que el motivo llegue al papel. `tests/test_pce_cotas.py`
    recorre `COTAS` y, para cada entrada, exige un escenario donde la cota
    ACTÚE, comprueba que la celda de `columna_valor` recalcule al centavo lo
    archivado, y que la de `columna_declaracion` diga que actuó.

    Una cota nueva que no se registre aquí hace fallar esa prueba, así que no
    se puede volver a poner una cota en el motor y olvidarla en la fórmula.
    """
    #: Identificador de la cota; la prueba exige un escenario con este nombre.
    nombre: str
    #: Qué importe acota, en castellano, para el mensaje de la prueba.
    que_acota: str
    #: Hoja del papel donde vive.
    hoja: str
    #: Columna (o celda, si `fila` no es None) cuya FÓRMULA reproduce el valor
    #: acotado. `None` cuando el papel imprime el importe como dato medido y no
    #: puede derivarlo de sus propias celdas (la pérdida de un caso individual).
    columna_valor: str | None
    #: Columna (o celda) que declara qué cota actuó. Nunca es `None`.
    columna_declaracion: str
    #: Filas fijas, para las cotas que no van por fila de datos. `None` = la
    #: cota se aplica fila a fila sobre los datos de la hoja.
    fila: int | None = None
    fila_declaracion: int | None = None


#: Todas las cotas del módulo. Ver `CotaDelModulo`.
COTAS: tuple[CotaDelModulo, ...] = (
    CotaDelModulo(
        nombre="perdida_esperada_de_la_banda",
        que_acota="La pérdida esperada de cada banda de la matriz colectiva",
        hoja="05-Matriz", columna_valor="H", columna_declaracion="J"),
    CotaDelModulo(
        nombre="perdida_esperada_del_caso_individual",
        que_acota="La pérdida esperada de cada caso evaluado individualmente",
        hoja="06-Individual", columna_valor=None, columna_declaracion="I"),
    CotaDelModulo(
        nombre="saldo_sin_medir_del_caso_individual",
        que_acota="El saldo sin medir de un caso, acotado a su propia exposición",
        hoja="06-Individual", columna_valor="F", columna_declaracion="J"),
    CotaDelModulo(
        nombre="tasa_observada_de_la_cohorte",
        que_acota="La tasa observada de la cohorte, acotada a [0 %; 100 %]",
        hoja="04-Tasas", columna_valor="D", columna_declaracion="E"),
    CotaDelModulo(
        nombre="cartera_medida",
        que_acota="La cartera medida, acotada a [0; cartera estratificada]",
        hoja="08-Conciliacion", columna_valor="B", columna_declaracion="B",
        fila=12, fila_declaracion=14),
)


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
        if 1 + float(self.ajuste_prospectivo) <= 0:
            # Un factor de 0,000 no es un ajuste prospectivo: anula la pérdida
            # esperada ENTERA (toda banda queda en 0,00 cualquiera que sea su
            # tasa observada) y deja un papel que afirma que no hay pérdida.
            # B5.5.51-52 pide ajustar la tasa histórica por las previsiones, no
            # sustituirla por cero, así que es un error de entrada: 400 con el
            # rango correcto, no una corrida archivada que dice 0,00.
            raise ValueError(
                f"El factor prospectivo no puede ser cero ni negativo: se pidió "
                f"{1 + float(self.ajuste_prospectivo):.3f}. Un factor de 0,000 anularía la "
                "pérdida esperada de todas las bandas y uno negativo invertiría su signo. "
                "Indique un factor mayor que 0,000 (1,000 = sin ajuste; 1,100 = 10 % más de "
                "pérdida esperada)."
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
            # El horizonte es el tiempo hasta el flujo esperado: no existe
            # negativo. Con uno negativo el factor de descuento pasa de 1 y la
            # pérdida esperada crecería al descontarla, que es lo contrario de
            # lo que hace descontar (B5.5.44).
            for tramo, t in self.horizontes.items():
                if not _es_numero(t) or float(t) < 0:
                    raise ValueError(
                        f"Horizonte de descuento inválido en '{tramo}': {t!r}. Indique los años "
                        "hasta el flujo esperado como un número mayor o igual a 0."
                    )

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

    LA BASE DE LA MEDICIÓN ES LA EXPOSICIÓN YA REDONDEADA A CENTAVOS. La
    exposición de una banda es un importe monetario, y un papel de trabajo
    auditable tiene que poder recalcularse desde sus propias celdas: la
    exposición que se imprime, multiplicada por la tasa que se imprime, debe
    dar la pérdida que se imprime. Antes se imprimía `redondear(saldo)` pero
    se medía sobre `saldo` con todos sus decimales -que es lo que deja el
    factor de anclaje a los estados financieros-, así que quien rehacía la
    cuenta desde el papel obtenía hasta un centavo de diferencia por banda
    contra lo archivado. Se redondea ANTES de multiplicar, no después.
    """
    filas = []
    total = 0.0
    exposicion_total = 0.0
    # Lo sin medir se lleva por partida DOBLE y ninguna de las dos sobra:
    # `sin_medir_deudora` y `sin_medir_acreedora` suman por separado, así que
    # la MAGNITUD (deudora + |acreedora|) dice cuánta cartera quedó sin
    # medición y la NETA dice cuánto hay que restarle a una cartera
    # estratificada que también es neta. Acumularlo en una sola variable con
    # signo -como estaba- hacía que una banda sin tasa de +20.000 y otra de
    # -20.000 se cancelaran y el módulo declarara que lo había medido todo.
    sin_medir_deudora = 0.0
    sin_medir_acreedora = 0.0
    exposicion_negativa = 0.0
    acotada_piso = 0.0
    acotada_techo = 0.0
    for tramo, saldo in exposiciones.items():
        # Centavos exactos antes de medir: esta es la cifra que el papel
        # imprime y sobre la que se multiplica (ver el docstring).
        saldo = redondear(float(saldo or 0))
        exposicion_total += saldo
        if saldo < 0:
            exposicion_negativa += saldo
        tasa = parametros.tasas_perdida.get(tramo)
        if tasa is None:
            # Sin historia no se inventa una tasa: la banda queda sin medir y su
            # exposición se informa aparte, en vez de afirmar (con una tasa cero)
            # que no hay pérdida. Se acumula por SIGNO, no en una sola suma:
            # una banda sin tasa no compensa a otra, porque ninguna de las dos
            # se midió.
            if saldo < 0:
                sin_medir_acreedora += saldo
            else:
                sin_medir_deudora += saldo
            filas.append({
                "tramo": tramo,
                "exposicion": saldo,
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
        tasa_ajustada, _ = acotar(tasa_ajustada_bruta, techo=1.0, motivo_techo=TASA_MAXIMA)
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
        #
        # El techo del importe en libros bruto se aplica igual que siempre
        # (B5.5.35 lo exige por escrito), pero NO lleva rótulo propio: con la
        # tasa ya acotada al 100 %, la LGD validada en [0, 1] y el factor de
        # descuento en (0, 1] -la tasa de descuento no puede ser negativa y los
        # horizontes tampoco-, el producto nunca supera la exposición, así que
        # `techo_exposicion` era un rótulo inalcanzable. El único recorte hacia
        # abajo posible es el de la tasa.
        ecl_sin_acotar = redondear(saldo * tasa_ajustada_bruta * lgd * factor)
        techo, _ = acotar(saldo, piso=0.0)
        ecl, _ = acotar(redondear(saldo * tasa_ajustada * lgd * factor), piso=0.0, techo=techo)
        acotado = None
        if ecl_sin_acotar < ecl - 0.0001:
            acotado = PISO_CERO
            acotada_piso += ecl - ecl_sin_acotar
        elif ecl_sin_acotar > ecl + 0.0001:
            acotado = TASA_MAXIMA
            acotada_techo += ecl_sin_acotar - ecl
        total += ecl
        filas.append({
            "tramo": tramo,
            "exposicion": saldo,
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
        # MAGNITUD: cuánta exposición quedó sin medición. Es la que decide
        # `medicion_completa`, el hallazgo y el KPI de la pantalla.
        "exposicion_sin_medir": redondear(sin_medir_deudora - sin_medir_acreedora),
        # NETA: la única que puede restarse de la cartera estratificada, que
        # también es neta. Las dos, con su desglose, llegan al papel.
        "exposicion_sin_medir_neta": redondear(sin_medir_deudora + sin_medir_acreedora),
        "exposicion_sin_medir_deudora": redondear(sin_medir_deudora),
        "exposicion_sin_medir_acreedora": redondear(sin_medir_acreedora),
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

    Igual que en la matriz colectiva, el saldo del caso se redondea a centavos
    ANTES de medir: es un importe monetario y es el que imprime el papel, así
    que saldo menos recuperación tiene que dar exactamente la pérdida
    archivada.
    """
    detalle = []
    saldo_total = 0.0
    ecl_total = 0.0
    acotada_piso = 0.0
    acotada_techo = 0.0
    sin_tasa_total = 0.0
    sin_tasa_recortado = 0.0
    acreedor_total = 0.0
    for caso in casos:
        # Centavos exactos antes de medir (ver el docstring).
        saldo = redondear(float(caso.get("saldo") or 0))
        techo, _ = acotar(saldo, piso=0.0)
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
        ecl, acotado = acotar(ecl_sin_acotar, piso=0.0, techo=techo, motivo_techo=TECHO_SALDO)
        if acotado == PISO_CERO:
            acotada_piso += ecl - ecl_sin_acotar
        elif acotado == TECHO_SALDO:
            acotada_techo += ecl_sin_acotar - ecl
        saldo_total += saldo
        ecl_total += ecl
        # Parte del saldo del caso que no se pudo medir (banda sin tasa y sin
        # estimación propia justificada). Va como campo propio, no solo dentro
        # del texto de `sustento`, para que se pueda sumar sin tener que
        # parsear una frase. Se acota a la exposición del propio caso: ver
        # `acotar_saldo_sin_medir`.
        # Con el MOTIVO, no solo con el valor: `acotar_saldo_sin_medir` tiene
        # dos cotas -el piso cero y el techo de la exposición del caso- y
        # deducir «se acotó» de `sin_acotar > acotado` solo ve la segunda. Con
        # un saldo sin medir acreedor el piso lo mueve a 0,00 y el caso decía
        # que no se había acotado nada.
        sin_tasa_sin_acotar = redondear(float(caso.get("saldo_sin_tasa") or 0.0))
        sin_tasa, sin_tasa_acotado = acotar_saldo_sin_medir_con_motivo(
            sin_tasa_sin_acotar, saldo)
        sin_tasa_total += sin_tasa
        # «Cuánto se recortó» es una MAGNITUD: con el piso actuando, la resta
        # cruda daba el recorte en negativo.
        sin_tasa_recortado += abs(sin_tasa_sin_acotar - sin_tasa)
        # Saldo acreedor DENTRO del caso (una nota de crédito en una de sus
        # bandas). El neto del cliente puede ser deudor y esconderla: sin este
        # campo, el piso cero actuaba sobre ella en silencio y ningún hallazgo
        # la nombraba.
        acreedor = redondear(float(caso.get("saldo_acreedor") or 0.0))
        acreedor_total += acreedor
        detalle.append({
            "identificacion": caso.get("identificacion"),
            "tramo": caso.get("tramo"),
            "saldo": saldo,
            "recuperacion_estimada": redondear(saldo - ecl),
            "sustento": caso.get("sustento", ""),
            "saldo_sin_tasa": sin_tasa,
            "saldo_sin_tasa_sin_acotar": sin_tasa_sin_acotar,
            "saldo_sin_tasa_acotado": sin_tasa_acotado is not None,
            "saldo_acreedor": acreedor,
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
        # Cuánto tuvo que recortarse ese saldo para no superar la exposición de
        # su propio caso, y cuánto saldo acreedor viaja dentro de los casos.
        "saldo_sin_tasa_acotado_total": redondear(sin_tasa_recortado),
        "saldo_acreedor_total": redondear(acreedor_total),
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
    totales = {"exposicion_total": 0.0, "exposicion_sin_medir": 0.0,
               "exposicion_sin_medir_neta": 0.0, "exposicion_sin_medir_deudora": 0.0,
               "exposicion_sin_medir_acreedora": 0.0, "exposicion_negativa": 0.0,
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
    brutos: dict[str, dict[str, float]] | None = None,
    ajustes: dict[str, int] | None = None,
) -> dict[str, dict[str, float]]:
    """Saca de la matriz colectiva los saldos que se miden caso por caso.

    Un caso puede repartirse en varias bandas (`bandas`), que es lo normal
    cuando el cliente entero sale de la matriz por superar el umbral de
    evaluación individual; si no trae ese desglose se usa su `tramo`.

    La guarda -«Los casos individuales del tramo X superan su exposición»- se
    evalúa contra el saldo DEUDOR de la banda (`brutos`), no contra su neto.
    Una nota de crédito de otro cliente en la misma banda deja el neto por
    debajo del saldo del caso sin que nadie mida dos veces; comparar contra el
    neto convertía esa nota de crédito en un error inaccionable, que es
    justamente lo que el módulo no puede volver a hacer. Sin `brutos` (la
    forma de un solo universo, donde no hay detalle por documento) se compara
    contra la exposición tal como llegó.

    El resto puede quedar NEGATIVO: es la nota de crédito, que sigue en la
    matriz colectiva con su signo y a la que `medir_ecl` aplica el piso cero.
    Solo se lleva a cero lo que está por debajo del centavo, que es ruido.

    `ajustes`, si se pasa, recoge cuántos centavos tuvo que repartir
    `_cuadrar_restantes_a_centavos` en cada segmento: no es un detalle interno,
    va a la bitácora del papel de trabajo.
    """
    restantes = {s: dict(bandas) for s, bandas in exposiciones.items()}
    techos = brutos if brutos is not None else exposiciones
    # Saldo que sale de cada segmento hacia 06-Individual: lo necesita
    # `_cuadrar_restantes_a_centavos` para fijar el objetivo de la matriz.
    fuera: dict[str, float] = {s: 0.0 for s in restantes}
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
            monto = float(monto)
            techo = float(techos.get(segmento, {}).get(tramo, restantes[segmento][tramo]))
            if monto > techo + 0.01:
                ubicacion = f"'{tramo}'" + (f" de {segmento}" if segmento else "")
                raise ValueError(
                    f"Los casos individuales del tramo {ubicacion} superan su exposición: "
                    f"USD {monto:,.2f} sobre USD {techo:,.2f}. Revise que los saldos evaluados "
                    "individualmente salgan de la misma cartera que la matriz."
                )
            restante = float(restantes[segmento][tramo]) - monto
            restantes[segmento][tramo] = 0.0 if abs(restante) < 0.01 else restante
        fuera[segmento] = fuera.get(segmento, 0.0) + float(medido["saldo"])
    return _cuadrar_restantes_a_centavos(restantes, exposiciones, fuera, ajustes)


def _a_centavos(valor: float) -> int:
    """El importe, ya redondeado, como número entero de centavos."""
    return int(Decimal(str(redondear(valor))) * 100)


def _cuadrar_restantes_a_centavos(
    restantes: dict[str, dict[str, float]],
    exposiciones: dict[str, dict[str, float]],
    fuera: dict[str, float],
    ajustes: dict[str, int] | None = None,
) -> dict[str, dict[str, float]]:
    """Deja cada banda de la matriz en CENTAVOS EXACTOS sin descuadrar el total.

    POR QUÉ HACE FALTA. La exposición de una banda es un importe monetario y
    `medir_ecl` la redondea ANTES de multiplicarla por la tasa: es la única
    forma de que el papel de trabajo se pueda recalcular desde sus propias
    celdas (exposición impresa × tasa impresa = pérdida impresa). Pero
    entonces el total deja de ser «la suma redondeada» y pasa a ser «la suma DE
    LAS REDONDEADAS», y esa suma puede apartarse unos centavos de la cartera
    anclada a los estados financieros: medio centavo por banda en el peor caso,
    hasta cuatro centavos por segmento con las ocho bandas por defecto. Sin
    esta función esa diferencia saldría en `08-Conciliacion` como un descuadre
    contra los EEFF que no existe en la cartera del cliente: es redondeo de
    presentación, no una partida conciliatoria.

    DÓNDE SE ABSORBE. Dentro de las propias bandas de la matriz, UN centavo por
    banda y empezando por las de mayor resto fraccionario (método del resto
    mayor). Así ninguna banda se aparta más de un centavo de su exposición
    exacta y se conserva la identidad que el papel necesita:

        Σ bandas de 05-Matriz + Σ casos de 06-Individual = cartera anclada

    Se descartaron las dos alternativas: cargarle toda la diferencia a una sola
    banda (distorsiona una banda concreta por varios centavos y sesga su
    pérdida esperada) y dejarla como partida conciliatoria de redondeo (ensucia
    la conciliación con una diferencia que no es del cliente). El reparto no es
    silencioso: la bitácora del papel lo declara.

    Aquí no se conoce la cartera de los estados financieros, ni hace falta. El
    objetivo de cada segmento es el importe que YA llegó en `exposiciones` -que
    el servicio ancló antes de llamar- redondeado una sola vez, menos los casos
    individuales que salieron de esas bandas (`fuera`, ya en centavos porque
    `evaluar_individual` los redondeó). Sin anclaje el objetivo es el total del
    archivo redondeado, que es igualmente la cifra que el papel declara.

    EL REPARTO NO PUEDE INVENTAR UNA BANDA ACREEDORA. Al quitar un centavo, el
    orden ascendente por resto pone primero las bandas VACÍAS (resto 0) y las
    dejaba en -0,01: esa banda entraba en la matriz, se imprimía en 05-Matriz y
    disparaba el hallazgo Alto «Saldos acreedores en la cartera medida» sobre
    un centavo que había puesto la propia herramienta. Ahora el centavo solo se
    quita de bandas que pueden absorberlo sin volverse acreedoras; si ninguna
    puede, manda el total -el papel no puede descuadrar contra los EEFF- y el
    reparto queda declarado en la bitácora igual que siempre.
    """
    cien = Decimal("100")
    for segmento, bandas in restantes.items():
        if not bandas:
            continue
        redondeadas = {b: redondear(v) for b, v in bandas.items()}
        bruto = sum(float(v or 0) for v in exposiciones.get(segmento, {}).values())
        objetivo = _a_centavos(bruto) - _a_centavos(fuera.get(segmento, 0.0))
        sobrante = objetivo - sum(_a_centavos(v) for v in redondeadas.values())
        if sobrante and ajustes is not None:
            ajustes[str(segmento or "CARTERA")] = sobrante
        if sobrante:
            exactos = {b: Decimal(str(float(v or 0))) * cien for b, v in bandas.items()}
            resto = {b: v - v.to_integral_value(rounding=ROUND_FLOOR)
                     for b, v in exactos.items()}
            orden = sorted(bandas, key=lambda b: resto[b], reverse=sobrante > 0)
            paso = Decimal("0.01") if sobrante > 0 else Decimal("-0.01")
            # Cuántos centavos lleva cada banda: se reparte UNO por banda antes
            # de repetir en ninguna, para que ninguna se aparte más de un
            # centavo de su exposición exacta. El segundo reparto es una red de
            # seguridad -`sobrante` no puede superar el número de bandas-, pero
            # si algún día lo hiciera el total seguiría cuadrando.
            usados: dict[str, int] = {}
            for _ in range(abs(sobrante)):
                # La elegibilidad se recalcula en cada paso: quitar un centavo
                # puede dejar sin margen a una banda que lo tenía al empezar.
                candidatos = [b for b in orden
                              if sobrante > 0 or redondear(redondeadas[b] - 0.01) >= 0]
                # Sin ninguna banda que pueda absorberlo sin volverse acreedora,
                # manda el cuadre del total: el papel no puede descuadrar contra
                # los EEFF, y el reparto se declara en la bitácora.
                candidatos = candidatos or orden
                minimo = min(usados.get(b, 0) for b in candidatos)
                b = next(x for x in candidatos if usados.get(x, 0) == minimo)
                usados[b] = minimo + 1
                redondeadas[b] = float(Decimal(str(redondeadas[b])) + paso)
        restantes[segmento] = redondeadas
    return restantes


def resumen_deterioro(
    exposiciones: dict[str, Any],
    parametros: ParametrosECL | dict[str, ParametrosECL],
    casos_individuales: list[dict[str, Any]] | None = None,
    saldo_contable: float | None = None,
    exposiciones_brutas: dict[str, Any] | None = None,
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

    `exposiciones_brutas` es la misma estructura con SOLO el saldo deudor de
    cada banda. Sirve para una cosa: acotar los casos individuales contra lo
    que de verdad puede salir de la banda. Sin ella, una nota de crédito de
    otro cliente en la misma banda haría fallar la guarda.
    """
    casos_individuales = casos_individuales or []
    individual = evaluar_individual(casos_individuales)

    segmentado = isinstance(parametros, dict)
    por_segmento: dict[str, dict[str, float]] = (
        {s: dict(e) for s, e in exposiciones.items()} if segmentado else {None: dict(exposiciones)}
    )
    brutos = None
    if exposiciones_brutas is not None:
        brutos = ({s: dict(e) for s, e in exposiciones_brutas.items()} if segmentado
                  else {None: dict(exposiciones_brutas)})
    # Centavos que la cuadratura del redondeo tuvo que repartir entre las
    # bandas: se declara en el resultado (y de ahí en la bitácora del papel),
    # nunca se aplica en silencio.
    ajuste_redondeo: dict[str, int] = {}
    restantes = _deducir_casos_individuales(
        por_segmento, casos_individuales, individual["casos"], segmentado, brutos,
        ajuste_redondeo)

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
    #
    # Y VIAJA EN DOS MAGNITUDES, porque las dos son reales y ninguna sustituye
    # a la otra:
    #
    # - la MAGNITUD (deudora + |acreedora|) es cuánta cartera quedó sin
    #   medición. Es la que declara `medicion_completa`, la que dispara el
    #   hallazgo y la que pinta la pantalla. Antes se acumulaba con signo, así
    #   que una banda sin tasa de +20.000 y otra de -20.000 se cancelaban y el
    #   módulo declaraba que había medido toda la cartera.
    # - la NETA es la única que puede restarse de la cartera estratificada,
    #   porque esa cartera también es neta: `medida = estratificada - neta`
    #   cuadra al centavo, y `medida + magnitud` NO da la estratificada. El
    #   papel imprime las dos, cada una con su rótulo, y dice por qué difieren.
    #
    # Lo sin medir de la evaluación individual ya viene con piso cero
    # (`acotar_saldo_sin_medir`), así que ahí magnitud y neta coinciden.
    exposicion_sin_medir = redondear(
        colectivo["exposicion_sin_medir"] + individual["saldo_sin_tasa_total"])
    exposicion_sin_medir_neta = redondear(
        colectivo.get("exposicion_sin_medir_neta", colectivo["exposicion_sin_medir"])
        + individual["saldo_sin_tasa_total"])
    # La cartera medida es lo estratificado menos lo que no se pudo medir, y
    # tiene que caer entre 0 y la cartera total: no existe una cartera medida
    # negativa sobre una cartera positiva, ni una mayor que la que hay. Las dos
    # magnitudes ya se cuadran sobre la misma base (`acotar_saldo_sin_medir`);
    # esta cota es la red que impide que un cambio futuro vuelva a desalinear
    # la pantalla, el papel y la base sin que nadie se entere.
    #
    # Cuando muerde NO se aplica en silencio: viajan la resta cruda
    # (`exposicion_medida_sin_acotar`) y el motivo (`exposicion_medida_acotada`),
    # `08-Conciliacion` imprime las tres celdas y el servicio levanta el
    # hallazgo «Cartera medida acotada».
    exposicion_medida_sin_acotar = redondear(exposicion_total - exposicion_sin_medir_neta)
    techo_cartera, _ = acotar(exposicion_total, piso=0.0)
    exposicion_medida, exposicion_medida_acotada = acotar(
        exposicion_medida_sin_acotar, piso=0.0, techo=techo_cartera,
        motivo_techo=TECHO_CARTERA)
    tope_acumulado = redondear(exposicion_total * TOPE_PROVISION_ACUMULADA)
    # El tope tributario del 10 % solo tiene lectura sobre una cartera
    # POSITIVA: con la cartera estratificada neta acreedora el tope sale
    # negativo y «excede el tope» decía que sí con una pérdida esperada de
    # 0,00. Lo que no se puede contrastar se declara, igual que el límite
    # anual del 1 %, en vez de concluir un absurdo.
    tope_verificable = exposicion_total > 0.005

    resultado: dict[str, Any] = {
        "colectivo": colectivo,
        "individual": individual,
        # Reparto de centavos que exige medir sobre la exposición redondeada
        # sin desanclar el total (ver `_cuadrar_restantes_a_centavos`). Vacío
        # cuando la suma de las bandas redondeadas ya daba el total exacto.
        "redondeo_exposicion": ajuste_redondeo,
        "exposicion_total": exposicion_total,
        "exposicion_sin_medir": exposicion_sin_medir,
        "exposicion_sin_medir_neta": exposicion_sin_medir_neta,
        "exposicion_sin_medir_deudora": redondear(
            colectivo.get("exposicion_sin_medir_deudora", 0.0)
            + individual["saldo_sin_tasa_total"]),
        "exposicion_sin_medir_acreedora": redondear(
            colectivo.get("exposicion_sin_medir_acreedora", 0.0)),
        "exposicion_medida": exposicion_medida,
        # La resta cruda y el motivo de la cota, para que el papel imprima las
        # dos cifras y la pantalla pueda decir que se acotó.
        "exposicion_medida_sin_acotar": exposicion_medida_sin_acotar,
        "exposicion_medida_acotada": exposicion_medida_acotada,
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
            # Sin cartera estratificada positiva el tope no es contrastable: se
            # declara, no se concluye (ver `tope_verificable`).
            "tope_acumulado_verificable": tope_verificable,
            "excede_tope_acumulado": tope_verificable and ecl_total > tope_acumulado,
            "exceso_sobre_tope_acumulado": (
                acotar(redondear(ecl_total - tope_acumulado), piso=0.0)[0]
                if tope_verificable else 0.0),
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
