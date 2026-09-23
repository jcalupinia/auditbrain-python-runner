"""Tokens e identidad visual EJECUTIVA (Dashboard SIGMANSERVICE) de los papeles
de trabajo NIIF. Fuente ÚNICA de colores, tipografías, formatos numéricos y
etiquetas en español, usada por todos los formatos de ``libro.py`` (Excel, Word,
PowerPoint, HTML). Si la identidad cambia, se cambia aquí y la heredan las 18
herramientas.

Sin dependencias de openpyxl a nivel de módulo: expone los tokens como datos y
unas fábricas de estilo que reciben las clases de openpyxl para no acoplar.
"""
from __future__ import annotations

# --- paleta (hex sin #) -------------------------------------------------------
DEEP_BLUE = "071B2F"   # fondo profundo
NAVY = "0A2342"        # azul marino base
GOLD = "C7A83C"        # dorado
LIME = "A6C63F"        # verde lima
TURQUOISE = "0D7377"   # turquesa
WHITE = "FFFFFF"
LIGHT = "F4F6F9"       # gris muy claro (paneles)
LINE = "B7C0CC"        # líneas
CELESTE = "DCE6F1"     # relleno de totales

# semáforo
RED = "C0392B"
AMBER = "D68910"
GREEN = "1E8449"

# --- tipografías (Excel sustituye por el fallback si no está instalada) -------
FONT_TITULO = "Montserrat"   # fallback de facto: Calibri / Segoe UI
FONT_TEXTO = "Calibri"
FONT_CIFRA = "Consolas"      # aproxima Roboto Mono para cifras monoespaciadas

# --- formatos numéricos (es-EC; Excel los muestra según la configuración local)
FMT = {"n": "#,##0.00", "p": "0.00%", "i": "#,##0", "a": "0", "d": "dd/mm/yyyy"}

# --- etiquetas en español -----------------------------------------------------
ESTADOS_ES = {
    "PRUEBA_SELECCIONADA": "Prueba seleccionada",
    "PROGRAMA_PROPUESTO": "Programa propuesto",
    "PROGRAMA_APROBADO": "Programa aprobado",
    "REQUERIMIENTO_GENERADO": "Requerimiento generado",
    "REQUERIMIENTO_APROBADO": "Requerimiento aprobado",
    "DOCUMENTACION_RECIBIDA": "Documentación recibida",
    "DOCUMENTACION_VALIDADA": "Documentación validada",
    "PRUEBA_CONFIGURADA": "Prueba configurada",
    "METODOLOGIA_APROBADA": "Metodología aprobada",
    "PRUEBA_EJECUTADA": "Prueba ejecutada",
    "RESULTADOS_ANALIZADOS": "Resultados analizados",
    "EN_REVISION": "En revisión",
    "APROBADO": "Aprobado",
}

ACCIONES_ES = {
    "create": "Prueba creada",
    "research": "Consulta de fuentes oficiales",
    "generate_program": "Programa generado",
    "save_program": "Programa guardado",
    "approve_program": "Base técnica confirmada",
    "generate_request": "Requerimiento generado",
    "save_request": "Requerimiento guardado",
    "approve_request": "Requerimiento aprobado",
    "upload": "Documento cargado",
    "reject_file": "Documento rechazado",
    "map_validate": "Mapeo y validación de anexos",
    "validate": "Documentación validada",
    "configure": "Parámetros configurados",
    "approve_methodology": "Metodología aprobada",
    "execute": "Prueba ejecutada",
    "analyze": "Resultados analizados",
    "submit": "Enviada a revisión",
    "approve": "Aprobada",
}

# color de chip por estado (semáforo por etapa)
_ESTADO_COLOR = {
    "PRUEBA_SELECCIONADA": TURQUOISE, "PROGRAMA_PROPUESTO": TURQUOISE, "PROGRAMA_APROBADO": TURQUOISE,
    "REQUERIMIENTO_GENERADO": AMBER, "REQUERIMIENTO_APROBADO": AMBER, "DOCUMENTACION_RECIBIDA": AMBER,
    "DOCUMENTACION_VALIDADA": AMBER, "PRUEBA_CONFIGURADA": GOLD, "METODOLOGIA_APROBADA": GOLD,
    "PRUEBA_EJECUTADA": LIME, "RESULTADOS_ANALIZADOS": LIME, "EN_REVISION": GOLD, "APROBADO": GREEN,
}


def estado_es(codigo: str) -> str:
    return ESTADOS_ES.get(codigo or "", codigo or "")


def accion_es(codigo: str) -> str:
    return ACCIONES_ES.get(codigo or "", (codigo or "").replace("_", " ").capitalize())


def color_estado(codigo: str) -> str:
    return _ESTADO_COLOR.get(codigo or "", NAVY)


def color_semaforo(n_problemas: int) -> str:
    """Color del semáforo por número de problemas encontrados."""
    if not n_problemas:
        return GREEN
    if n_problemas <= 3:
        return AMBER
    return RED


# --- fábricas de estilo openpyxl (se les pasan las clases para no acoplar) ----
def estilos(Font, PatternFill, Border, Side, Alignment) -> dict:
    """Diccionario de estilos reutilizables para el Excel ejecutivo."""
    fino = Side(style="thin", color=LINE)
    doble = Side(style="double", color=NAVY)
    return {
        "titulo": Font(name=FONT_TITULO, size=15, bold=True, color=NAVY),
        "subtitulo": Font(name=FONT_TITULO, size=10, bold=True, color=GOLD),
        "marca": Font(name=FONT_TITULO, size=16, bold=True, color=WHITE),
        "marca_sub": Font(name=FONT_TEXTO, size=9, color=WHITE),
        "encabezado": Font(name=FONT_TITULO, size=10, bold=True, color=WHITE),
        "dato": Font(name=FONT_TEXTO, size=9, color="1A1A1A"),
        "cifra": Font(name=FONT_CIFRA, size=9, color="1A1A1A"),
        "total": Font(name=FONT_CIFRA, size=10, bold=True, color=NAVY),
        "kpi_valor": Font(name=FONT_CIFRA, size=18, bold=True, color=NAVY),
        "kpi_etq": Font(name=FONT_TITULO, size=9, bold=True, color=TURQUOISE),
        "boton": Font(name=FONT_TITULO, size=10, bold=True, color=WHITE),
        "boton_nav": Font(name=FONT_TITULO, size=9, bold=True, color=NAVY),
        "nota": Font(name=FONT_TEXTO, size=8, italic=True, color="6B7280"),
        "fill_marca": PatternFill("solid", fgColor=NAVY),
        "fill_deep": PatternFill("solid", fgColor=DEEP_BLUE),
        "fill_encabezado": PatternFill("solid", fgColor=NAVY),
        "fill_total": PatternFill("solid", fgColor=CELESTE),
        "fill_panel": PatternFill("solid", fgColor=LIGHT),
        "fill_boton": PatternFill("solid", fgColor=TURQUOISE),
        "fill_boton_nav": PatternFill("solid", fgColor=CELESTE),
        "fill_gold": PatternFill("solid", fgColor=GOLD),
        "borde": Border(left=fino, right=fino, top=fino, bottom=fino),
        "borde_total": Border(left=fino, right=fino, top=doble, bottom=doble),
        "centro": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "izq": Alignment(horizontal="left", vertical="top", wrap_text=True),
        "der": Alignment(horizontal="right", vertical="center"),
    }
