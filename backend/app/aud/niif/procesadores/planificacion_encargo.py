"""Planificación de la auditoría · documentación del encargo que prepara el equipo de auditoría (complemento de
``planificacion_nia``; no es una herramienta del catálogo por sí sola).

Cubre los faltantes A1–A19 de la revisión de control de calidad frente a las NIA:

- Cuestionario de planificación (RQ-010): aceptación y continuidad (NIGC 1, NIA 220), condiciones previas y carta de
  encargo (NIA 210), materialidad específica (NIA 320 párr. 10), comunicación con el gobierno (NIA 260), discusión del
  equipo (NIA 315, NIA 240), indagaciones y factores de riesgo de fraude (NIA 240), componentes del control interno y
  controles generales de TI (NIA 315 Revisada 2019).
- Equipo del encargo e independencia (RQ-011): confirmaciones, amenazas y salvaguardas, rotación del socio en entidades
  de interés público y revisor de calidad del encargo (NIGC 2).
- Diferencias de auditoría (RQ-012, NIA 450) y componentes del grupo (RQ-013, NIA 600 Revisada).

Regla de cero invención: lo que el equipo no documentó queda «[PENDIENTE]» y el control de calidad (hoja 16) lo cuenta;
nunca se completa por inferencia. Los porcentajes (confianza, error esperado, componente, rotación) son política de la
firma y los párrafos citados llevan «VERIFICAR» hasta cotejarlos con el texto oficial vigente.
"""
from __future__ import annotations

import math

from backend.app.aud.niif.procesadores.base import FILA0, a_fecha, a_num, campo, fx, n2, norm

PENDIENTE = "[PENDIENTE]"
SI, NO = "Sí", "No"
ADECUADO, DEFICIENCIAS, NO_APLICA = "Adecuado", "Con deficiencias", "No aplica"
ORIGEN_CUESTIONARIO = "Cuestionario de planificación (RQ-010)"

H24, H25, H26, H27, H28, H29, H30, H31, H32 = (
    "24_Aceptacion", "25_Equipo", "26_Discusion_Fraude", "27_Control_Interno", "28_Afirmaciones", "29_Muestreo",
    "30_Diferencias", "31_Grupo", "32_Comunicacion")
CEDULAS = [
    (H24, "Aceptación y continuidad, condiciones previas y carta de encargo, materialidad específica y comunicación (NIGC 1; "
          "NIA 210, 220, 260 y 320)"),
    (H25, "Equipo del encargo, independencia, amenazas y salvaguardas, rotación y revisor de calidad (IESBA; NIA 220; NIGC 2)"),
    (H26, "Discusión del equipo e indagaciones y factores de riesgo de fraude (NIA 315 y 240)"),
    (H27, "Componentes del control interno y controles generales de TI (NIA 315 Revisada 2019)"),
    (H28, "Valoración del riesgo por afirmación y a nivel de estados financieros (NIA 315 y 330)"),
    (H29, "Extensión y tamaño de la muestra por cuenta (NIA 330 y 530)"),
    (H30, "Sumario de diferencias de auditoría (NIA 450)"),
    (H31, "Auditoría de grupo: componentes y materialidad del componente (NIA 600 Revisada)"),
    (H32, "Comunicación de la planificación a los responsables del gobierno y asuntos clave candidatos (NIA 260 y 701)"),
]

# --- cuestionario de planificación ----------------------------------------------------------------------------------
BLOQUES = {
    "ACE": ("Aceptación y continuidad", H24), "CON": ("Condiciones previas y carta de encargo", H24),
    "MES": ("Materialidad específica", H24), "COM": ("Comunicación con el gobierno", H24),
    "DIS": ("Discusión del equipo del encargo", H26), "FRA": ("Fraude: indagaciones y factores de riesgo", H26),
    "CI": ("Componentes del control interno", H27), "TI": ("Controles generales de TI", H27),
}
TIPOS_RESPUESTA = ("sino", "evaluacion", "texto", "fecha", "numero")


def _q(codigo, pregunta, norma, tipo="texto", esperado=None, sev="", nia="", alerta="", resp="", eeff=False, aplica=""):
    """Pregunta del cuestionario. ``esperado`` (sino) o ``tipo == "evaluacion"`` definen cuándo hay alerta; ``nia`` es la
    norma corta de la hoja 13; ``eeff`` marca los riesgos a nivel de estados financieros (hoja 28); ``aplica`` = parámetro
    Sí/No del que depende (si vale «No», la pregunta no aplica)."""
    return {"codigo": codigo, "bloque": BLOQUES[codigo.split("-")[0]][0], "hoja": BLOQUES[codigo.split("-")[0]][1],
            "pregunta": pregunta, "norma": norma, "tipo": tipo, "esperado": esperado, "sev": sev, "nia": nia, "alerta": alerta,
            "resp": resp, "eeff": eeff, "aplica": aplica}


_CONDICION = ("Condición previa del encargo no cumplida (NIA 210 párr. 6): no aceptar el encargo salvo que la ley lo exija; "
              "tratarlo con la dirección y el gobierno.")
_RESP_CONDICION = "Obtener el acuerdo de la dirección sobre sus responsabilidades antes de aceptar (NIA 210 párr. 6 y 8)."
_FACTOR_FRAUDE = ("Respuesta global: escepticismo reforzado, elemento de imprevisibilidad y pruebas de asientos de diario, "
                  "estimaciones y transacciones inusuales (NIA 240 párr. 28–33 — VERIFICAR).")
_DEF_CI = ("Deficiencias en {x}: considerarlas en la valoración de los riesgos y comunicar las significativas por escrito "
           "(NIA 265).")
_RESP_CI = "Evaluar si son deficiencias significativas, no confiar en esos controles y ampliar las pruebas sustantivas del área."
_DEF_TI = ("Deficiencias en los controles generales de TI ({x}): no confiar en controles automáticos ni en informes del sistema "
           "sin probar su integridad y exactitud.")
_RESP_TI = "Probar la integridad y exactitud de los informes usados como evidencia; considerar un especialista en TI (NIA 620)."

CUESTIONARIO = [
    _q("ACE-01", "¿Se evaluó la integridad de los propietarios principales, la dirección y los responsables del gobierno, sin "
                 "asuntos que impidan aceptar o continuar el encargo?", "NIGC 1; NIA 220 (Revisada) párr. 22–24 (VERIFICAR)",
       "sino", SI, "Alto", "NIA 220",
       "Integridad de la dirección no evaluada o con reservas: riesgo de fraude a nivel de estados financieros y de continuidad "
       "del encargo.", "Consultar con el socio antes de continuar y reforzar el escepticismo profesional (NIA 220; NIA 240).", True),
    _q("ACE-02", "¿La firma tiene la competencia, la capacidad, el tiempo y los recursos (incluidos expertos) para el encargo?",
       "NIGC 1; NIA 220 (Revisada) párr. 25–26 (VERIFICAR)", "sino", SI, "Alto", "NIA 220",
       "La firma no confirma competencia o recursos suficientes para el encargo.",
       "Asignar el personal o los expertos necesarios antes de iniciar y documentar la decisión del socio (NIGC 1)."),
    _q("ACE-03", "¿Se cumplen los requerimientos de ética aplicables, incluida la independencia de la firma y del equipo?",
       "Código IESBA; NIA 220 (Revisada) párr. 16–21 (VERIFICAR)", "sino", SI, "Alto", "NIA 220",
       "Requerimientos de ética o de independencia no confirmados: no se puede emitir el informe hasta resolverlo.",
       "Eliminar las amenazas o aplicar salvaguardas; si no es posible, no aceptar o renunciar al encargo."),
    _q("ACE-04", "¿Hubo asuntos significativos en el encargo anterior o en la aceptación que pongan en duda la continuidad?",
       "NIGC 1; NIA 220 (Revisada) párr. 23 (VERIFICAR)", "sino", NO, "Medio", "NIA 220",
       "Asuntos del encargo anterior o de la aceptación que afectan la continuidad: considerarlos en la estrategia.",
       "Documentar cómo se resolvieron y su efecto en los riesgos del año."),
    _q("ACE-05", "Encargo inicial: ¿se comunicó con el auditor predecesor y se revisaron sus papeles de trabajo?",
       "NIA 510 párr. 6; NIA 300 párr. 13; Código IESBA (VERIFICAR)", "sino", SI, "Alto", "NIA 510",
       "Encargo inicial sin comunicación con el auditor predecesor: los saldos de apertura requieren procedimientos propios.",
       "Comunicarse con el predecesor o aplicar procedimientos sustantivos a los saldos de apertura (NIA 510 párr. 6).",
       aplica="encargoInicial"),
    _q("ACE-06", "Fecha de la decisión de aceptar o continuar el encargo (aprobada por el socio)", "NIGC 1; NIA 220 (Revisada)",
       "fecha"),
    _q("CON-01", "¿El marco de información financiera aplicable es aceptable?", "NIA 210 párr. 6 a)", "sino", SI, "Alto", "NIA 210",
       _CONDICION, _RESP_CONDICION, True),
    _q("CON-02", "¿La dirección reconoce su responsabilidad por la preparación de los estados financieros conforme al marco?",
       "NIA 210 párr. 6 b) i)", "sino", SI, "Alto", "NIA 210", _CONDICION, _RESP_CONDICION, True),
    _q("CON-03", "¿La dirección reconoce su responsabilidad por el control interno necesario para prepararlos libres de "
                 "incorrección material?", "NIA 210 párr. 6 b) ii)", "sino", SI, "Alto", "NIA 210", _CONDICION, _RESP_CONDICION, True),
    _q("CON-04", "¿La dirección reconoce su responsabilidad de dar acceso a toda la información, a la información adicional "
                 "solicitada y a las personas de la entidad?", "NIA 210 párr. 6 b) iii)", "sino", SI, "Alto", "NIA 210",
       _CONDICION, _RESP_CONDICION, True),
    _q("CON-05", "¿La dirección impuso limitaciones al alcance del trabajo del auditor?", "NIA 210 párr. 7; NIA 705", "sino", NO,
       "Alto", "NIA 210",
       "Limitación al alcance impuesta por la dirección: puede impedir emitir una opinión (NIA 210 párr. 7; NIA 705).",
       "Pedir a la dirección que retire la limitación; si no la retira, no aceptar o evaluar el efecto en la opinión.", True),
    _q("CON-06", "Fecha de la carta de encargo firmada", "NIA 210 párr. 9–10", "fecha"),
    _q("CON-07", "Firmantes de la carta de encargo (por la entidad y por la firma)", "NIA 210 párr. 10"),
    _q("MES-01", "¿Hay transacciones, saldos o revelaciones que requieren una materialidad inferior (partes relacionadas, "
                 "remuneración de la dirección, revelaciones sensibles)?", "NIA 320 párr. 10 y A10–A11 (VERIFICAR)", "sino"),
    _q("MES-02", "Partidas con materialidad específica y su justificación", "NIA 320 párr. 10 y 14"),
    _q("MES-03", "Importe de la materialidad específica (USD)", "NIA 320 párr. 10", "numero"),
    _q("COM-01", "Fecha de la comunicación de la planificación a los responsables del gobierno", "NIA 260 (Revisada) párr. 15",
       "fecha"),
    _q("COM-02", "Medio y destinatarios de la comunicación (reunión, carta o acta)", "NIA 260 (Revisada) párr. 18–19 (VERIFICAR)"),
    _q("DIS-01", "Fecha de la discusión del equipo del encargo", "NIA 315 (Revisada 2019) párr. 17; NIA 240 párr. 15 (VERIFICAR)",
       "fecha"),
    _q("DIS-02", "Asistentes a la discusión (incluidos el socio y los miembros clave del equipo)", "NIA 315 (Revisada 2019) párr. 17"),
    _q("DIS-03", "Temas tratados: susceptibilidad de los estados financieros a incorrección material, incluida la debida a fraude",
       "NIA 315 (Revisada 2019) párr. 17; NIA 240 párr. 15 (VERIFICAR)"),
    _q("DIS-04", "Conclusiones y riesgos identificados en la discusión", "NIA 315 (Revisada 2019) párr. 17; NIA 230"),
    _q("DIS-05", "¿Participó el socio del encargo en la discusión?", "NIA 315 (Revisada 2019) párr. 17 (VERIFICAR)", "sino", SI,
       "Medio", "NIA 315",
       "El socio no participó en la discusión del equipo: debe dirigirla o conocer y aprobar sus conclusiones.",
       "Documentar la participación del socio o una reunión complementaria con él."),
    _q("FRA-01", "Indagación a la dirección: su valoración del riesgo de fraude y cómo lo identifica y responde",
       "NIA 240 párr. 17 (VERIFICAR)"),
    _q("FRA-02", "¿La dirección tiene conocimiento de fraude real, presunto o denunciado que afecte a la entidad?",
       "NIA 240 párr. 18 (VERIFICAR)", "sino", NO, "Significativo", "NIA 240",
       "Fraude real, presunto o denunciado conocido por la dirección: riesgo significativo de incorrección material debida a "
       "fraude.", "Evaluar el efecto en los estados financieros, comunicarlo al gobierno y diseñar procedimientos específicos "
                  "(NIA 240).", True),
    _q("FRA-03", "Indagación a los responsables del gobierno: cómo supervisan el riesgo de fraude y si conocen fraudes",
       "NIA 240 párr. 20–21 (VERIFICAR)"),
    _q("FRA-04", "Indagación a la auditoría interna (si existe; si no, «No aplica»)", "NIA 240 párr. 19 (VERIFICAR)"),
    _q("FRA-05", "Factor de riesgo · incentivos o presiones (metas, covenants, bonos atados a resultados): ¿se identificaron?",
       "NIA 240 párr. 24 y Anexo 1 (VERIFICAR)", "sino", NO, "Alto", "NIA 240",
       "Incentivos o presiones para manipular la información financiera: factor de riesgo de fraude.", _FACTOR_FRAUDE, True),
    _q("FRA-06", "Factor de riesgo · oportunidades (controles débiles, transacciones complejas, dominio de una sola persona): "
                 "¿se identificaron?", "NIA 240 párr. 24 y Anexo 1 (VERIFICAR)", "sino", NO, "Alto", "NIA 240",
       "Oportunidades para cometer fraude: factor de riesgo de fraude.", _FACTOR_FRAUDE, True),
    _q("FRA-07", "Factor de riesgo · actitudes o racionalización (incumplimientos previos, relación tensa con el auditor): "
                 "¿se identificaron?", "NIA 240 párr. 24 y Anexo 1 (VERIFICAR)", "sino", NO, "Alto", "NIA 240",
       "Actitudes o racionalización de la dirección: factor de riesgo de fraude.", _FACTOR_FRAUDE, True),
    _q("CI-01", "Entorno de control (integridad, valores éticos, supervisión del gobierno, estructura y competencia)",
       "NIA 315 (Revisada 2019) párr. 21 (VERIFICAR)", "evaluacion", sev="Alto", nia="NIA 315",
       alerta="Deficiencias en el entorno de control: riesgo a nivel de estados financieros; no confiar en los controles y "
              "ampliar las pruebas sustantivas.",
       resp="Respuesta global (NIA 330 párr. 5) y comunicación de las deficiencias significativas (NIA 265).", eeff=True),
    _q("CI-02", "Proceso de valoración del riesgo de la entidad", "NIA 315 (Revisada 2019) párr. 22–23 (VERIFICAR)", "evaluacion",
       sev="Medio", nia="NIA 315", alerta=_DEF_CI.format(x="el proceso de valoración del riesgo de la entidad"), resp=_RESP_CI),
    _q("CI-03", "Proceso de seguimiento del sistema de control interno", "NIA 315 (Revisada 2019) párr. 24 (VERIFICAR)",
       "evaluacion", sev="Medio", nia="NIA 315", alerta=_DEF_CI.format(x="el seguimiento del control interno"), resp=_RESP_CI),
    _q("CI-04", "Sistema de información y comunicación relevante para la información financiera",
       "NIA 315 (Revisada 2019) párr. 25 (VERIFICAR)", "evaluacion", sev="Medio", nia="NIA 315",
       alerta=_DEF_CI.format(x="el sistema de información y comunicación"), resp=_RESP_CI),
    _q("CI-05", "Actividades de control: diseño e implementación de los controles relevantes para los riesgos identificados",
       "NIA 315 (Revisada 2019) párr. 26 (VERIFICAR)", "evaluacion", sev="Medio", nia="NIA 315",
       alerta=_DEF_CI.format(x="las actividades de control"), resp=_RESP_CI),
    _q("TI-01", "Aplicaciones y sistemas relevantes para la información financiera (ERP, nómina, facturación, bancos)",
       "NIA 315 (Revisada 2019) párr. 26 b) (VERIFICAR)"),
    _q("TI-02", "Riesgos derivados del uso de TI identificados", "NIA 315 (Revisada 2019) párr. 26 c) (VERIFICAR)"),
    _q("TI-03", "Gestión de accesos (altas, bajas, privilegios y segregación de funciones en el sistema)",
       "NIA 315 (Revisada 2019) párr. 26 d) y A166–A172 (VERIFICAR)", "evaluacion", sev="Medio", nia="NIA 315",
       alerta=_DEF_TI.format(x="accesos"), resp=_RESP_TI),
    _q("TI-04", "Gestión de cambios en programas y configuraciones", "NIA 315 (Revisada 2019) párr. 26 d) (VERIFICAR)",
       "evaluacion", sev="Medio", nia="NIA 315", alerta=_DEF_TI.format(x="cambios en programas"), resp=_RESP_TI),
    _q("TI-05", "Operaciones de TI (respaldos, gestión de incidentes y procesos programados)",
       "NIA 315 (Revisada 2019) párr. 26 d) (VERIFICAR)", "evaluacion", sev="Medio", nia="NIA 315",
       alerta=_DEF_TI.format(x="operaciones"), resp=_RESP_TI),
]
POR_CODIGO = {q["codigo"]: q for q in CUESTIONARIO}
HOJAS_CUESTIONARIO = (H24, H26, H27)
# Fila de cada pregunta en su hoja (orden fijo del catálogo): la usan las hojas 11, 13, 16, 21 y 32.
FILA_Q = {}
for _h in HOJAS_CUESTIONARIO:
    for _i, _x in enumerate(q for q in CUESTIONARIO if q["hoja"] == _h):
        FILA_Q[_x["codigo"]] = (_h, FILA0 + _i)
COLS_CUESTIONARIO = [["Bloque", "t"], ["Código", "t"], ["Pregunta o aspecto", "t"], ["Norma", "t"], ["Respuesta", "x"],
                     ["Detalle o evidencia", "t"], ["Fecha", "d"], ["Responsable", "t"], ["Estado", "t"]]

# --- equipo, diferencias y componentes ------------------------------------------------------------------------------
ROLES = ("Socio", "Gerente", "Senior", "Asistente", "Revisor de calidad", "Experto", "Otro")
TIPOS_DIF = ("Factual", "De juicio", "Proyectada")
PERIODOS_DIF = ("Actual", "Anterior")
ROLES_GRUPO = ("Auditor del grupo", "Auditor de un componente")
ESTADOS_ANTERIORES = ("Auditados por nosotros", "Auditados por otro auditor", "No auditados")

_CUEST = [
    campo("codigo", "Código de la pregunta", alias=("codigo", "código", "cod", "ref", "referencia", "id"), ejemplo="ACE-01"),
    campo("pregunta", "Pregunta (referencia; no se usa en el cálculo)", requerido=False, alias=("pregunta", "aspecto"),
          ejemplo="¿Se evaluó la integridad de los propietarios principales, la dirección y los responsables del gobierno…?"),
    campo("respuesta", "Respuesta", requerido=False,
          alias=("respuesta", "conclusion", "conclusión", "evaluacion", "evaluación", "valor", "resultado"), ejemplo="Sí"),
    campo("detalle", "Detalle o evidencia", requerido=False,
          alias=("detalle", "evidencia", "comentario", "observacion", "observación", "sustento"),
          ejemplo="Consulta de antecedentes y reunión con el directorio; sin reservas."),
    campo("fecha", "Fecha", "date", requerido=False, alias=("fecha", "fecha de la respuesta"), ejemplo="2025-09-15"),
    campo("responsable", "Responsable", requerido=False, alias=("responsable", "preparado por", "quien", "quién", "elaborado por"),
          ejemplo="CPA Andrea Vélez (ficticio)"),
]
_EQUIPO = [
    campo("integrante", "Integrante", alias=("integrante", "nombre", "miembro", "persona"), ejemplo="CPA Andrea Vélez (ficticio)"),
    campo("rol", "Rol en el encargo", alias=("rol", "cargo", "funcion", "función"), ejemplo="Socio"),
    campo("independencia", "¿Confirmó su independencia? (Sí/No)", requerido=False,
          alias=("independencia", "confirmo independencia", "confirmó independencia", "declaracion de independencia"), ejemplo="Sí"),
    campo("fecha_confirmacion", "Fecha de la confirmación", "date", requerido=False,
          alias=("fecha", "fecha de confirmacion", "fecha de confirmación"), ejemplo="2025-09-10"),
    campo("amenazas", "Amenazas identificadas", requerido=False, alias=("amenazas", "amenaza"), ejemplo=""),
    campo("salvaguardas", "Salvaguardas aplicadas", requerido=False, alias=("salvaguardas", "salvaguarda", "medidas"), ejemplo=""),
    campo("anios", "Años en el encargo", "number", requerido=False, alias=("anios", "años", "años en el encargo", "antiguedad"),
          ejemplo="3"),
    campo("horas", "Horas presupuestadas", "number", requerido=False, alias=("horas", "presupuesto de horas", "horas presupuestadas"),
          ejemplo="120"),
]
_DIFS = [
    campo("referencia", "Referencia", alias=("referencia", "ref", "id", "codigo del ajuste", "código del ajuste"), ejemplo="AJ-01"),
    campo("codigo", "Cuenta afectada (código)", requerido=False, alias=("codigo", "código", "cuenta"), ejemplo="5101"),
    campo("descripcion", "Descripción", alias=("descripcion", "descripción", "detalle", "concepto"),
          ejemplo="Provisión de jubilación patronal no ajustada al cálculo actuarial."),
    campo("tipo", "Tipo (Factual / De juicio / Proyectada)", requerido=False, alias=("tipo", "clase", "naturaleza"), ejemplo="Factual"),
    campo("importe", "Efecto en la utilidad (USD; negativo si la reduce)", "number",
          alias=("importe", "efecto", "monto", "valor", "efecto en resultados"), ejemplo="-18500.00"),
    campo("corregida", "¿Corregida por la entidad? (Sí/No)", requerido=False, alias=("corregida", "ajustada", "registrada"),
          ejemplo="No"),
    campo("periodo", "Período (Actual / Anterior)", requerido=False, alias=("periodo", "período", "año", "ejercicio"), ejemplo="Actual"),
]
_COMPONENTES = [
    campo("componente", "Componente", alias=("componente", "entidad", "subsidiaria", "sucursal", "unidad"), ejemplo="Subsidiaria Norte"),
    campo("activos", "Activos del componente (USD)", "number", alias=("activos", "activo total", "total activos"), ejemplo="850000.00"),
    campo("ingresos", "Ingresos del componente (USD)", "number", requerido=False, alias=("ingresos", "ventas"), ejemplo="1200000.00"),
    campo("auditor", "Auditor del componente", requerido=False, alias=("auditor", "firma", "auditor del componente"),
          ejemplo="Equipo del grupo"),
    campo("materialidad", "Materialidad de desempeño del componente (USD)", "number", requerido=False,
          alias=("materialidad", "materialidad del componente", "materialidad de desempeño"), ejemplo=""),
    campo("instrucciones", "¿Se enviaron instrucciones? (Sí/No)", requerido=False, alias=("instrucciones", "comunicacion", "comunicación"),
          ejemplo="Sí"),
]
CAMPOS = {"cuestionario_planificacion": _CUEST, "equipo_encargo": _EQUIPO, "diferencias_auditoria": _DIFS,
          "componentes_grupo": _COMPONENTES}

# --- parámetros del encargo (se agregan a la hoja 02) ---------------------------------------------------------------
PARAMETROS = {
    "estadosAnteriores": "", "rolGrupo": "", "materialidadAsignadaGrupo": "", "pctComponente": 50, "umbralComponente": 15,
    "aniosRotacionSocio": 7, "confianzaAlta": 95, "confianzaMedia": 90, "confianzaBaja": 80, "pctErrorEsperado": 10,
}
ETIQUETAS = {
    "estadosAnteriores": "Estados del año anterior (" + " / ".join(ESTADOS_ANTERIORES) + ")",
    "rolGrupo": "Auditoría de grupo: rol de la firma (" + " / ".join(ROLES_GRUPO) + ")",
    "materialidadAsignadaGrupo": "Auditor de un componente: materialidad de desempeño asignada por el equipo del grupo (USD)",
    "pctComponente": "Materialidad de desempeño de cada componente: % de la del grupo (política de la firma)",
    "umbralComponente": "Componente de trabajo: % de los activos o ingresos del grupo desde el cual se audita (política de la firma)",
    "aniosRotacionSocio": "Años máximos del socio en una entidad de interés público antes de rotar (IESBA — VERIFICAR)",
    "confianzaAlta": "Muestreo: confianza para riesgos altos o significativos (%)",
    "confianzaMedia": "Muestreo: confianza para riesgos medios (%)",
    "confianzaBaja": "Muestreo: confianza para riesgos bajos (%)",
    "pctErrorEsperado": "Muestreo: error esperado como % del error tolerable (política de la firma)",
}
SUSTENTO = {
    "estadosAnteriores": "NIA 510 párr. 6; NIA 710 párr. 13–14 (VERIFICAR)", "rolGrupo": "NIA 600 (Revisada)",
    "materialidadAsignadaGrupo": "NIA 600 (Revisada): instrucciones del equipo del grupo",
    "pctComponente": "NIA 600 (Revisada): inferior a la del grupo — política de la firma (VERIFICAR)",
    "umbralComponente": "NIA 600 (Revisada) — política de la firma (VERIFICAR)",
    "aniosRotacionSocio": "Código IESBA sección 540 (VERIFICAR)",
    "confianzaAlta": "NIA 530 — política de la firma", "confianzaMedia": "NIA 530 — política de la firma",
    "confianzaBaja": "NIA 530 — política de la firma", "pctErrorEsperado": "NIA 530 — política de la firma (VERIFICAR)",
}


def _opcion(v, opciones, etiqueta) -> str:
    k = norm(v)
    if not k:
        return ""
    x = next((o for o in opciones if norm(o) == k or norm(o).startswith(k)), None)
    if x is None:
        raise ValueError(f"{etiqueta}: use " + ", ".join(opciones) + ".")
    return x


def _num(p, k, minimo, maximo, vacio_ok=False):
    v = p.get(k)
    if vacio_ok and str(v if v is not None else "").strip() == "":
        return None
    x = a_num(v)
    if x is None or not minimo <= float(x) <= maximo:
        raise ValueError(f"{ETIQUETAS[k]}: use un valor de {minimo:g} a {maximo:g}.")
    return float(x)


def parametros(p: dict) -> dict:
    """Valida y normaliza los parámetros del encargo."""
    out = {"estadosAnteriores": _opcion(p.get("estadosAnteriores"), ESTADOS_ANTERIORES, ETIQUETAS["estadosAnteriores"]),
           "rolGrupo": _opcion(p.get("rolGrupo"), ROLES_GRUPO, ETIQUETAS["rolGrupo"]),
           "materialidadAsignadaGrupo": _num(p, "materialidadAsignadaGrupo", 0, 1e13, vacio_ok=True),
           "pctComponente": _num(p, "pctComponente", 0.01, 100), "umbralComponente": _num(p, "umbralComponente", 0.01, 100),
           "aniosRotacionSocio": _num(p, "aniosRotacionSocio", 1, 30),
           "confianzaAlta": _num(p, "confianzaAlta", 50, 99.9), "confianzaMedia": _num(p, "confianzaMedia", 50, 99.9),
           "confianzaBaja": _num(p, "confianzaBaja", 50, 99.9), "pctErrorEsperado": _num(p, "pctErrorEsperado", 0, 90)}
    return out


# --- lectura y validación -----------------------------------------------------------------------------------------

def _sino(v) -> str | None:
    k = norm(v)
    if not k:
        return ""
    if k in ("si", "s", "yes", "y", "x", "true", "1", "verdadero"):
        return SI
    if k in ("no", "n", "false", "0", "falso"):
        return NO
    if k in ("noaplica", "na", "nd"):
        return NO_APLICA
    return None


def _evaluacion(v) -> str | None:
    k = norm(v)
    if not k:
        return ""
    if k.startswith(("adecuad", "efectiv", "satisfact", "sindeficien")):
        return ADECUADO
    if k.startswith(("condeficien", "deficien", "inadecuad", "debil", "noefectiv")):
        return DEFICIENCIAS
    if k in ("noaplica", "na"):
        return NO_APLICA
    return None


def _rol(v) -> str:
    k = norm(v)
    for claves, rol in ((("socio", "partner"), "Socio"), (("revisor", "eqr", "calidad"), "Revisor de calidad"),
                        (("gerente", "encargad", "supervisor", "manager"), "Gerente"), (("senior", "semisenior"), "Senior"),
                        (("asistente", "junior", "auxiliar"), "Asistente"), (("experto", "especialista", "actuario"), "Experto")):
        if k.startswith(claves):
            return rol
    return "Otro"


def _tipo_dif(v) -> str | None:
    k = norm(v)
    if not k:
        return "Factual"
    return "Factual" if k.startswith("fact") else "De juicio" if "juicio" in k else \
        "Proyectada" if k.startswith(("proyect", "extrapol")) else None


def _periodo_dif(v) -> str | None:
    k = norm(v)
    if not k:
        return "Actual"
    return "Actual" if k.startswith(("actual", "corriente", "presente")) else \
        "Anterior" if k.startswith(("anterior", "previo", "pasado")) else None


def respuesta(q: dict, v):
    """Respuesta normalizada según el tipo de la pregunta; None si no es válida."""
    s = str(v if v is not None else "").strip()
    if q["tipo"] == "sino":
        return _sino(s)
    if q["tipo"] == "evaluacion":
        return _evaluacion(s)
    if q["tipo"] == "fecha":
        if not s:
            return ""
        f = a_fecha(s)
        return f.isoformat() if f else None
    if q["tipo"] == "numero":
        if not s:
            return ""
        x = a_num(s)
        return None if x is None else float(x)
    return s


def validar(tipo: str, filas: list, out: dict) -> None:
    """Errores propios de los anexos del encargo (se suman a los de ``validar_campos``)."""
    err = out["errors"]
    if tipo == "cuestionario_planificacion":
        vistos = {}
        for f in filas:
            c = str(f.get("codigo", "") or "").strip().upper()
            q = POR_CODIGO.get(c)
            if q is None:
                err.append({"row": f.get("_row"), "field": "codigo",
                            "message": f"Código de pregunta desconocido: {c or '(vacío)'} (use los del modelo, p. ej. ACE-01)."})
                continue
            if c in vistos:
                err.append({"row": f.get("_row"), "field": "codigo", "message": f"Pregunta repetida: {c} (también en la fila {vistos[c]})."})
            vistos.setdefault(c, f.get("_row"))
            if respuesta(q, f.get("respuesta")) is None:
                ayuda = {"sino": "Sí, No o No aplica", "evaluacion": "Adecuado, Con deficiencias o No aplica",
                         "fecha": "una fecha", "numero": "un número"}[q["tipo"]]
                err.append({"row": f.get("_row"), "field": "respuesta", "message": f"{c}: responda con {ayuda}."})
    elif tipo == "equipo_encargo":
        for f in filas:
            if _sino(f.get("independencia")) not in ("", SI, NO):
                err.append({"row": f.get("_row"), "field": "independencia", "message": "Independencia: responda Sí o No."})
    elif tipo == "diferencias_auditoria":
        vistos = {}
        for f in filas:
            ref_ = str(f.get("referencia", "") or "").strip()
            if ref_ and ref_ in vistos:
                err.append({"row": f.get("_row"), "field": "referencia", "message": f"Referencia repetida: {ref_}."})
            vistos.setdefault(ref_, f.get("_row"))
            if _tipo_dif(f.get("tipo")) is None:
                err.append({"row": f.get("_row"), "field": "tipo", "message": "Tipo: use " + ", ".join(TIPOS_DIF) + "."})
            if _sino(f.get("corregida")) not in ("", SI, NO):
                err.append({"row": f.get("_row"), "field": "corregida", "message": "¿Corregida?: responda Sí o No."})
            if _periodo_dif(f.get("periodo")) is None:
                err.append({"row": f.get("_row"), "field": "periodo", "message": "Período: use Actual o Anterior."})
    elif tipo == "componentes_grupo":
        for f in filas:
            if _sino(f.get("instrucciones")) not in ("", SI, NO, NO_APLICA):
                err.append({"row": f.get("_row"), "field": "instrucciones", "message": "Instrucciones: responda Sí o No."})


def analizar(datasets: dict, sino: dict, pe: dict) -> dict:
    """Lee los anexos del encargo. Las respuestas inválidas ya las rechaza ``validar``; aquí se ignoran."""
    resp = {}
    for f in datasets.get("cuestionario_planificacion") or []:
        c = str(f.get("codigo", "") or "").strip().upper()
        q = POR_CODIGO.get(c)
        if q is None or c in resp:
            continue
        r = respuesta(q, f.get("respuesta"))
        fch = a_fecha(f.get("fecha")) if str(f.get("fecha") or "").strip() else None
        resp[c] = {"respuesta": "" if r is None else r, "detalle": str(f.get("detalle", "") or "").strip(),
                   "fecha": fch.isoformat() if fch else "", "responsable": str(f.get("responsable", "") or "").strip()}
    estado = {q["codigo"]: estado_q(q, resp.get(q["codigo"], {}).get("respuesta", ""), sino) for q in CUESTIONARIO}
    equipo = []
    for f in datasets.get("equipo_encargo") or []:
        nombre = str(f.get("integrante", "") or "").strip()
        if not nombre:
            continue
        ind = _sino(f.get("independencia")) or ""
        ind = ind if ind in (SI, NO) else ""
        fch = a_fecha(f.get("fecha_confirmacion")) if str(f.get("fecha_confirmacion") or "").strip() else None
        an, hr = a_num(f.get("anios")), a_num(f.get("horas"))
        x = {"integrante": nombre, "rol": _rol(f.get("rol")), "independencia": ind, "fecha": fch.isoformat() if fch else "",
             "amenazas": str(f.get("amenazas", "") or "").strip(), "salvaguardas": str(f.get("salvaguardas", "") or "").strip(),
             "anios": None if an is None else float(an), "horas": None if hr is None else float(hr)}
        x["estado"] = estado_equipo(x, sino, pe)
        equipo.append(x)
    difs = []
    for f in datasets.get("diferencias_auditoria") or []:
        v = a_num(f.get("importe"))
        difs.append({"referencia": str(f.get("referencia", "") or "").strip(), "codigo": str(f.get("codigo", "") or "").strip(),
                     "descripcion": str(f.get("descripcion", "") or "").strip(), "tipo": _tipo_dif(f.get("tipo")) or "Factual",
                     "periodo": _periodo_dif(f.get("periodo")) or "Actual",
                     "corregida": SI if _sino(f.get("corregida")) == SI else NO, "importe": float(v or 0), "origen": "RQ-012"})
    comp = []
    for f in datasets.get("componentes_grupo") or []:
        nombre = str(f.get("componente", "") or "").strip()
        if not nombre:
            continue
        mat = a_num(f.get("materialidad")) if str(f.get("materialidad") or "").strip() else None
        ins = _sino(f.get("instrucciones")) or ""
        comp.append({"componente": nombre, "activos": float(a_num(f.get("activos")) or 0),
                     "ingresos": float(a_num(f.get("ingresos")) or 0), "auditor": str(f.get("auditor", "") or "").strip(),
                     "materialidad": None if mat is None else float(mat), "instrucciones": ins if ins in (SI, NO, NO_APLICA) else ""})
    alertas = [q for q in CUESTIONARIO if estado[q["codigo"]] == "Alerta"]
    return {"resp": resp, "estado": estado, "equipo": equipo, "difs": difs, "comp": comp, "alertas": alertas,
            "hayCuestionario": bool(resp), "hayEquipo": bool(equipo)}


def estado_q(q: dict, r, sino: dict) -> str:
    """Estado de la pregunta (espejo de la fórmula de la columna «Estado»)."""
    if q["aplica"] and sino.get(q["aplica"]) == NO:
        return NO_APLICA
    if r in ("", None):
        return "Pendiente"
    if q["tipo"] == "sino" and q["esperado"]:
        return NO_APLICA if r == NO_APLICA else "Conforme" if r == q["esperado"] else "Alerta"
    if q["tipo"] == "evaluacion":
        return "Alerta" if r == DEFICIENCIAS else NO_APLICA if r == NO_APLICA else "Conforme"
    return "Documentado"


def _f_estado(q: dict, e: str, par) -> str:
    if q["tipo"] == "sino" and q["esperado"]:
        core = (f'IF({e}="{PENDIENTE}","Pendiente",IF({e}="{NO_APLICA}","{NO_APLICA}",'
                f'IF({e}="{q["esperado"]}","Conforme","Alerta")))')
    elif q["tipo"] == "evaluacion":
        core = f'IF({e}="{PENDIENTE}","Pendiente",IF({e}="{DEFICIENCIAS}","Alerta",IF({e}="{NO_APLICA}","{NO_APLICA}","Conforme")))'
    else:
        core = f'IF({e}="{PENDIENTE}","Pendiente","Documentado")'
    return f'IF({par(q["aplica"])}="No","{NO_APLICA}",{core})' if q["aplica"] else core


ALERTA_INDEP = "Alerta · sin confirmación de independencia"
ALERTA_AMENAZA = "Alerta · amenaza sin salvaguarda"
ALERTA_ROTACION = "Alerta · rotación del socio (entidad de interés público)"


def estado_equipo(x: dict, sino: dict, pe: dict) -> str:
    if x["independencia"] == NO:
        return ALERTA_INDEP
    if x["amenazas"] and not x["salvaguardas"]:
        return ALERTA_AMENAZA
    if x["rol"] == "Socio" and sino.get("interesPublico") == SI and (x["anios"] or 0) >= pe["aniosRotacionSocio"]:
        return ALERTA_ROTACION
    return "Conforme" if x["independencia"] == SI else "Pendiente"


# --- riesgos que el cuestionario lleva a la hoja 13 -----------------------------------------------------------------

def riesgos(enc: dict, sin_herramienta: str) -> list[dict]:
    """Una fila por pregunta con alerta; su «¿Se presenta?» es fórmula al estado de la pregunta."""
    return [{"cod": "cuestionario", "q": q["codigo"], "origen": ORIGEN_CUESTIONARIO, "rubro": q["bloque"],
             "cond": f"{q['codigo']}: {q['pregunta']}", "valor": None, "presenta": "Sí", "riesgo": q["alerta"], "sev": q["sev"],
             "norma": q["nia"], "resp": q["resp"], "herr": sin_herramienta, "eeff": q["eeff"]} for q in enc["alertas"]]


def ref_estado(codigo: str) -> str:
    h, r = FILA_Q[codigo]
    return f"'{h}'!I{r}"


def ref_respuesta(codigo: str) -> str:
    h, r = FILA_Q[codigo]
    return f"'{h}'!E{r}"


# --- hojas 24, 26 y 27 (cuestionario) -------------------------------------------------------------------------------

def filas_cuestionario(hoja_: str, enc: dict, par) -> list:
    filas = []
    for q in (q for q in CUESTIONARIO if q["hoja"] == hoja_):
        r = FILA_Q[q["codigo"]][1]
        x = enc["resp"].get(q["codigo"], {})
        v = x.get("respuesta", "")
        celda = PENDIENTE if v in ("", None) else (n2(v) if q["tipo"] == "numero" else v)
        filas.append([q["bloque"], q["codigo"], q["pregunta"], q["norma"], celda, x.get("detalle", ""), x.get("fecha") or None,
                      x.get("responsable", ""), fx(_f_estado(q, f"E{r}", par), enc["estado"][q["codigo"]])])
    return filas


GUIA_CUESTIONARIO = ("Lo prepara el equipo de auditoría (RQ-010): una fila por pregunta con su código (ACE-01, CON-01…), la "
                     "respuesta (Sí/No, Adecuado/Con deficiencias, una fecha o un texto), el detalle o la evidencia, la fecha y el "
                     "responsable. Lo que no se documentó queda [PENDIENTE].")

# --- hoja 25 (equipo e independencia) -------------------------------------------------------------------------------
COLS_EQUIPO = [["Integrante", "t"], ["Rol", "t"], ["¿Confirmó su independencia?", "t"], ["Fecha de la confirmación", "d"],
               ["Amenazas identificadas", "t"], ["Salvaguardas aplicadas", "t"], ["Años en el encargo", "n"],
               ["Horas presupuestadas", "n"], ["Estado", "t"]]
TXT_TOTAL_HORAS = "Total de horas presupuestadas"


def filas_equipo(enc: dict, par) -> tuple[list, list]:
    filas, estilos = [], []
    for i, x in enumerate(enc["equipo"]):
        r = FILA0 + i
        f_ = (f'IF(C{r}="No","{ALERTA_INDEP}",IF(AND(E{r}<>"",F{r}=""),"{ALERTA_AMENAZA}",IF(AND(B{r}="Socio",'
              f'{par("interesPublico")}="Sí",N(G{r})>={par("aniosRotacionSocio")}),"{ALERTA_ROTACION}",'
              f'IF(C{r}="Sí","Conforme","Pendiente"))))')
        filas.append([x["integrante"], x["rol"], x["independencia"] or PENDIENTE, x["fecha"] or None, x["amenazas"],
                      x["salvaguardas"], n2(x["anios"]), n2(x["horas"]), fx(f_, x["estado"])])
        estilos.append(None)
    n = len(filas)
    tot = sum(x["horas"] or 0 for x in enc["equipo"])
    filas.append([TXT_TOTAL_HORAS, None, None, None, None, None, None,
                  fx(f"SUM(H{FILA0}:H{FILA0 + n - 1})" if n else "0", n2(tot)), None])
    estilos.append({"tipo": "total"})
    return filas, estilos


def rango_equipo(col: str, n: int) -> str:
    return f"'{H25}'!${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


# --- hoja 30 (diferencias, NIA 450) ---------------------------------------------------------------------------------
COLS_DIF = [["Referencia", "t"], ["Código", "t"], ["Descripción", "t"], ["Tipo", "t"], ["Período", "t"], ["¿Corregida?", "t"],
            ["Efecto en la utilidad", "n"], ["¿Supera el umbral trivial?", "t"], ["¿Se acumula?", "t"], ["Evaluación", "t"]]
TXT_DIF_ACTUAL = "Incorrecciones no corregidas del período"
TXT_DIF_ANTERIOR = "Efecto de las incorrecciones no corregidas del año anterior"
TXT_DIF_TOTAL = "Total acumulado"
TXT_DIF_DESEMP = "Materialidad de desempeño"
TXT_DIF_GLOBAL = "Materialidad global"
TXT_DIF_CONCL = "Conclusión (NIA 450 párr. 11)"
CONCL_SIN_MAT = "Pendiente: sin materialidad (NIA 320)"
CONCL_GLOBAL = "Revisar · supera la materialidad global: incorrección material (NIA 450 párr. 11)"
CONCL_DESEMP = "Revisar · supera la materialidad de desempeño: ampliar los procedimientos"
CONCL_OK = "Conforme · por debajo de la materialidad de desempeño"


def diferencias(enc: dict, informe: list) -> list[dict]:
    """Las del equipo (RQ-012); si no trae las del año anterior, las salvedades con importe del informe anterior (RQ-005)."""
    difs = list(enc["difs"])
    if not any(x["periodo"] == "Anterior" for x in difs):
        for j, x in enumerate(informe):
            if x["tipo"] == "Salvedad" and x["importe"] is not None:
                difs.append({"referencia": f"RQ-005 · {j + 1}", "codigo": "", "periodo": "Anterior", "corregida": NO,
                             "descripcion": f"{x['concepto']}: salvedad del informe anterior (confirmar si se corrigió)",
                             "tipo": "Factual", "importe": float(x["importe"]), "origen": "RQ-005"})
    return difs


def calcula_diferencias(difs: list, mt: dict) -> dict:
    triv, des, glo = mt["trivial"], mt["desempeno"], mt["global"]
    for x in difs:
        x["supera"] = SI if triv is None or abs(x["importe"]) >= triv else NO
        x["acumula"] = SI if x["corregida"] == NO and x["supera"] == SI else NO
    act = sum(x["importe"] for x in difs if x["periodo"] == "Actual" and x["acumula"] == SI)
    ant = sum(x["importe"] for x in difs if x["periodo"] == "Anterior" and x["acumula"] == SI)
    tot = act + ant
    concl = (CONCL_SIN_MAT if not glo else CONCL_GLOBAL if abs(tot) >= glo - 1e-9 else
             CONCL_DESEMP if abs(tot) >= des - 1e-9 else CONCL_OK)
    return {"actual": act, "anterior": ant, "total": tot, "conclusion": concl}


def filas_diferencias(difs: list, res: dict, mt: dict, refs: dict) -> tuple[list, list, dict]:
    filas, estilos = [], []
    trv = refs["TRIVIAL"]
    for i, x in enumerate(difs):
        r = FILA0 + i
        filas.append([x["referencia"], x["codigo"], x["descripcion"], x["tipo"], x["periodo"], x["corregida"], n2(x["importe"]),
                      fx(f'IF({trv}="","Sí",IF(ABS(G{r})>={trv},"Sí","No"))', x["supera"]),
                      fx(f'IF(AND(F{r}="No",H{r}="Sí"),"Sí","No")', x["acumula"]), None])
        estilos.append(None)
    n, a, b = len(difs), FILA0, FILA0 + len(difs) - 1
    fila = {}

    def suma(per):
        return f'SUMIFS(G{a}:G{b},E{a}:E{b},"{per}",I{a}:I{b},"Sí")' if n else "0"
    r1 = FILA0 + n
    fila["actual"], fila["anterior"], fila["total"], fila["desemp"], fila["global"], fila["concl"] = range(r1, r1 + 6)
    filas += [
        [TXT_DIF_ACTUAL, None, None, None, None, None, fx(suma("Actual"), n2(res["actual"])), None, None, None],
        [TXT_DIF_ANTERIOR, None, None, None, None, None, fx(suma("Anterior"), n2(res["anterior"])), None, None, None],
        [TXT_DIF_TOTAL, None, None, None, None, None, fx(f"G{fila['actual']}+G{fila['anterior']}", n2(res["total"])), None, None,
         None],
        [TXT_DIF_DESEMP, None, None, None, None, None, fx(f'IF({refs["DESEMP"]}="","",{refs["DESEMP"]})', n2(mt["desempeno"])),
         None, None, None],
        [TXT_DIF_GLOBAL, None, None, None, None, None, fx(f'IF({refs["GLOBAL"]}="","",{refs["GLOBAL"]})', n2(mt["global"])),
         None, None, None],
        [TXT_DIF_CONCL, None, None, None, None, None, None, None, None,
         fx(f'IF(G{fila["global"]}="","{CONCL_SIN_MAT}",IF(ABS(G{fila["total"]})>=G{fila["global"]},"{CONCL_GLOBAL}",'
            f'IF(ABS(G{fila["total"]})>=G{fila["desemp"]},"{CONCL_DESEMP}","{CONCL_OK}")))', res["conclusion"])],
    ]
    estilos += [{"tipo": "total"}] * 3 + [None, None, {"tipo": "control"}]
    return filas, estilos, fila


# --- hoja 29 (extensión y muestreo) ---------------------------------------------------------------------------------
COLS_MUESTREO = [["PT", "t"], ["Código", "t"], ["Cuenta", "t"], ["Nivel", "t"], ["Confianza (%)", "n"],
                 ["Población (saldo al corte)", "n"], ["Error tolerable", "n"], ["Error esperado", "n"],
                 ["Factor de confiabilidad", "n"], ["Factor de expansión", "n"], ["Tamaño de la muestra", "i"],
                 ["Intervalo de muestreo", "n"], ["Método", "t"]]
METODO_SIN_MAT = "Pendiente: sin materialidad (NIA 320)"
METODO_MENOR = "Sin muestra: saldo menor que el error tolerable"
METODO_REVISAR = "Revisar: el error esperado consume el tolerable"
METODO_MUS = "Unidad monetaria; mayores que el intervalo al 100 %"


def _alto(nivel: str) -> bool:
    return nivel in ("Alto", "Significativo") or str(nivel).startswith("Pendiente")


def _ef(conf: float) -> float:
    """Factor de expansión del error esperado (tabla del muestreo por unidad monetaria — VERIFICAR)."""
    return 1.9 if conf >= 99 else 1.6 if conf >= 95 else 1.5 if conf >= 90 else 1.4 if conf >= 85 else 1.3 if conf >= 80 else 1.2


def filas_muestreo(cuentas: list, mt: dict, pe: dict, refs: dict, par) -> tuple[list, dict]:
    """``cuentas`` = [{pt, codigo, cuenta, nivel, r28, r08, saldo}] (las que tienen su propio procedimiento en la hoja 19;
    el nivel es el más alto de la cuenta en la hoja 28)."""
    filas, tam = [], {}
    des = mt["desempeno"]
    for i, c in enumerate(cuentas):
        r = FILA0 + i
        nivel = c["nivel"]
        conf = pe["confianzaAlta"] if _alto(nivel) else pe["confianzaMedia"] if nivel == "Medio" else pe["confianzaBaja"]
        pob = abs(c["saldo"])
        rf = round(-math.log(1 - conf / 100), 4)
        ef = _ef(conf)
        te = des
        ee = None if te is None else te * pe["pctErrorEsperado"] / 100
        if te is None:
            n, metodo = "", METODO_SIN_MAT
        elif pob < te:
            n, metodo = 0, METODO_MENOR
        elif te - ee * ef <= 0:
            n, metodo = "", METODO_REVISAR
        else:
            n, metodo = math.ceil(round(pob * rf / (te - ee * ef), 6)), METODO_MUS
        inter = "" if n in ("", 0) else round(pob / n, 2)
        tam[c["codigo"]] = (r, n, metodo)
        filas.append([
            c["pt"], c["codigo"], c["cuenta"], fx(f"{refs['P28']}K{c['r28']}", nivel),
            fx(f'IF(OR(D{r}="Alto",D{r}="Significativo",LEFT(D{r},9)="Pendiente"),{par("confianzaAlta")},'
               f'IF(D{r}="Medio",{par("confianzaMedia")},{par("confianzaBaja")}))', conf),
            fx(f"ABS({refs['H8']}H{c['r08']})", n2(pob)),
            fx(f'IF({refs["DESEMP"]}="","",{refs["DESEMP"]})', n2(te)),
            fx(f'IF(G{r}="","",G{r}*{par("pctErrorEsperado")}/100)', n2(ee)),
            fx(f"ROUND(-LN(1-E{r}/100),4)", rf),
            fx(f"IF(E{r}>=99,1.9,IF(E{r}>=95,1.6,IF(E{r}>=90,1.5,IF(E{r}>=85,1.4,IF(E{r}>=80,1.3,1.2)))))", ef),
            fx(f'IF(G{r}="","",IF(F{r}<G{r},0,IF(G{r}-H{r}*J{r}<=0,"",ROUNDUP(ROUND(F{r}*I{r}/(G{r}-H{r}*J{r}),6),0))))', n),
            fx(f'IF(OR(K{r}="",K{r}=0),"",ROUND(F{r}/K{r},2))', inter),
            fx(f'IF(G{r}="","{METODO_SIN_MAT}",IF(F{r}<G{r},"{METODO_MENOR}",IF(K{r}="","{METODO_REVISAR}","{METODO_MUS}")))', metodo),
        ])
    return filas, tam


EXT_ALTO = "Pruebas de detalle con confianza alta; partidas clave y mayores que el intervalo al 100 %"
EXT_MEDIO = "Pruebas de detalle con confianza media (muestra por unidad monetaria)"
EXT_BAJO = "Analíticos sustantivos con un umbral igual a la materialidad de desempeño (NIA 520)"
EXT_ENCARGO = "Según el procedimiento (todo el encargo)"


def extension(r19: int, nivel: str, tam: tuple | None, refs: dict) -> dict:
    """Columna «Extensión» del programa: la muestra de la hoja 29 en las cuentas; por nivel en los riesgos."""
    if tam:
        r29, n, metodo = tam
        k, mm = f"{refs['P29']}K{r29}", f"{refs['P29']}M{r29}"
        v = (f"Muestra de {n} partidas por unidad monetaria (hoja 29)" if isinstance(n, int) and n > 0 else metodo)
        return fx(f'IF(AND(ISNUMBER({k}),N({k})>0),"Muestra de "&{k}&" partidas por unidad monetaria (hoja 29)",{mm})', v)
    d = f"D{r19}"
    v = (EXT_ENCARGO if nivel == "Todo encargo" else EXT_ALTO if _alto(nivel) else EXT_MEDIO if nivel == "Medio" else EXT_BAJO)
    return fx(f'IF({d}="Todo encargo","{EXT_ENCARGO}",IF(OR({d}="Alto",{d}="Significativo",LEFT({d},9)="Pendiente"),"{EXT_ALTO}",'
              f'IF({d}="Medio","{EXT_MEDIO}","{EXT_BAJO}")))', v)


# --- hoja 28 (afirmaciones) -----------------------------------------------------------------------------------------
AFIRMACIONES = [("Existencia u ocurrencia", ("existencia", "ocurrencia")), ("Integridad", ("integridad",)),
                ("Exactitud y valuación", ("exactitud", "valuacion", "valoracion", "condicion")), ("Corte", ("corte",)),
                ("Derechos y obligaciones", ("derecho", "obligacion")),
                ("Presentación y clasificación", ("presentacion", "clasificacion", "revelacion"))]
COLS_AFIRMACIONES = ([["Nivel de la valoración", "t"], ["Código", "t"], ["Cuenta o riesgo", "t"], ["Sección u origen", "t"]]
                     + [[a, "t"] for a, _ in AFIRMACIONES]
                     + [["Nivel más alto", "t"], ["Riesgos vinculados", "t"], ["¿Se probará el control?", "t"], ["Respuesta", "t"]])
RANGO = {"Significativo": 4, "Alto": 3, "Medio": 2, "Bajo": 1}
NIVEL_EEFF = "Estados financieros"
NIVEL_AFIRMACION = "Afirmación"
RESP_GLOBAL = "Respuesta global (NIA 330 párr. 5): escepticismo, personal con experiencia, supervisión e imprevisibilidad"
RESP_570 = "Evaluar la capacidad de continuar y los planes de la dirección (NIA 570)"
RESP_AFIRMACION = "Por afirmación en el programa (hoja 19)"


def menciona(texto: str, claves: tuple) -> bool:
    t = norm(texto)
    return t in ("todas", "todo", "") or any(k in t for k in claves)


def filas_afirmaciones(eeff: list, cuentas: list, refs: dict) -> list:
    """``eeff`` = [(j, riesgo)] a nivel de estados financieros; ``cuentas`` = [{codigo, cuenta, sec, r18, material, relevantes,
    vinc: [(tipo, fila, nivel, aseveraciones, codigo, probar)]}] (tipo «12» o «13»)."""
    filas = []
    for j, x in eeff:
        r13 = FILA0 + j
        v = x["sev"] if x["presenta"] == "Sí" else "No se presenta"
        filas.append([NIVEL_EEFF, x["codigo"], x["riesgo"], x["origen"], *(["Todas"] * len(AFIRMACIONES)),
                      fx(f'IF({refs["R13"]}F{r13}="Sí",{refs["R13"]}H{r13},"No se presenta")', v), x["codigo"], "",
                      RESP_570 if x["norma"] == "NIA 570" else RESP_GLOBAL])
    for c in cuentas:
        r = FILA0 + len(filas)
        mat_f = f'OR({refs["C18"]}F{c["r18"]}="Sí",{refs["C18"]}G{c["r18"]}="Sí")'
        celdas = []
        for nombre, claves in AFIRMACIONES:
            conds = {k: [] for k in RANGO}
            vals = []
            for tipo, fila, nivel, aser, _cod, _pr in c["vinc"]:
                if not menciona(aser, claves):
                    continue
                if nivel:
                    vals.append(nivel)
                if tipo == "12":
                    m_, j_ = f"{refs['R12']}M{fila}", f"{refs['R12']}J{fila}"
                    conds["Significativo"].append(f'{m_}="Sí"')
                    conds["Alto"].append(f'OR({j_}="Alto",{j_}="Pendiente de calificación")')
                    conds["Medio"].append(f'{j_}="Medio"')
                    conds["Bajo"].append(f'{j_}="Bajo"')
                else:
                    f_, h_ = f"{refs['R13']}F{fila}", f"{refs['R13']}H{fila}"
                    for k in RANGO:
                        conds[k].append(f'AND({f_}="Sí",{h_}="{k}")')
            relevante = nombre in c["relevantes"]
            if relevante:
                vals.append("Medio" if c["material"] else "Bajo")
            v = max(vals, key=lambda z: RANGO[z]) if vals else "—"
            fin = f'IF({mat_f},"Medio","Bajo")' if relevante else ('IF(OR(' + ",".join(conds["Bajo"]) + '),"Bajo","—")'
                                                                  if conds["Bajo"] else '"—"')
            f_ = fin
            for k in ("Medio", "Alto", "Significativo"):
                if conds[k]:
                    f_ = f'IF(OR({",".join(conds[k])}),"{k}",{f_})'
            celdas.append(fx(f_, v) if (conds["Bajo"] or relevante) else "—")
        niveles = [x["v"] if isinstance(x, dict) else x for x in celdas]
        alto = max((z for z in niveles if z in RANGO), key=lambda z: RANGO[z], default="—")
        rng = f"E{r}:J{r}"
        f_alto = (f'IF(COUNTIF({rng},"Significativo")>0,"Significativo",IF(COUNTIF({rng},"Alto")>0,"Alto",'
                  f'IF(COUNTIF({rng},"Medio")>0,"Medio",IF(COUNTIF({rng},"Bajo")>0,"Bajo","—"))))')
        carta = [fila for tipo, fila, *_r in c["vinc"] if tipo == "12"]
        probar = "Sí" if any(t == "12" and pr_ == "Sí" for t, _f, _n, _a, _c, pr_ in c["vinc"]) else "No"
        f_pr = (fx("IF(OR(" + ",".join(f'{refs["R12"]}N{f}="Sí"' for f in carta) + '),"Sí","No")', probar) if carta else "No")
        filas.append([NIVEL_AFIRMACION, c["codigo"], c["cuenta"], c["sec"], *celdas, fx(f_alto, alto),
                      " ".join(dict.fromkeys(cod for *_r, cod, _p in c["vinc"])), f_pr, RESP_AFIRMACION])
    return filas


# --- hoja 31 (grupo, NIA 600) ---------------------------------------------------------------------------------------
COLS_GRUPO = [["Componente o concepto", "t"], ["Activos", "n"], ["Ingresos", "n"], ["% de los activos del grupo", "p"],
              ["% de los ingresos del grupo", "p"], ["¿Componente de trabajo?", "t"], ["Auditor", "t"],
              ["Materialidad de desempeño", "n"], ["Estado", "t"], ["¿Se enviaron instrucciones?", "t"]]
NO_GRUPO = "No aplica: el encargo no es una auditoría de grupo (hoja 02)"
TXT_ASIGNADA = "Materialidad de desempeño asignada por el equipo del grupo"


def filas_grupo(enc: dict, sino: dict, pe: dict, mt: dict, tot: dict, refs: dict, par) -> tuple[list, list]:
    """Componentes (auditor del grupo) o la materialidad asignada (auditor de un componente)."""
    filas, estado = [], []
    if sino.get("auditoriaGrupo") != SI:
        return [[fx(f'IF({par("auditoriaGrupo")}="Sí","Auditoría de grupo: registre el rol y los componentes","{NO_GRUPO}")',
                    NO_GRUPO), None, None, None, None, None, None, None, "No aplica", None]], ["No aplica"]
    des = mt["desempeno"]
    if pe["rolGrupo"] == "Auditor de un componente":
        a = pe["materialidadAsignadaGrupo"]
        e = "Pendiente" if a is None or des is None else "Conforme" if des <= a + 1e-9 else "Revisar"
        f_ = (f'IF(OR({par("materialidadAsignadaGrupo")}="",{refs["DESEMP"]}=""),"Pendiente",'
              f'IF({refs["DESEMP"]}<={par("materialidadAsignadaGrupo")},"Conforme","Revisar"))')
        return [[TXT_ASIGNADA, None, None, None, None, None, None,
                 fx(f'IF({par("materialidadAsignadaGrupo")}="","",{par("materialidadAsignadaGrupo")})', n2(a)), fx(f_, e), None]], [e]
    ta, ve = tot["activos"], tot["ventas"]
    for i, c in enumerate(enc["comp"]):
        r = FILA0 + i
        pa = None if not ta else c["activos"] / ta
        pi = None if not ve else c["ingresos"] / ve
        trabajo = SI if (pa is not None and pa * 100 >= pe["umbralComponente"]) or (pi is not None and pi * 100 >= pe["umbralComponente"]) \
            else NO
        mat = c["materialidad"] if c["materialidad"] is not None else (None if des is None else des * pe["pctComponente"] / 100)
        est = "Pendiente" if mat is None or des is None else "Conforme" if mat < des - 1e-9 else "Revisar"
        f_mat = (n2(c["materialidad"]) if c["materialidad"] is not None else
                 fx(f'IF({refs["DESEMP"]}="","",{refs["DESEMP"]}*{par("pctComponente")}/100)', n2(mat)))
        filas.append([c["componente"], n2(c["activos"]), n2(c["ingresos"]),
                      fx(f'IF({refs["TA"]}=0,"",B{r}/{refs["TA"]})', pa), fx(f'IF({refs["VE"]}=0,"",C{r}/{refs["VE"]})', pi),
                      fx(f'IF(OR(N(D{r})*100>={par("umbralComponente")},N(E{r})*100>={par("umbralComponente")}),"Sí","No")', trabajo),
                      c["auditor"] or PENDIENTE, f_mat,
                      fx(f'IF(OR(H{r}="",{refs["DESEMP"]}=""),"Pendiente",IF(H{r}<{refs["DESEMP"]},"Conforme","Revisar"))', est),
                      c["instrucciones"] or PENDIENTE])
        estado.append(est)
    if not filas:
        filas.append([f"{PENDIENTE} componentes del grupo (RQ-013)", None, None, None, None, None, None, None, "Pendiente", None])
        estado.append("Pendiente")
    return filas, estado


# --- hoja 32 (comunicación con el gobierno y asuntos clave candidatos) ----------------------------------------------
COLS_COMUNICACION = [["Asunto", "t"], ["Contenido", "x"], ["Norma", "t"], ["Estado", "t"]]
RESPONSABILIDADES = ("El auditor se forma y expresa una opinión sobre los estados financieros preparados por la dirección bajo la "
                     "supervisión del gobierno; la auditoría no los exime de sus responsabilidades.")
NO_KAM = "No aplica: la entidad no es cotizada ni de interés público (NIA 701 párr. 5)"


def filas_comunicacion(enc: dict, sino: dict, sig: list, kam_ant: list, equipo_rev: list, refs: dict, par,
                       fechas: dict, n_equipo: int) -> list:
    """``sig`` = riesgos significativos [(hoja, fila, columna_texto, columna_flag, valor_flag, texto, codigo)];
    ``kam_ant`` = asuntos clave del informe anterior [(fila 14, concepto)]."""
    eip = sino.get("interesPublico") == SI

    def fecha(k, etq, norma):
        v = fechas.get(k)
        return [etq, fx(f'IF({par(k)}="","{PENDIENTE}",{par(k)})', v or PENDIENTE), norma,
                fx(f'IF({par(k)}="","Pendiente","Documentado")', "Documentado" if v else "Pendiente")]
    filas = [
        ["Responsabilidades del auditor", RESPONSABILIDADES, "NIA 260 (Revisada) párr. 14", "Documentado"],
        fecha("fechaPreliminar", "Alcance y momento · visita preliminar", "NIA 260 (Revisada) párr. 15"),
        fecha("fechaFinal", "Alcance y momento · visita final", "NIA 260 (Revisada) párr. 15"),
        fecha("fechaInforme", "Alcance y momento · entrega del informe", "NIA 260 (Revisada) párr. 15"),
        ["Materialidad global (si se decide comunicarla)", fx(f'IF({refs["GLOBAL"]}="","{PENDIENTE}",{refs["GLOBAL"]})',
                                                               n2(refs["mt_global"]) if refs["mt_global"] else PENDIENTE),
         "NIA 260 (Revisada) párr. A13 (VERIFICAR)",
         fx(f'IF({refs["GLOBAL"]}="","Pendiente","Documentado")', "Documentado" if refs["mt_global"] else "Pendiente")],
    ]
    for h_, fila, col_t, col_f, flag, texto, cod in sig:
        filas.append([f"Riesgo significativo · {cod}", fx(f"'{h_}'!{col_t}{fila}", texto), "NIA 260 (Revisada) párr. 15",
                      fx(f'IF(\'{h_}\'!{col_f}{fila}="{flag}","Comunicar","No aplica")', "Comunicar")])
    if not sig:
        filas.append(["Riesgos significativos", "Sin riesgos significativos identificados en las hojas 12 y 13",
                      "NIA 260 (Revisada) párr. 15", "Documentado"])
    ind_v = ("Declaración de independencia de la firma y del equipo (hoja 25)" if eip else
             "Solo si hay amenazas no resueltas (la entidad no es de interés público)")
    filas.append(["Independencia", fx(f'IF({par("interesPublico")}="Sí","Declaración de independencia de la firma y del equipo '
                                      f'(hoja 25)","Solo si hay amenazas no resueltas (la entidad no es de interés público)")', ind_v),
                  "NIA 260 (Revisada) párr. 17", "Documentado" if eip or n_equipo else "Pendiente"])
    for cod, etq in (("COM-01", "Fecha de la comunicación"), ("COM-02", "Medio y destinatarios")):
        v = enc["resp"].get(cod, {}).get("respuesta") or PENDIENTE
        filas.append([etq, fx(ref_respuesta(cod), v), POR_CODIGO[cod]["norma"], fx(ref_estado(cod), enc["estado"][cod])])
    rev_v = ", ".join(equipo_rev) if equipo_rev else PENDIENTE
    n_rev = f'COUNTIF({rango_equipo("B", n_equipo)},"Revisor de calidad")' if n_equipo else "0"
    filas.append(["Revisor de calidad del encargo (NIGC 2)", rev_v, "NIGC 2; NIA 220 (Revisada) párr. 36 (VERIFICAR)",
                  fx(f'IF({par("interesPublico")}="No","No aplica",IF({n_rev}>0,"Conforme","Revisar"))',
                     "No aplica" if not eip else "Conforme" if equipo_rev else "Revisar")])
    kam = [(f"Asunto clave candidato · {cod}", fx(f"'{h_}'!{col_t}{fila}", texto)) for h_, fila, col_t, _cf, _fl, texto, cod in sig]
    kam += [("Asunto clave candidato · informe anterior", fx(f"{refs['P14']}B{fila}", texto)) for fila, texto in kam_ant]
    for etq, cont in kam:
        filas.append([etq, cont, "NIA 701 párr. 9–10 (VERIFICAR)",
                      fx(f'IF({par("interesPublico")}="Sí","Candidato","No aplica")', "Candidato" if eip else "No aplica")])
    if not kam:
        filas.append(["Asuntos clave de auditoría", fx(f'IF({par("interesPublico")}="Sí","Sin candidatos: documentar por qué",'
                                                       f'"{NO_KAM}")', "Sin candidatos: documentar por qué" if eip else NO_KAM),
                      "NIA 701", "No aplica" if not eip else "Revisar"])
    return filas


# --- explicaciones («Cómo se calcula») ------------------------------------------------------------------------------
_EST_Q = ("«Pendiente» si falta la respuesta; «Alerta» si la respuesta no es la esperada (por ejemplo, «No» a una condición "
          "previa o «Con deficiencias» en un componente del control interno), y la alerta pasa a la hoja 13 como riesgo; "
          "«Conforme» o «Documentado» si está completa; «No aplica» si la pregunta no corresponde (encargo que no es inicial).")
EXPLICA = {
    H24: {"Estado": _EST_Q}, H26: {"Estado": _EST_Q}, H27: {"Estado": _EST_Q},
    H25: {"Estado": ("Alerta si el integrante no confirmó su independencia, si hay una amenaza sin salvaguarda o si el socio de una "
                     "entidad de interés público alcanzó los años de rotación de la hoja 02; «Pendiente» si falta la confirmación."),
          "Horas presupuestadas": "En la fila de total suma las horas presupuestadas de todo el equipo."},
    H28: {"Nivel más alto": ("El nivel más alto de las seis afirmaciones de la fila; en los riesgos a nivel de estados financieros, "
                             "la severidad de la hoja 13 si el riesgo se presenta."),
          "Existencia u ocurrencia": ("Nivel del riesgo en esa afirmación: el de los riesgos de las hojas 12 y 13 que la mencionan "
                                      "(Significativo, Alto, Medio o Bajo) y, si la afirmación es relevante para la sección, "
                                      "«Medio» cuando la cuenta es material y «Bajo» si no; «—» si no es relevante."),
          "Integridad": "Igual que la primera afirmación, para la integridad (en los pasivos, los pasivos no registrados).",
          "Exactitud y valuación": "Igual que la primera afirmación, para la exactitud y la valuación.",
          "Corte": "Igual que la primera afirmación, para el corte (sobre todo en ingresos, costos y gastos).",
          "Derechos y obligaciones": "Igual que la primera afirmación, para los derechos (activos) y las obligaciones (pasivos).",
          "Presentación y clasificación": "Igual que la primera afirmación, para la presentación, la clasificación y las revelaciones.",
          "¿Se probará el control?": "«Sí» si algún hallazgo de la carta vinculado a la cuenta marca que se probará su control (hoja 12)."},
    H29: {"Nivel": ("Trae el nivel más alto de la cuenta en la valoración por afirmación (hoja 28): si un riesgo significativo "
                    "o alto recae en la cuenta, la muestra se calcula con la confianza alta."),
          "Confianza (%)": "Según el nivel: alto, significativo o pendiente usa la confianza alta de la hoja 02; medio, la media; bajo, la baja.",
          "Población (saldo al corte)": "Saldo al corte de la cuenta en valor absoluto (hoja 08).",
          "Error tolerable": "Es la materialidad de desempeño de la hoja 11.",
          "Error esperado": "Error tolerable por el porcentaje de error esperado de la hoja 02.",
          "Factor de confiabilidad": "Factor de Poisson sin errores para la confianza: −ln(1 − confianza), con 4 decimales.",
          "Factor de expansión": "Factor de la tabla del muestreo por unidad monetaria según la confianza (política de la firma — VERIFICAR).",
          "Tamaño de la muestra": ("Población × factor de confiabilidad ÷ (error tolerable − error esperado × factor de expansión), "
                                   "redondeado hacia arriba; cero si el saldo es menor que el error tolerable."),
          "Intervalo de muestreo": "Población ÷ tamaño de la muestra: toda partida mayor que el intervalo se prueba al 100 %.",
          "Método": "Explica si hay muestra, si el saldo no la necesita o si el error esperado impide calcularla."},
    H30: {"¿Supera el umbral trivial?": "Compara el efecto de la diferencia con el umbral de errores claramente insignificantes (hoja 11).",
          "¿Se acumula?": "Se acumula la diferencia no corregida que supera el umbral trivial (NIA 450 párr. 5).",
          "Efecto en la utilidad": ("Abajo suma las diferencias que se acumulan del período y del año anterior, las totaliza y trae "
                                    "las materialidades de la hoja 11 para compararlas."),
          "Evaluación": ("Compara el total acumulado con la materialidad global y la de desempeño: supera la global, supera la de "
                         "desempeño o queda por debajo.")},
    H31: {"Componente o concepto": ("Si el encargo no es una auditoría de grupo (hoja 02) lo indica con «No aplica»; si lo es, "
                                    "lista los componentes de la RQ-013 o, como auditor de un componente, la materialidad asignada."),
          "% de los activos del grupo": "Activos del componente ÷ total del activo del grupo (hoja 09).",
          "% de los ingresos del grupo": "Ingresos del componente ÷ ventas netas del grupo (hoja 09).",
          "¿Componente de trabajo?": "«Sí» si sus activos o ingresos alcanzan el umbral de la hoja 02 (política de la firma).",
          "Materialidad de desempeño": ("La que registró el equipo para el componente o, si falta, la de desempeño del grupo por "
                                        "el porcentaje de la hoja 02; como auditor de un componente, la asignada por el grupo."),
          "Estado": "La materialidad del componente debe ser inferior a la de desempeño del grupo (NIA 600 Revisada)."},
    H32: {"Contenido": ("Trae las fechas de la hoja 02, la materialidad de la hoja 11, el texto de cada riesgo significativo de "
                        "las hojas 12 y 13, las respuestas del cuestionario (hoja 24) y los asuntos clave del informe anterior."),
          "Estado": ("«Comunicar» para cada riesgo significativo; «Candidato» para los asuntos clave si la entidad es de interés "
                     "público; el estado de la pregunta del cuestionario; «Revisar» si una entidad de interés público no tiene "
                     "revisor de calidad en la hoja 25.")},
}
