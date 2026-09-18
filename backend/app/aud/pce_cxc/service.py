"""Orquesta el análisis de pérdidas crediticias esperadas de cuentas por cobrar.

Secuencia: leer los tres cortes -> derivar tasas de la cohorte más antigua ->
anclar la exposición a los estados financieros -> separar los saldos de evaluación
individual -> medir -> comparar contra la política del cliente -> armar hallazgos
y pendientes. Ningún parámetro se inventa: lo que falta se reporta.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.aud.pce_cxc.bandas import BANDAS_POR_DEFECTO, desdoblar
from backend.app.aud.pce_cxc.cohortes import tasas_por_permanencia
from backend.app.aud.pce_cxc.lectura import MOTIVO_FILA_REPETIDA, leer_cartera
from backend.app.aud.pce_cxc.models import CorridaPCE
from backend.app.aud.pce_cxc.motor import (
    ParametrosECL, redondear, resumen_deterioro,
)
from backend.app.auth.models import User
from backend.app.context import service as ctx_service
from backend.app.context.models import Project

SEGMENTOS = ("NO-RELACIONADOS", "RELACIONADOS")


# ---------------------------------------------------------------------------
# Autorización multi-tenant
#
# Mismo patrón que los módulos hermanos (`obligaciones_fiscales/service.py` y
# `informe_cumplimiento_tributario/service.py`): el proyecto acota el alcance y
# `ctx_service.user_can_access_project` decide. `require_staff` por sí solo no
# alcanza: dice que quien pregunta es operador, no de QUÉ firma.
# ---------------------------------------------------------------------------

def asegurar_acceso_a_proyecto(db: Session, user: User, project_id: int) -> Project:
    proyecto = db.get(Project, project_id)
    if not proyecto or not ctx_service.user_can_access_project(db, user, proyecto):
        raise PermissionError("Sin acceso al proyecto.")
    return proyecto


def obtener_corrida(db: Session, user: User, corrida_id: int) -> CorridaPCE:
    """Recupera una corrida verificando que el usuario pueda verla.

    - Con proyecto asociado: manda el acceso al proyecto (organización + rol).
    - SIN proyecto asociado (`project_id` es nulo): no hay proyecto que acote el
      alcance, así que la corrida es visible para quien la creó y para los
      operadores de SU MISMA organización -el papel de trabajo es de la firma,
      no del operador que apretó el botón-. Si no se puede determinar esa
      organización (la corrida perdió su `user_id`, o el autor ya no existe o no
      tiene organización), solo la ve el propio autor; si tampoco hay autor, no
      la ve nadie.
    """
    corrida = db.get(CorridaPCE, corrida_id)
    if not corrida:
        raise LookupError("Corrida no encontrada")
    if corrida.project_id is not None:
        asegurar_acceso_a_proyecto(db, user, corrida.project_id)
        return corrida
    if corrida.user_id is not None and corrida.user_id == user.id:
        return corrida
    autor = db.get(User, corrida.user_id) if corrida.user_id is not None else None
    if not (autor and autor.organization_id and autor.organization_id == user.organization_id):
        raise PermissionError("Sin acceso a la corrida.")
    return corrida


# ---------------------------------------------------------------------------
# Normalización de los parámetros que llegan del formulario
#
# `parametros` viaja como JSON libre desde el router, así que aquí se valida su
# forma antes de tocarla. Un parámetro mal formado es un error de entrada del
# usuario (HTTP 400 con un mensaje que dice qué corregir), nunca un
# `AttributeError` que termine en HTTP 500.
# ---------------------------------------------------------------------------

def _diccionario(valor: Any, nombre: str) -> dict:
    """Normaliza un parámetro que debe llegar como objeto (diccionario)."""
    if valor is None or valor == "" or valor == [] or valor == {}:
        return {}
    if isinstance(valor, dict):
        return valor
    raise ValueError(
        f"El parámetro '{nombre}' debe ser un objeto con un valor por clave; llegó un "
        f"{type(valor).__name__}. Corrija '{nombre}' en el formulario y vuelva a calcular."
    )


def _numero(valor: Any, nombre: str, por_defecto: float = 0.0) -> float:
    """Normaliza un parámetro numérico sin convertir un 0 explícito en el defecto."""
    if valor is None or valor == "":
        return por_defecto
    if isinstance(valor, bool):
        raise ValueError(f"El parámetro '{nombre}' debe ser un número; llegó un booleano.")
    try:
        return float(valor)
    except (TypeError, ValueError):
        raise ValueError(
            f"El parámetro '{nombre}' debe ser un número; llegó {valor!r}. Corríjalo en el "
            "formulario y vuelva a calcular."
        ) from None


def _factores_prospectivos(valor: Any) -> dict[str, float]:
    """Factor prospectivo por segmento, admitiendo el formato antiguo escalar.

    El exportador ya soportaba un escalar que aplica a todos los segmentos, así
    que el servicio lo acepta igual en vez de reventar con un 500 al llamar
    `.get` sobre un número.
    """
    if valor is None or valor == "":
        return {s: 1.0 for s in SEGMENTOS}
    if isinstance(valor, dict):
        return {s: _numero(valor.get(s), f"factor_prospectivo['{s}']", 1.0) for s in SEGMENTOS}
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        unico = _numero(valor, "factor_prospectivo", 1.0)
        return {s: unico for s in SEGMENTOS}
    raise ValueError(
        f"El parámetro 'factor_prospectivo' debe ser un número (el mismo factor para todos los "
        f"segmentos) o un objeto con un factor por segmento; llegó un {type(valor).__name__}. "
        "Corríjalo en el formulario y vuelva a calcular."
    )


def _tasas_sustitutas(valor: Any) -> dict[str, dict[str, Any]]:
    """Valida la forma de cada tasa sustituta: `{ "SEGMENTO|banda": {tasa, justificacion} }`."""
    crudo = _diccionario(valor, "tasas_sustitutas")
    salida: dict[str, dict[str, Any]] = {}
    for clave, sus in crudo.items():
        if not isinstance(sus, dict):
            raise ValueError(
                f"La tasa sustituta de '{clave}' debe ser un objeto con 'tasa' y 'justificacion'; "
                f"llegó {sus!r}. Corrija 'tasas_sustitutas' y vuelva a calcular."
            )
        tasa = _numero(sus.get("tasa"), f"tasas_sustitutas['{clave}'].tasa", 0.0)
        if not 0 <= tasa <= 1:
            raise ValueError(
                f"La tasa sustituta de '{clave}' es {tasa}: debe estar entre 0 y 1 (0,42 = 42 %). "
                "Corrija 'tasas_sustitutas' y vuelva a calcular."
            )
        salida[clave] = {"tasa": tasa, "justificacion": str(sus.get("justificacion", ""))}
    return salida


def _evaluaciones_individuales(valor: Any) -> dict[str, dict[str, Any]]:
    """Valida la forma de cada evaluación individual: `{ "SEGMENTO|cliente": {ecl, justificacion} }`."""
    crudo = _diccionario(valor, "evaluaciones_individuales")
    salida: dict[str, dict[str, Any]] = {}
    for clave, est in crudo.items():
        if not isinstance(est, dict):
            raise ValueError(
                f"La evaluación individual de '{clave}' debe ser un objeto con 'ecl' y "
                f"'justificacion'; llegó {est!r}. Corrija 'evaluaciones_individuales' y vuelva a "
                "calcular."
            )
        salida[clave] = {
            "ecl": _numero(est.get("ecl"), f"evaluaciones_individuales['{clave}'].ecl", 0.0),
            "justificacion": str(est.get("justificacion", "")),
        }
    return salida


def _umbral_dias(valor: Any) -> int:
    """Días de mora a partir de los cuales se presume incumplimiento.

    Un 0 guardado no puede convertirse en 730 en silencio (era lo que hacía
    `int(valor or 730)`): o el valor es utilizable, o se dice que no lo es.
    """
    if valor is None or valor == "":
        return 730
    dias = _numero(valor, "umbral_dias_incumplimiento", 730)
    if dias != int(dias) or int(dias) <= 0:
        raise ValueError(
            f"El parámetro 'umbral_dias_incumplimiento' es {valor!r}: indique un número entero de "
            "días mayor que 0 (el plan usa 730; NIIF 9 B5.5.37 presume 90 salvo refutación), o "
            "déjelo vacío para usar el valor por defecto."
        )
    return int(dias)


def analizar(cortes: list[dict[str, Any]], parametros: dict[str, Any]) -> dict[str, Any]:
    if len(cortes) != 3:
        raise ValueError("Se requieren los tres análisis de antigüedad: sin tres cierres no existe "
                         "una cohorte con ventana completa de 24 meses")
    umbral_dias = _umbral_dias(parametros.get("umbral_dias_incumplimiento"))
    bandas = desdoblar(BANDAS_POR_DEFECTO, umbral_dias)
    nombres = [b["nombre"] for b in bandas]

    leidos = [leer_cartera(c["contenido"], c["nombre"], c["fecha"], bandas,
                           c.get("hoja"), c.get("mapeo")) for c in cortes]
    cohorte, intermedio, actual = leidos

    # El corte intermedio no entra en las tasas -la permanencia se mide entre
    # t-2 y t-, pero sí controla que el camino entre los dos extremos sea
    # coherente: sin él no hay forma de ver un documento que desapareció y
    # volvió, ni un remanente que creció.
    coh = tasas_por_permanencia(cohorte["filas"], actual["filas"], intermedio["filas"])
    tasas = coh["tasas"]

    # Exposición por segmento y banda, anclada a los estados financieros.
    eeff = _diccionario(parametros.get("eeff"), "eeff")
    meta = {"NO-RELACIONADOS": _numero(eeff.get("no_relacionados"), "eeff.no_relacionados"),
            "RELACIONADOS": _numero(eeff.get("relacionados"), "eeff.relacionados")}
    ancla = sum(meta.values()) > 0
    total_seg = {s: 0.0 for s in SEGMENTOS}
    for f in actual["filas"]:
        total_seg[f["segmento"]] += f["saldo"]
    factor, sin_estratificar = {}, {}
    for s in SEGMENTOS:
        if not ancla:
            factor[s], sin_estratificar[s] = 1.0, 0.0
        elif total_seg[s] > 0:
            factor[s], sin_estratificar[s] = meta[s] / total_seg[s], 0.0
        else:
            factor[s], sin_estratificar[s] = 1.0, meta[s]

    # Evaluación individual: los clientes por encima del umbral salen de la
    # matriz. La comparación va contra el saldo YA ANCLADO, que es la exposición
    # que se va a medir: con el saldo crudo del archivo, un cliente con 90.000 y
    # un factor de anclaje de 5,0 (450.000 de exposición) se quedaba en la
    # matriz midiéndose con el promedio de su banda.
    umbral_ind = _numero(parametros.get("umbral_individual"), "umbral_individual")
    por_cliente: dict[tuple[str, str], float] = {}
    for f in actual["filas"]:
        clave = (f["segmento"], f["cliente"] or "(sin nombre)")
        por_cliente[clave] = por_cliente.get(clave, 0.0) + f["saldo"] * factor[f["segmento"]]
    individuales = {k for k, v in por_cliente.items() if umbral_ind and v > umbral_ind}

    # La matriz se mide POR SEGMENTO: terceros y relacionadas tienen comportamiento
    # de pago distinto y no pueden agruparse (NIIF 9 B5.5.35).
    #
    # La exposición de cada banda se acumula COMPLETA, incluidos los clientes que
    # se van a evaluar individualmente: es `motor.resumen_deterioro` quien los
    # deduce de su banda, con su guarda de no medir dos veces. Repartir aquí y
    # entregar la matriz ya depurada dejaba esa guarda fuera del producto.
    colectiva = {s: {b: 0.0 for b in nombres} for s in SEGMENTOS}
    # Saldo DEUDOR de cada banda: es el techo contra el que el motor acota los
    # casos individuales. El neto no sirve, porque una nota de crédito de otro
    # cliente lo deja por debajo del saldo del caso sin que nadie mida dos veces.
    deudora = {s: {b: 0.0 for b in nombres} for s in SEGMENTOS}
    casos: dict[tuple[str, str], dict[str, Any]] = {}
    for f in actual["filas"]:
        clave = (f["segmento"], f["cliente"] or "(sin nombre)")
        saldo = f["saldo"] * factor[f["segmento"]]
        colectiva[f["segmento"]][f["banda"]] += saldo
        if saldo > 0:
            deudora[f["segmento"]][f["banda"]] += saldo
        if clave in individuales:
            caso = casos.setdefault(clave, {"identificacion": clave[1], "segmento": clave[0],
                                            "saldo": 0.0, "bandas": {}})
            caso["saldo"] += saldo
            caso["bandas"][f["banda"]] = caso["bandas"].get(f["banda"], 0.0) + saldo

    # Tasas aplicadas: las observadas de cada segmento, o las sustituidas con
    # justificación escrita. Sin ninguna de las dos, la banda queda sin medir.
    sustitutas = _tasas_sustitutas(parametros.get("tasas_sustitutas"))
    factores_solicitados = _factores_prospectivos(parametros.get("factor_prospectivo"))
    justificacion = str(parametros.get("justificacion_prospectivo") or "")
    aplicadas: dict[str, dict[str, float]] = {}
    for s in SEGMENTOS:
        aplicadas[s] = {}
        for b in nombres:
            obs = tasas.get(s, {}).get(b)
            sus = sustitutas.get(f"{s}|{b}")
            if sus and sus["justificacion"].strip():
                aplicadas[s][b] = sus["tasa"]
            elif obs is not None:
                aplicadas[s][b] = obs

    # El ajuste prospectivo pedido solo se aplica si viene con justificación
    # escrita (NIIF 9 B5.5.51-52). Sin ella se ignora en silencio aquí (nunca
    # se levanta una excepción por esto) y queda expuesto como hallazgo.
    factor_prospectivo_aplicado: dict[str, float] = {}
    for s in SEGMENTOS:
        solicitado = factores_solicitados[s]
        if solicitado < 0:
            raise ValueError(
                f"El parámetro 'factor_prospectivo' de {s} es {solicitado:,.3f}: un factor negativo "
                "invertiría el signo de la pérdida esperada. Indique un factor mayor o igual a "
                "0,000 (1,000 = sin ajuste)."
            )
        if solicitado != 1.0 and not justificacion.strip():
            factor_prospectivo_aplicado[s] = 1.0
        else:
            factor_prospectivo_aplicado[s] = solicitado

    evaluaciones = _evaluaciones_individuales(parametros.get("evaluaciones_individuales"))
    lista_casos = []
    sin_medir_individual = 0.0
    for clave, caso in casos.items():
        est = evaluaciones.get(f"{clave[0]}|{clave[1]}")
        aplicadas_seg = aplicadas[clave[0]]
        # Cada saldo del caso se separa entre las bandas con tasa (se miden
        # provisionalmente con ella) y las bandas sin tasa: estas últimas no se
        # rellenan con 0,00 en silencio, se declaran como saldo sin medir.
        saldo_sin_tasa = sum(v for b, v in caso["bandas"].items() if b not in aplicadas_seg)
        provisional = sum(v * aplicadas_seg[b] for b, v in caso["bandas"].items() if b in aplicadas_seg)
        propia = bool(est and est["justificacion"].strip())
        # Techo del caso: su importe en libros bruto (B5.5.35). Un cliente con
        # saldo neto acreedor (nota de crédito mayor que sus facturas) tiene
        # techo 0,00 y se mide en 0,00; nunca genera "ganancia esperada".
        techo = max(redondear(caso["saldo"]), 0.0)
        if propia:
            # Una estimación propia con justificación escrita cubre todo el caso:
            # no queda saldo sin medir.
            ecl_caso = est["ecl"]
            if ecl_caso < -0.005 or ecl_caso > techo + 0.005:
                raise ValueError(
                    f"La pérdida esperada indicada para '{clave[1]}' ({clave[0]}) es "
                    f"{ecl_caso:,.2f} y su importe en libros bruto es {caso['saldo']:,.2f}: bajo "
                    "NIIF 9 la corrección de valor no puede ser negativa ni superar el importe en "
                    f"libros. Corrija 'evaluaciones_individuales' con un importe entre 0,00 y "
                    f"{techo:,.2f}."
                )
            sustento = est["justificacion"]
            saldo_sin_tasa_caso = 0.0
        else:
            ecl_caso = provisional
            sustento = "Medido con la tasa de la matriz (provisional)"
            saldo_sin_tasa_caso = saldo_sin_tasa if saldo_sin_tasa > 0.005 else 0.0
            if saldo_sin_tasa_caso > 0:
                sustento += f"; USD {saldo_sin_tasa_caso:,.2f} sin medir por falta de tasa"
                sin_medir_individual += saldo_sin_tasa_caso
        # Se entrega la pérdida SIN acotar: `evaluar_individual` aplica el piso y
        # el techo y deja dicho cuál actuó, en el mismo lugar donde lo hace la
        # matriz colectiva.
        lista_casos.append({
            "identificacion": f"{caso['identificacion']} ({clave[0]})", "tramo": None,
            # `segmento` y `bandas` son lo que `resumen_deterioro` necesita para
            # sacar el caso de CADA banda en la que tiene saldo: un cliente que
            # supera el umbral individual reparte su cartera entre varias.
            "segmento": clave[0], "bandas": caso["bandas"],
            "saldo": caso["saldo"], "ecl": ecl_caso,
            "sustento": sustento, "saldo_sin_tasa": saldo_sin_tasa_caso,
        })

    saldo_contable = sum(meta.values()) if ancla else None
    # La medición completa la hace el motor: matriz por segmento, deducción de
    # los casos individuales de su banda, conciliación y cuadro tributario. El
    # servicio orquesta y traduce; no vuelve a implementar el resumen.
    parametros_por_segmento = {
        s: ParametrosECL(
            tasas_perdida=aplicadas[s], lgd=1.0,
            ajuste_prospectivo=factor_prospectivo_aplicado[s] - 1.0,
            justificacion_ajuste=justificacion,
            fuente_tasas="Permanencia a 24 meses sobre la cohorte del corte más antiguo")
        for s in SEGMENTOS
    }
    resumen = resumen_deterioro(colectiva, parametros_por_segmento,
                                casos_individuales=lista_casos,
                                saldo_contable=saldo_contable,
                                exposiciones_brutas=deudora)
    tramos = resumen["colectivo"]["tramos"]
    individual = resumen["individual"]
    exp_negativa = resumen["colectivo"]["exposicion_negativa"]

    total_sin_estratificar = redondear(sum(sin_estratificar.values()))
    # Cartera que el lector no pudo leer en el CORTE ACTUAL (el que fija la
    # exposición). No es un detalle de trazabilidad: con anclaje a los estados
    # financieros, `factor = cartera_EEFF / total_del_archivo` absorbe el hueco,
    # así que cada dólar perdido aquí reaparece como exposición inventada sobre
    # las filas que sí entraron.
    descartado_en_lectura = redondear(actual["cartera_no_leida"])
    negativa_individual = sum(c["saldo"] for c in resumen["individual"]["casos"] if c["saldo"] < 0)
    exposicion = {
        "colectiva": resumen["colectivo"]["exposicion_total"],
        "individual": resumen["individual"]["saldo_total"],
        "sin_estratificar": total_sin_estratificar,
        "descartado_en_lectura": descartado_en_lectura,
        # Saldo acreedor (notas de crédito, anticipos) dentro de la cartera
        # medida: no genera "ganancia esperada", pero tampoco se esconde.
        "negativa": redondear(exp_negativa + negativa_individual),
        # Lo que no se midió en la matriz colectiva (bandas sin tasa) más lo que
        # no se midió en la evaluación individual (mismo motivo): nunca se
        # convierte en cero, se declara. Lo totaliza el motor.
        "sin_medir": resumen["exposicion_sin_medir"],
        # Cartera efectivamente medida: la estratificada menos lo sin medir. Es
        # la misma cifra que la pantalla rotula «Cartera medida» y que
        # `08-Conciliacion` B9 calcula como `=B5-B8`.
        "medida": resumen["exposicion_medida"],
        "total": redondear(resumen["exposicion_total"] + total_sin_estratificar),
        "segun_archivo": actual["total_saldo"],
        "factores_anclaje": factor,
    }

    politica = _comparar_politica(_diccionario(parametros.get("politica"), "politica"),
                                  bandas, tramos)
    hallazgos = _hallazgos(resumen, politica, parametros, factor_prospectivo_aplicado,
                           justificacion, exposicion, actual, ancla)
    pendientes = _pendientes(resumen, parametros, coh, leidos, sin_medir_individual, politica)

    return {
        "exposicion": exposicion, "tasas": tasas, "detalle_cohorte": coh["detalle"],
        "trazabilidad": coh["trazabilidad"], "anomalias": coh["anomalias"],
        "documentos_ambiguos": coh["documentos_ambiguos"],
        "documentos_ambiguos_total": coh["documentos_ambiguos_total"],
        # Contraste de la cohorte contra su rastro en el corte intermedio.
        "control_corte_intermedio": coh["control_corte_intermedio"],
        "matriz": resumen["colectivo"],
        "individual": resumen["individual"], "conciliacion": resumen.get("conciliacion", {
            "cartera_total": exposicion["total"], "saldo_contable": None,
            "diferencia": None, "cuadra": None}),
        "tributario": resumen["tributario"], "politica": politica,
        "ecl_total": resumen["ecl_total"],
        # Invariantes del motor, expuestas al producto: si la medición cubre
        # toda la cartera y qué proporción de LO MEDIDO representa la pérdida
        # (dividir entre el total diluiría el porcentaje con lo que no se midió).
        "medicion_completa": resumen["medicion_completa"],
        "porcentaje_sobre_cartera": resumen["porcentaje_sobre_cartera"],
        "hallazgos": hallazgos, "pendientes": pendientes,
        "bitacora": {
            "bandas": nombres, "umbral_incumplimiento": umbral_dias,
            "umbral_individual": umbral_ind,
            "cortes": [{"archivo": c["nombre"], "fecha": c["fecha"].isoformat(),
                        "hoja": l["hoja"], "fila_encabezado": l["fila_encabezado"],
                        "mapeo": l["mapeo"], "formato_fecha": l["formato_fecha"],
                        "documentos": len(l["filas"]), "duplicados_exactos": l["duplicados_exactos"],
                        "documentos_repetidos": l["documentos_repetidos"],
                        # El conteo de descartados se conserva (lo usa 02-Fuentes)
                        # y ahora va acompañado de su importe: sin él, la cartera
                        # que el lector no pudo leer desaparecía del papel.
                        "descartados": len(l["descartados"]),
                        "descartados_importe": l["descartados_importe"],
                        "descartados_por_motivo": l["descartados_por_motivo"],
                        "cartera_no_leida": l["cartera_no_leida"],
                        "total": l["total_saldo"]}
                       for c, l in zip(cortes, leidos)],
            "metodo": "Permanencia a 24 meses", "descuento": "No aplicado (NIIF 9 B5.5.44)",
        },
    }


def _comparar_politica(politica, bandas, tramos):
    """Compara la matriz observada contra la política fija del cliente.

    La política del cliente es un único porcentaje por banda (`{banda: tasa}`),
    sin distinción de segmento, así que aquí se agregan la exposición y el ECL
    de NO-RELACIONADOS y RELACIONADOS por banda antes de comparar. `tramos`
    trae una fila por cada combinación segmento/banda (los nombres de banda se
    repiten entre segmentos) y, como la matriz colectiva se inicializa con
    todas las bandas para ambos segmentos antes de medir, `tramos` ya cubre el
    universo completo banda x segmento, incluidas las combinaciones en cero.

    Dentro de cada banda, un segmento puede estar medido (tiene tasa, `ecl` no
    es `None`) y el otro sin medir (sin historia, `ecl` es `None`). Mezclar esa
    exposición sin medir en el mismo denominador que la medida diluye la tasa
    observada -justo la pérdida cero disfrazada que este módulo prohíbe-, así
    que aquí se acumulan por separado.

    Una banda cuya tasa de política NO se ingresó queda SIN COMPARAR
    (`sin_comparar`, con `tasa_politica`, `provision_politica` y `diferencia`
    en `None`): convertir lo desconocido en 0 % hacía que el papel acusara al
    cliente de no provisionar una banda que nunca se le preguntó. Lo que falta
    se declara como pendiente, no se rellena con cero.
    """
    por_banda: dict[str, dict[str, Any]] = {
        b["nombre"]: {"medida": 0.0, "sin_medir": 0.0, "ecl": None} for b in bandas
    }
    for t in tramos:
        datos = por_banda.setdefault(t["tramo"], {"medida": 0.0, "sin_medir": 0.0, "ecl": None})
        if t["ecl"] is None:
            datos["sin_medir"] += t["exposicion"]
        else:
            datos["medida"] += t["exposicion"]
            datos["ecl"] = t["ecl"] if datos["ecl"] is None else datos["ecl"] + t["ecl"]

    filas, total, sin_politica = [], 0.0, []
    for b in bandas:
        nombre = b["nombre"]
        datos = por_banda[nombre]
        exposicion_medida = datos["medida"]
        exposicion_sin_medir = datos["sin_medir"]
        exposicion = exposicion_medida + exposicion_sin_medir
        cruda = politica.get(nombre, politica.get(b["origen"]))
        if cruda is None or cruda == "":
            # El dato no existe: la banda no se compara. Un 0 % aquí sería una
            # afirmación sobre la política del cliente que nadie hizo.
            tasa = None
            provision = None
            sin_politica.append(nombre)
        else:
            tasa = _numero(cruda, f"politica['{nombre}']")
            if not 0 <= tasa <= 1:
                raise ValueError(
                    f"La tasa de política de la banda '{nombre}' es {tasa}: debe estar entre 0 y 1 "
                    "(0,02 = 2 %). Corrija la política de deterioro del cliente y vuelva a calcular."
                )
            # La provisión de la política se calcula sobre la exposición total
            # de la banda: es lo que el cliente provisiona hoy, mida o no mida
            # el auditor cada segmento.
            provision = redondear(exposicion * tasa)
            total += provision
        ecl = datos["ecl"]
        tasa_observada = (ecl / exposicion_medida) if (ecl is not None and exposicion_medida > 0) else None
        filas.append({"banda": nombre, "banda_origen": b["origen"], "exposicion": redondear(exposicion),
                      "exposicion_medida": redondear(exposicion_medida),
                      "exposicion_sin_medir": redondear(exposicion_sin_medir),
                      "tasa_politica": tasa, "provision_politica": provision, "ecl": ecl,
                      "tasa_observada": tasa_observada, "sin_comparar": tasa is None,
                      "diferencia": None if (ecl is None or tasa is None)
                                    else redondear(ecl - provision)})
    bruta = sum(abs(f["diferencia"]) for f in filas if f["diferencia"] is not None)
    return {"filas": filas, "provision_politica_total": redondear(total),
            "diferencia_bruta": redondear(bruta),
            # Bandas cuya tasa de política no se ingresó, y si la política quedó
            # declarada para TODAS las bandas.
            "bandas_sin_politica": sin_politica,
            "politica_declarada": not sin_politica}


def _hallazgos(resumen, politica, parametros, factor_prospectivo_aplicado, justificacion,
               exposicion=None, actual=None, ancla=False):
    h = []
    exposicion = exposicion or {}
    actual = actual or {}
    descartado = float(exposicion.get("descartado_en_lectura") or 0)
    if descartado > 0.005:
        motivos = ", ".join(
            f"{d['motivo']} ({d['filas']} fila{'s' if d['filas'] != 1 else ''}, "
            f"USD {d['importe']:,.2f})"
            for d in actual.get("descartados_por_motivo") or []
            if d["motivo"] != MOTIVO_FILA_REPETIDA)
        efecto = (f"La medición se hizo sobre USD {float(actual.get('total_saldo') or 0):,.2f} y no "
                  f"sobre el total del archivo.")
        if ancla:
            efecto += (" Además, con anclaje a los estados financieros el factor "
                       "cartera_EEFF / total_del_archivo absorbe el hueco: ese importe reaparece "
                       "como exposición repartida sobre las filas que sí se leyeron, y cambia la "
                       "mezcla por banda.")
        h.append({"titulo": "Cartera descartada en la lectura del corte actual", "riesgo": "Alto",
                  "condicion": f"USD {descartado:,.2f} del análisis de antigüedad del corte actual "
                               f"no se pudieron leer: {motivos}.",
                  "criterio": "NIIF 9 B5.5.35: la matriz se aplica sobre el importe en libros bruto "
                              "de TODA la cartera, no sobre la parte legible del archivo.",
                  "causa": "El archivo del cliente trae filas sin número de documento o sin fecha "
                           "de vencimiento, los dos datos que sostienen el método.",
                  "efecto": efecto,
                  "recomendacion": "Solicitar el análisis de antigüedad con número de documento y "
                                   "fecha de vencimiento en todas las filas, o depurar esas filas "
                                   "con el cliente antes de volver a calcular."})
    negativa = float(exposicion.get("negativa") or 0)
    if negativa < -0.005:
        h.append({"titulo": "Saldos acreedores en la cartera medida", "riesgo": "Alto",
                  "condicion": f"USD {abs(negativa):,.2f} de saldo acreedor (notas de crédito o "
                               "anticipos) dentro de la cartera que se mide.",
                  "criterio": "NIIF 9 5.5.15 y B5.5.35: la corrección de valor no puede ser "
                              "negativa ni superar el importe en libros bruto.",
                  "causa": "El análisis de antigüedad mezcla notas de crédito y anticipos de "
                           "clientes con las facturas por cobrar.",
                  "efecto": "Su pérdida esperada se fijó en 0,00: sin ese piso, esas bandas "
                            "restarían pérdida a las demás bandas del mismo segmento y la "
                            "corrección total quedaría subestimada.",
                  "recomendacion": "Reclasificar los saldos acreedores a pasivo (anticipos de "
                                   "clientes) o cruzarlos contra la factura que corrigen antes de "
                                   "medir."})
    acotada_techo = float(resumen["colectivo"].get("ecl_acotada_por_techo") or 0)
    if acotada_techo > 0.005:
        h.append({"titulo": "Pérdida esperada acotada al importe en libros bruto", "riesgo": "Alto",
                  "condicion": f"El cálculo daba USD {acotada_techo:,.2f} más de pérdida que la "
                               "exposición de sus bandas: la tasa ajustada por el factor "
                               "prospectivo superó el 100 %.",
                  "criterio": "NIIF 9 B5.5.35: la matriz se aplica sobre el importe en libros bruto.",
                  "causa": "El factor prospectivo solicitado lleva la tasa observada por encima de 1.",
                  "efecto": "La tasa se acotó al 100 % para que la cobertura no supere la cartera; "
                            "el factor tal como se pidió no es aplicable.",
                  "recomendacion": "Revisar el factor prospectivo con el socio: un factor que lleva "
                                   "la tasa sobre el 100 % indica que la banda ya está en pérdida "
                                   "total y el ajuste no aporta."})
    sin_ajuste_efectivo = not any(
        abs(float(v) - 1.0) > 1e-9 for v in factor_prospectivo_aplicado.values()
    )
    if sin_ajuste_efectivo or not justificacion.strip():
        h.append({"titulo": "Ausencia del componente prospectivo", "riesgo": "Alto",
                  "condicion": "La estimación no incorpora información sobre condiciones futuras: "
                               "el factor aplicado es 1,000.",
                  "criterio": "NIIF 9 párr. 5.5.17(c).",
                  "causa": "No se ha desarrollado un procedimiento para incorporar información "
                           "prospectiva, o el ajuste propuesto carece de justificación escrita.",
                  "efecto": "Incumplimiento de un requerimiento explícito de la norma.",
                  "recomendacion": "Documentar las variables prospectivas con fuente identificada y su traslación al factor."})
    # Sobre lo medido (tasa_observada), no sobre la exposición total de la banda:
    # dividir entre el total diluiría el porcentaje con la parte sin medir, que
    # es justo la dilución silenciosa que esta comparación evita.
    # Solo se compara contra lo que el cliente declaró: una banda sin política
    # ingresada queda fuera del hallazgo (antes su ausencia se convertía en 0 %
    # y el papel la acusaba de no provisionar). Su falta se declara como
    # pendiente en `_pendientes`.
    sub = [f for f in politica["filas"]
           if not f.get("sin_comparar") and f["tasa_politica"] == 0
           and f["tasa_observada"] is not None and f["tasa_observada"] > 0.05]
    if sub:
        h.append({"titulo": "Política de deterioro no sustentada en el comportamiento observado",
                  "riesgo": "Alto",
                  "condicion": "Bandas sin provisionar pese a registrar pérdida observada: " +
                               ", ".join(f["banda"] for f in sub) + ".",
                  "criterio": "NIIF 9 párr. 5.5.15 y B5.5.35.",
                  "causa": "La política se definió sobre criterios de gestión y no sobre el comportamiento de pago.",
                  "efecto": f"Diferencia bruta de {politica['diferencia_bruta']:,.2f}.",
                  "recomendacion": "Reemplazar los porcentajes fijos por la matriz derivada del comportamiento observado."})
    if resumen["colectivo"].get("exposicion_sin_medir", 0) > 0.005:
        h.append({"titulo": "Cartera sin tasa histórica", "riesgo": "Alto",
                  "condicion": f"Quedan {resumen['colectivo']['exposicion_sin_medir']:,.2f} sin medir por falta de historia en su banda.",
                  "criterio": "NIIF 9 B5.5.35: la matriz se sustenta en la experiencia propia de la entidad.",
                  "causa": "La cohorte no tiene documentos en esas bandas.",
                  "efecto": "La pérdida esperada no cubre la totalidad de la cartera.",
                  "recomendacion": "Resolver por analogía con un segmento comparable, dejando constancia, o declarar la limitación."})
    return h


def _pendientes(resumen, parametros, coh, leidos, sin_medir_individual=0.0, politica=None):
    p = []
    sin_politica = (politica or {}).get("bandas_sin_politica") or []
    if sin_politica:
        p.append({"variable": "Política de deterioro del cliente", "responsable": "Cliente",
                  "criticidad": "Alta",
                  "efecto": "La política de deterioro del cliente no fue proporcionada para "
                            f"{len(sin_politica)} banda(s) ({', '.join(sin_politica)}): esas "
                            "filas quedan SIN COMPARAR en 07-Politica. Sin el dato no se puede "
                            "concluir si la provisión registrada se aparta del comportamiento "
                            "observado, y suponerla en 0 % acusaría al cliente de algo que "
                            "nunca declaró."})
    if not parametros.get("materialidad"):
        p.append({"variable": "Materialidad de desempeño", "responsable": "Socio", "criticidad": "Alta",
                  "efecto": "Impide concluir sobre la significatividad del ajuste"})
    if not parametros.get("umbral_individual"):
        p.append({"variable": "Umbral de evaluación individual", "responsable": "Socio", "criticidad": "Alta",
                  "efecto": "Impide segregar de la matriz los saldos relevantes"})
    if sin_medir_individual > 0.005:
        p.append({"variable": "Saldos individuales sin tasa aplicable", "responsable": "Gerente / Socio",
                  "criticidad": "Alta",
                  "efecto": f"USD {sin_medir_individual:,.2f} de saldos evaluados individualmente caen en "
                            "bandas sin tasa observada y sin estimación propia justificada: su pérdida "
                            "provisional es 0,00 pero no está medida, no que no haya pérdida."})
    if not str(parametros.get("justificacion_prospectivo") or "").strip():
        p.append({"variable": "Información prospectiva documentada", "responsable": "Cliente",
                  "criticidad": "Alta", "efecto": "El factor permanece en 1,000"})
    if not parametros.get("mayor_provision"):
        p.append({"variable": "Mayores de la provisión de los tres ejercicios", "responsable": "Cliente",
                  "criticidad": "Alta",
                  "efecto": "Sin ellos no se puede demostrar que los castigos fueron inmateriales, y el método de permanencia queda sin sustento"})
    if coh.get("documentos_ambiguos_total"):
        total = coh["documentos_ambiguos_total"]
        ejemplos = ", ".join(d["documento"] for d in coh["documentos_ambiguos"][:5])
        p.append({"variable": "Número de documento no único", "responsable": "Cliente",
                  "criticidad": "Alta",
                  "efecto": f"{total} número(s) de documento aparecen con más de un cliente "
                            f"(por ejemplo: {ejemplos}). El método de permanencia rastrea la "
                            "cohorte por ese número, así que el saldo remanente -numerador de "
                            "todas las tasas- suma saldos de clientes distintos: la trazabilidad "
                            "queda invalidada de raíz, no solo reducida."})
    # El 1 % de la LORTI limita la provisión DEL EJERCICIO, y para conocerla
    # hace falta el movimiento de la provisión del período, que la herramienta
    # no recibe. Lo que no se puede medir se declara: el papel compara contra
    # el tope del 10 % acumulado y deja este pendiente.
    if not (resumen.get("tributario") or {}).get("limite_ejercicio_verificable"):
        p.append({"variable": "Movimiento de la provisión del ejercicio", "responsable": "Cliente",
                  "criticidad": "Alta",
                  "efecto": "Sin el movimiento de la provisión del período (saldo inicial, "
                            "dotación, uso y reversión) no se puede determinar la provisión DEL "
                            "EJERCICIO, así que el límite del 1 % de la LORTI art. 10 num. 11 no "
                            "se puede verificar. El papel contrasta la pérdida esperada acumulada "
                            "contra el tope del 10 %, que es el límite que sí corresponde a un "
                            "saldo acumulado."})
    control = coh.get("control_corte_intermedio") or {}
    if control.get("inconsistencias_total"):
        total = control["inconsistencias_total"]
        ejemplos = ", ".join(c["documento"] for c in control["inconsistencias"][:5])
        p.append({"variable": "Consistencia de la cohorte en el corte intermedio",
                  "responsable": "Cliente", "criticidad": "Alta",
                  "efecto": f"{total} documento(s) de la cohorte siguen una trayectoria imposible "
                            f"entre los tres cortes (por ejemplo: {ejemplos}): desaparecen en el "
                            "corte intermedio y reaparecen en el actual, o su saldo crece sin "
                            "facturación nueva. El remanente en el corte actual -numerador de "
                            f"todas las tasas- incluye USD {control['inconsistencias_importe']:,.2f} "
                            "de esos documentos, así que la permanencia medida no es la de la "
                            "cohorte original."})
    if coh["trazabilidad"] < 0.8:
        p.append({"variable": "Trazabilidad por número de documento", "responsable": "Cliente",
                  "criticidad": "Alta",
                  "efecto": f"Solo el {coh['trazabilidad']:.1%} de la cohorte se localizó en el corte actual: el método de cohortes podría no ser aplicable"})
    if coh.get("anomalias"):
        bandas_afectadas = ", ".join(f"{a['segmento']}/{a['banda']}" for a in coh["anomalias"])
        p.append({"variable": "Tasas de cohorte fuera de rango", "responsable": "Gerente / Socio",
                  "criticidad": "Alta",
                  "efecto": f"En {bandas_afectadas} el saldo remanente en el corte actual superó al "
                            "saldo inicial de la cohorte, o resultó negativo; la tasa se acotó entre "
                            "0 % y 100 % para poder medir, pero el origen del incremento (nueva "
                            "facturación reclasificada al mismo documento, reversión, error de "
                            "carga) debe explicarse antes de aceptar la matriz."})
    for l in leidos:
        if l["formato_fecha"] in ("ambiguo", "inconsistente"):
            p.append({"variable": f"Formato de fecha de {l['hoja']}", "responsable": "Equipo",
                      "criticidad": "Alta", "efecto": "Toda la mora depende del orden día/mes"})
    return p
