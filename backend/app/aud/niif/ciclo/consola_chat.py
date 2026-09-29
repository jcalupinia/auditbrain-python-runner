"""Consola-chat de las pruebas del encargo: el «agente» determinista.

Convierte el estado del ciclo de una prueba (la planificación NIA o cualquiera de
las 20 herramientas del catálogo) en un hilo de mensajes tipo chat, con dos lados
en la misma consola:

- **Preparador**: el agente le dice, paso a paso, qué documentos subir para que la
  prueba se pueda producir y cuándo procesarla y enviarla a revisión.
- **Auditor**: el agente le entrega el resultado y el veredicto de la consola de
  revisión (``consola_revision`` para la planificación; ``revision.base`` para las
  demás herramientas) para que lo revise y apruebe.

Es determinista (decisión del dueño): los mensajes salen de lo que el ciclo ya
sabe (estado, documentos requeridos, huecos detectados, resultado del recálculo),
no de un modelo de lenguaje. No cambia nada: solo lee el estado y arma el guion.
En la planificación, las respuestas de gobierno del encargo (independencia,
aceptación, enfoque por ciclo) se resuelven automáticamente y no se preguntan aquí.
"""
from __future__ import annotations

# Fases del piloto, en el orden en que el preparador y el auditor las viven.
FASE_DOCUMENTOS = "documentos"       # faltan documentos del cliente
FASE_PROCESAR = "procesar"           # documentos completos, falta producir la planificación
FASE_ENVIAR = "enviar"               # producida, falta enviarla a revisión del auditor
FASE_REVISAR = "revisar"             # en revisión: el auditor corre el veredicto y aprueba
FASE_APROBADA = "aprobada"           # cerrada

# Estados del ciclo agrupados por fase del chat.
_ANTES_DE_DATOS = ("PRUEBA_SELECCIONADA", "PROGRAMA_PROPUESTO", "PROGRAMA_APROBADO", "REQUERIMIENTO_GENERADO")
_SUBIENDO = ("REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA")
_LISTA_PARA_PROCESAR = ("DOCUMENTACION_VALIDADA", "PRUEBA_CONFIGURADA", "METODOLOGIA_APROBADA")
_PRODUCIDA = ("PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS")


def fase_de(estado: str, huecos: list | None) -> str:
    """Fase del chat a la que corresponde el estado del ciclo."""
    if estado == "APROBADO":
        return FASE_APROBADA
    if estado == "EN_REVISION":
        return FASE_REVISAR
    if estado in _PRODUCIDA:
        return FASE_ENVIAR
    if estado in _LISTA_PARA_PROCESAR:
        return FASE_PROCESAR
    # Antes del requerimiento o subiendo: si aún faltan documentos, es fase de documentos;
    # si ya están todos, se puede procesar de una.
    if huecos:
        return FASE_DOCUMENTOS
    if estado in _SUBIENDO:
        return FASE_PROCESAR
    return FASE_DOCUMENTOS


def _msg(de: str, texto: str) -> dict:
    return {"de": de, "texto": texto}


def guion(datos: dict, rol: str = "preparador") -> dict:
    """Hilo de mensajes y siguiente acción para la consola-chat.

    ``datos`` trae: ``estado``, ``cliente``, ``prueba`` (nombre de la herramienta),
    ``es_planificacion`` (bool), ``huecos`` (list[str]), ``pendientes`` (list[str]
    de documentos que faltan), ``recibidos``/``total`` (conteo de documentos
    obligatorios), ``tiene_run`` (bool), ``conclusion_hecha`` (bool) y, en revisión,
    ``veredicto`` (str) con ``bloqueos``/``hallazgos``.
    """
    estado = datos.get("estado") or ""
    cliente = datos.get("cliente") or "el cliente"
    prueba = datos.get("prueba") or "la prueba"
    es_plan = bool(datos.get("es_planificacion"))
    huecos = datos.get("huecos") or []
    fase = fase_de(estado, huecos)
    es_auditor = rol == "auditor"

    # El nombre de la prueba se usa como sustantivo femenino («la planificación», «la prueba de …»).
    ella = "la planificación" if es_plan else f"la prueba «{prueba}»"
    presentacion = f"{prueba} — auditoría de {cliente}. Yo te voy guiando por el proceso."
    if es_plan:
        presentacion += (" La independencia del equipo y el enfoque por ciclo ya quedan resueltos por política de la "
                         "firma, así que no hace falta llenarlos.")
    mensajes: list[dict] = [_msg("agente", presentacion)]
    siguiente: dict = {}

    if fase == FASE_DOCUMENTOS:
        pendientes = datos.get("pendientes") or huecos
        lista = "\n".join(f"• {d}" for d in pendientes) if pendientes else "• (todos los documentos requeridos)"
        mensajes.append(_msg("agente", f"Para producir {ella} necesito estos documentos del cliente. "
                                        f"Súbelos aquí:\n{lista}"))
        recibidos, total = datos.get("recibidos"), datos.get("total")
        if isinstance(recibidos, int) and isinstance(total, int) and total:
            mensajes.append(_msg("agente", f"Llevas {recibidos} de {total} documentos obligatorios."))
        siguiente = {"fase": fase, "rol": "preparador", "accion": "subir", "etiqueta": "Subir documentos"}

    elif fase == FASE_PROCESAR:
        que_produce = ("toda la planificación (índices, materialidad, riesgos, programa)" if es_plan
                       else "todo el papel de trabajo (cédulas, conciliación, ajuste propuesto y hallazgos)")
        mensajes.append(_msg("agente", "Ya tengo los documentos. Con un clic preparo el programa, valido y concilio la "
                                       f"información y produzco {que_produce}."))
        siguiente = {"fase": fase, "rol": "preparador", "accion": "procesar",
                     "etiqueta": "Producir la planificación" if es_plan else "Producir la prueba"}

    elif fase == FASE_ENVIAR:
        mensajes.append(_msg("agente", f"{ella[0].upper()}{ella[1:]} está producida. La reviso y, si está conforme, la "
                                       "envío al auditor para su veredicto."))
        siguiente = {"fase": fase, "rol": "preparador", "accion": "enviar", "etiqueta": "Enviar a revisión del auditor"}

    elif fase == FASE_REVISAR:
        if es_auditor:
            veredicto = datos.get("veredicto")
            if veredicto:
                mensajes.append(_msg("agente", f"Veredicto del recálculo independiente: {veredicto}."))
                for b in datos.get("bloqueos") or []:
                    mensajes.append(_msg("agente", f"⛔ {b}"))
                for h in datos.get("hallazgos") or []:
                    mensajes.append(_msg("agente", f"⚠ {h}"))
                if veredicto == "NO APTO":
                    mensajes.append(_msg("agente", "No recomiendo aprobar hasta resolver lo anterior. Puedes devolverla "
                                                   "al preparador."))
                    siguiente = {"fase": fase, "rol": "auditor", "accion": "devolver", "etiqueta": "Devolver al preparador"}
                else:
                    coincide = ("El recálculo coincide con el motor y el balance cuadra." if es_plan
                                else "El recálculo independiente coincide con el motor y el papel está completo.")
                    mensajes.append(_msg("agente", f"{coincide} La aprobación final es tu decisión (compuerta del socio)."))
                    siguiente = {"fase": fase, "rol": "auditor", "accion": "aprobar",
                                 "etiqueta": "Aprobar la planificación" if es_plan else "Aprobar la prueba"}
            else:
                mensajes.append(_msg("agente", f"{ella[0].upper()}{ella[1:]} está en revisión. Corro el recálculo "
                                               "independiente y te doy el veredicto."))
                siguiente = {"fase": fase, "rol": "auditor", "accion": "revisar",
                             "etiqueta": "Revisar la planificación" if es_plan else "Revisar la prueba"}
        else:
            mensajes.append(_msg("agente", f"{ella[0].upper()}{ella[1:]} ya está con el auditor. Cambia al lado «Auditor» "
                                           "para ver el veredicto, o espera su revisión."))
            siguiente = {"fase": fase, "rol": "auditor", "accion": "esperar", "etiqueta": "En revisión del auditor"}

    elif fase == FASE_APROBADA:
        quien = datos.get("aprobada_por")
        titulo = "Planificación aprobada" if es_plan else f"Prueba «{prueba}» aprobada"
        mensajes.append(_msg("agente", titulo + (f" por {quien}" if quien else "") +
                             ". Puedes descargar el papel (Excel, Word, PowerPoint, HTML/PDF)."))
        siguiente = {"fase": fase, "rol": "auditor", "accion": "descargar", "etiqueta": "Descargar el papel"}

    return {"fase": fase, "rol": rol, "mensajes": mensajes, "siguiente": siguiente}
