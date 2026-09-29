"""Consola-chat del piloto de planificación: el «agente» determinista.

Convierte el estado del ciclo de una prueba de planificación en un hilo de
mensajes tipo chat, con dos lados en la misma consola:

- **Preparador**: el agente le dice, paso a paso, qué documentos subir para que la
  prueba se pueda producir y cuándo procesarla y enviarla a revisión.
- **Auditor**: el agente le entrega el resultado y el veredicto de la consola de
  revisión (``consola_revision``) para que lo revise y apruebe.

Es determinista (decisión del dueño): los mensajes salen de lo que el ciclo ya
sabe (estado, documentos requeridos, huecos detectados, resultado del recálculo),
no de un modelo de lenguaje. No cambia nada: solo lee el estado y arma el guion.
Las respuestas de gobierno del encargo (independencia, aceptación, enfoque por
ciclo) se resuelven automáticamente y no se preguntan aquí.
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

    ``datos`` trae: ``estado``, ``cliente``, ``huecos`` (list[str]),
    ``pendientes`` (list[str] de documentos que faltan), ``recibidos``/``total``
    (conteo de documentos obligatorios), ``tiene_run`` (bool),
    ``conclusion_hecha`` (bool) y, en revisión, ``veredicto`` (str) con
    ``bloqueos``/``hallazgos``.
    """
    estado = datos.get("estado") or ""
    cliente = datos.get("cliente") or "el cliente"
    huecos = datos.get("huecos") or []
    fase = fase_de(estado, huecos)
    es_auditor = rol == "auditor"

    mensajes: list[dict] = [
        _msg("agente", f"Planificación de auditoría de {cliente}. Yo te voy guiando; la independencia del equipo y el "
                       "enfoque por ciclo ya quedan resueltos por política de la firma, así que no hace falta llenarlos."),
    ]
    siguiente: dict = {}

    if fase == FASE_DOCUMENTOS:
        pendientes = datos.get("pendientes") or huecos
        lista = "\n".join(f"• {d}" for d in pendientes) if pendientes else "• (todos los documentos requeridos)"
        mensajes.append(_msg("agente", "Para producir la planificación necesito estos documentos del cliente. "
                                        f"Súbelos aquí:\n{lista}"))
        recibidos, total = datos.get("recibidos"), datos.get("total")
        if isinstance(recibidos, int) and isinstance(total, int) and total:
            mensajes.append(_msg("agente", f"Llevas {recibidos} de {total} documentos obligatorios."))
        siguiente = {"fase": fase, "rol": "preparador", "accion": "subir", "etiqueta": "Subir documentos"}

    elif fase == FASE_PROCESAR:
        mensajes.append(_msg("agente", "Ya tengo los documentos. Con un clic preparo el programa, valido y concilio la "
                                       "información y produzco toda la planificación (índices, materialidad, riesgos, "
                                       "programa)."))
        siguiente = {"fase": fase, "rol": "preparador", "accion": "procesar", "etiqueta": "Producir la planificación"}

    elif fase == FASE_ENVIAR:
        mensajes.append(_msg("agente", "La planificación está producida. La reviso y, si está conforme, la envío al "
                                       "auditor para su veredicto."))
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
                    mensajes.append(_msg("agente", "El recálculo coincide con el motor y el balance cuadra. La aprobación "
                                                   "final es tu decisión (compuerta del socio)."))
                    siguiente = {"fase": fase, "rol": "auditor", "accion": "aprobar", "etiqueta": "Aprobar la planificación"}
            else:
                mensajes.append(_msg("agente", "La planificación está en revisión. Corro el recálculo independiente y te "
                                               "doy el veredicto."))
                siguiente = {"fase": fase, "rol": "auditor", "accion": "revisar", "etiqueta": "Revisar la planificación"}
        else:
            mensajes.append(_msg("agente", "La planificación ya está con el auditor. Cambia al lado «Auditor» para ver el "
                                           "veredicto, o espera su revisión."))
            siguiente = {"fase": fase, "rol": "auditor", "accion": "esperar", "etiqueta": "En revisión del auditor"}

    elif fase == FASE_APROBADA:
        quien = datos.get("aprobada_por")
        mensajes.append(_msg("agente", "Planificación aprobada" + (f" por {quien}" if quien else "") +
                             ". Puedes descargar el papel (Excel, Word, PowerPoint, HTML/PDF)."))
        siguiente = {"fase": fase, "rol": "auditor", "accion": "descargar", "etiqueta": "Descargar el papel"}

    return {"fase": fase, "rol": rol, "mensajes": mensajes, "siguiente": siguiente}
