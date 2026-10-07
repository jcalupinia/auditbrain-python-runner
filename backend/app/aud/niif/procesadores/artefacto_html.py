"""Render del papel de Planificación con el MOTOR DEL ARTEFACTO AuditBrain.

El artefacto `AuditBrain_Analisis_LANSEY_v19_OFFLINE` es una app HTML autónoma: su
propio JS dibuja las pestañas compuestas (situación, resultados, analítico,
índices, materialidad, riesgos, notas, control y programa) y hasta genera el Excel
del lado del cliente. Para que la herramienta de Planificación entregue un HTML
**idéntico** al artefacto se reutiliza ese motor en vez del renderer propio
(`libro.html`): se toma la plantilla del artefacto (sin datos de cliente) y se le
inyecta la configuración del encargo ``AUDITIA``.

Dos caminos (ambos verificados → 11/11 pestañas idénticas al artefacto):

1. **Crudo (producción, el preferido).** ``AUDITIA.files`` lleva los balances
   **xlsx tal cual los subió el cliente** en base64; el propio motor los parsea con
   su ``parseSheet``/``buildModel`` (respeta celdas vacías y capta los subtotales
   «Total …», igual que el artefacto). Fidelidad total, sin re-parsear del lado de
   la herramienta.
2. **Pre-parseado (respaldo/ejemplo).** Si falta el crudo de algún balance, se
   arma ``LANSEY = {dic2025, ago2026, ago2025}`` desde los datasets ya parseados.

La plantilla (`assets/artefacto_planificacion.tmpl.html`) se construyó a partir del
artefacto reemplazando la constante embebida ``LANSEY`` por el placeholder
``__AUDITIA_LANSEY__`` y la función ``loadLansey`` por una versión que lee
``AUDITIA``. El Excel/Word/PowerPoint/PDF siguen saliendo del motor propio de la
herramienta; esto cambia solo el HTML.

Verificación: `scripts/verificar_artefacto_identico.py`.
"""
from __future__ import annotations

import base64
import html as _html
import json
import os
import re

from backend.app.aud.niif.procesadores.base import num

_TMPL = os.path.join(os.path.dirname(__file__), "..", "assets", "artefacto_planificacion.tmpl.html")

# rol del artefacto  →  (período, dataset de la herramienta, clave de saldo)
_ROLES = (
    ("prior", "dic2025", "balance_anterior", "saldo_anterior"),      # cierre del año anterior (auditado)
    ("current", "ago2026", "balance_actual", "saldo_actual"),        # fecha de corte que se audita (principal)
    ("eri", "ago2025", "resultados_mismo_corte", "saldo_eri"),       # estado de resultados del año anterior al mismo corte
)


def _rows(dataset, key):
    """Filas ``[[código, nombre, saldo]]``; celda vacía → ``None`` (null), no 0.

    El motor del artefacto distingue null (usar subtotal o sumar hijas) de un 0
    explícito; convertir null a 0 rompería los totales de las cuentas superiores.
    """
    out = []
    for r in dataset or []:
        cod = str(r.get("codigo") or r.get("code") or "").strip()
        if not cod:
            continue
        nom = str(r.get("cuenta") or r.get("nombre") or r.get("name") or "").strip()
        bruto = r.get(key)
        if bruto in (None, ""):
            bruto = r.get("saldo", r.get("valor", r.get("value", None)))
        out.append([cod, nom, None if bruto in (None, "") else num(bruto, 0.0)])
    return out


def construir_lansey(datasets: dict) -> dict:
    """Respaldo: los datasets ya parseados en la forma ``{dic2025, ago2026, ago2025}``."""
    obj = {}
    for _rol, periodo, ds, key in _ROLES:
        obj[periodo] = {"rows": _rows((datasets or {}).get(ds), key), "totals": {}}
    return obj


def construir_config(files: dict, engagement: dict, parametros: dict) -> dict:
    """Configuración ``AUDITIA`` para `loadLansey` (empresa, modo, períodos, archivos)."""
    e = engagement or {}
    p = parametros or {}
    files = files or {}
    # «Preliminar» puede venir como tipoRevision, engagement.mode o el campo «Visita de
    # auditoría» de la ficha (engagement.visit). Antes no se miraba `visit`, así que una
    # visita preliminar se trataba como final (comparaba contra Diciembre del corte).
    prelim = str(p.get("tipoRevision") or e.get("mode") or e.get("visit") or "").strip().lower().startswith("prelim")
    hay_eri = bool(files.get("eri"))
    per = {
        "prior": str(e.get("periodoAnterior") or p.get("periodoAnterior") or "Cierre anterior"),
        "current": str(e.get("periodoCorte") or p.get("periodoCorte") or "Corte"),
        "eri": str(e.get("periodoEri") or p.get("periodoEri") or "Mismo corte anterior"),
    }
    # Meses transcurridos del ejercicio: con revisión preliminar y SIN estado de resultados al mismo
    # corte, el motor prorratea el ERI del año anterior (diciembre ÷ 12 × meses). En la final son 12.
    # El default en preliminar es el MES DEL CORTE (agosto → 8); en final, 12.
    mm = re.match(r"\d{4}-(\d{2})", str(e.get("cutoff") or p.get("cutoff") or ""))
    mes_corte = int(mm.group(1)) if mm else 0
    defecto_meses = (mes_corte or 8) if prelim else 12
    try:
        meses = int(float(p.get("mesesTranscurridos") or e.get("mesesTranscurridos") or defecto_meses))
    except (TypeError, ValueError):
        meses = defecto_meses
    meses = min(12, max(1, meses))
    return {
        "company": str(e.get("client") or p.get("cliente") or ""),
        "ruc": str(e.get("ruc") or p.get("ruc") or ""),
        "mode": "preliminar" if prelim else "final",
        "hasERI": hay_eri,
        "meses": meses,
        "periods": per,
        "files": files,
    }


# --- secciones CUALITATIVAS: datos reales del cliente en vez del ejemplo LANSEY ---
# El motor del artefacto recalcula las pestañas CON NÚMEROS desde las balanzas reales,
# pero el Perfil del encargo y la Matriz de riesgos venían HARDCODEADOS con el ejemplo
# LANSEY. Aquí se arman esas secciones desde las cédulas que ya calculó el procesador
# (hoja 14_Perfil, hoja 12_Riesgos_CCI) y se inyectan en ``AUDITIA`` (AUDITIA.perfil /
# AUDITIA.risks); la plantilla las usa si vienen y cae al ejemplo LANSEY si faltan.

def _v(cell):
    """Valor de una celda del run: ``{"f":…,"v":…}`` → ``v``; valor plano → tal cual."""
    return cell.get("v") if isinstance(cell, dict) else cell


def _hoja_rows(hojas, name) -> list:
    for h in hojas or []:
        if h.get("name") == name:
            return h.get("rows") or []
    return []


def _nivel(valor) -> str:
    """Nivel de riesgo al código del artefacto (clase CSS y texto): ALTO/MEDIO/BAJO/PEND."""
    s = str(valor or "").strip().lower()
    if s.startswith("alto"):
        return "ALTO"
    if s.startswith("medio"):
        return "MEDIO"
    if s.startswith("bajo"):
        return "BAJO"
    return "PEND"  # «Pendiente de calificación» u otro


def _risks_de(hojas) -> list:
    """Matriz de riesgos del artefacto desde la hoja 12_Riesgos_CCI del procesador.
    Columnas: 0 id · 1 área · 2 descripción · 3 afirmaciones · 4 P · 5 I · 6 C ·
    7 inherente · 8 residual · 9 nivel · 10 respuesta."""
    out = []
    for r in _hoja_rows(hojas, "12_Riesgos_CCI"):
        if not r:
            continue
        rid = str(_v(r[0]) or "").strip()
        if not re.match(r"^R\d", rid):      # salta títulos / filas sin id de riesgo
            continue

        def g(i):
            return _v(r[i]) if i < len(r) else None

        out.append({
            "id": rid,
            "proc": str(g(1) or ""),        # área / proceso (línea en negrita)
            "desc": str(g(2) or ""),
            "aser": str(g(3) or ""),
            "p": num(g(4), 0.0), "i": num(g(5), 0.0), "c": num(g(6), 0.0),
            "inh": num(g(7), 0.0), "res": num(g(8), 0.0),
            "cls": _nivel(g(9)),
            "resp": str(g(10) or ""),
        })
    return out


def _entendimiento_de(hojas) -> list:
    """Entendimiento de la entidad y su entorno DERIVADO de los documentos cargados (hoja 35_Entendimiento,
    NIA 315): sector y actividad, propiedad y gobierno, capital, índices, políticas/marco, financiamiento y
    hallazgos de control. Columnas de la hoja: 0 Aspecto · 2 «Dato de los documentos». Devuelve
    ``[[aspecto, dato], ...]`` solo con los aspectos que tienen dato real (los [PENDIENTE] y los vacíos se omiten)."""
    out = []
    for r in _hoja_rows(hojas, "35_Entendimiento"):
        if not r:
            continue
        asp = str(_v(r[0]) or "").strip()
        dato = str(_v(r[2]) or "").strip() if len(r) > 2 else ""
        if not asp or asp.lower() == "aspecto":          # encabezado o fila vacía
            continue
        if not dato or dato.startswith("[PENDIENTE]") or dato.lower().startswith("pendiente"):
            continue
        out.append([asp, dato])
    return out


def _perfil_de(hojas) -> dict | None:
    """Perfil del encargo del artefacto desde la hoja 14_Perfil del procesador.
    Columnas: 0 tipo · 1 concepto · 2 detalle · 4 fuente. Tipos: Identificación,
    Entendimiento, Contexto. Devuelve ``{ident, obs, ctx}`` (como el artefacto).

    El bloque «Entendimiento de la entidad y su entorno» combina lo del informe del año anterior (hoja 14) con lo
    DERIVADO de los documentos cargados (hoja 35): así no queda [PENDIENTE] cuando el requerimiento trae datos."""
    ident, obs_b, ctx = [], [], []
    for r in _hoja_rows(hojas, "14_Perfil"):
        if not r:
            continue
        # Fila de título de sección: col0 string y el resto vacío → se omite.
        if isinstance(r[0], str) and all(x in (None, "") for x in r[1:]):
            continue
        tipo = str(_v(r[0]) or "").strip().lower()
        concepto = str(_v(r[1]) or "").strip() if len(r) > 1 else ""
        detalle = str(_v(r[2]) or "").strip() if len(r) > 2 else ""
        fuente = str(_v(r[4]) or "").strip() if len(r) > 4 else ""
        if tipo.startswith("identif"):
            ident.append([concepto, detalle, fuente])
        elif tipo.startswith("entend"):
            obs_b.append([concepto, detalle])
        elif tipo.startswith("context"):
            ctx.append([concepto, detalle])
    if not ident:
        return None
    # Descarta los renglones [PENDIENTE] del informe (hoja 14) y suma el entendimiento derivado de los documentos
    # (hoja 35): actividad del RUC/informe, capital del balance, índices, financiamiento y hallazgos de la carta.
    obs_b = [x for x in obs_b if x and not str(x[1] if len(x) > 1 else "").startswith("[PENDIENTE]")]
    obs_b += _entendimiento_de(hojas)
    obs = [{"t": "Entendimiento de la entidad y su entorno", "b": obs_b}] if obs_b else []
    return {"ident": ident, "obs": obs, "ctx": ctx}


def _prog_de(hojas) -> list:
    """Programa de auditoría del artefacto desde la hoja 19_Programa del procesador.
    El artefacto muestra 4 columnas [PT, área, riesgo, procedimiento]; de la hoja se toman
    las columnas 0 (PT), 1 (área), 2 (riesgo) y 4 (procedimiento sustantivo)."""
    out = []
    for r in _hoja_rows(hojas, "19_Programa"):
        if not r:
            continue
        pt = str(_v(r[0]) or "").strip()
        if not re.match(r"^PT", pt):     # salta títulos / filas sin PT
            continue

        def g(i):
            return _v(r[i]) if i < len(r) else None

        out.append([pt, str(g(1) or ""), str(g(2) or ""), str(g(4) or "")])
    return out


def construir_cualitativos(hojas, siempre: bool = False) -> dict:
    """Secciones cualitativas del cliente (perfil, matriz de riesgos, programa) para inyectar
    en AUDITIA, armadas desde las cédulas que ya calculó el procesador con lo que el auditor
    cargó en los requerimientos:
      - Perfil ← hoja 14_Perfil (informe del año anterior RQ-005, certificado de RUC RQ-008).
      - Matriz de riesgos ← hoja 12_Riesgos_CCI (carta de control interno).
      - Programa ← hoja 19_Programa (derivado de los riesgos y las cuentas a revisar).

    ``siempre=True`` (corrida real de un cliente): se usan SIEMPRE los datos de ese cliente,
    aunque una sección quede vacía porque aún no se cargó su requerimiento. Así NUNCA se
    muestra el ejemplo LANSEY en la planificación de una compañía real. ``siempre=False``
    (artefacto de demostración, sin corrida): solo se incluye lo que haya; lo que falte cae
    al ejemplo LANSEY de la plantilla."""
    risks = _risks_de(hojas)
    perfil = _perfil_de(hojas)
    prog = _prog_de(hojas)
    if siempre:
        return {
            "risks": risks,                                            # [] si falta la carta
            "perfil": perfil or {"ident": [], "obs": [], "ctx": []},   # vacío si falta el informe/RUC
            "prog": prog,                                              # [] si no hay programa aún
        }
    out = {}
    if risks:
        out["risks"] = risks
    if perfil:
        out["perfil"] = perfil
    if prog:
        out["prog"] = prog
    return out


# Pestañas válidas del artefacto (whitelist para el modo "sección única"; evita
# inyectar nada arbitrario en el HTML por el parámetro ``seccion``).
SECCIONES = ("dashboard", "perfil", "situacion", "resultados", "analitico",
             "ratios", "materia", "riesgos", "notas", "control", "programa")


def render(files: dict, engagement: dict, parametros: dict, datasets: dict | None = None,
           seccion: str | None = None, hojas: list | None = None) -> bytes:
    """HTML del papel con el motor del artefacto.

    ``files`` = ``{"prior":{"b64","name","sheet"?}|None, "current":{…}, "eri":{…}|None}``
    con los balances crudos en base64. Si falta el crudo de prior o current, se usa
    el respaldo pre-parseado desde ``datasets``.

    ``seccion`` (opcional): si es una de ``SECCIONES``, el HTML arranca en modo de
    una sola sección (oculta carga/navegación/otras secciones) para entregar un
    archivo autónomo por botón (Materialidad.html, Riesgos.html, …).
    """
    files = {k: v for k, v in (files or {}).items() if v and v.get("b64")}
    cfg = construir_config(files, engagement, parametros)
    # Secciones cualitativas del cliente (perfil, matriz de riesgos, programa) desde las
    # cédulas del procesador. En una corrida real (hay cédulas) SIEMPRE manda lo del cliente,
    # aunque una sección quede vacía por un requerimiento no cargado: así nunca se muestra el
    # ejemplo LANSEY en la planificación de una compañía real. Sin cédulas (artefacto de
    # demostración) se conserva el ejemplo LANSEY de la plantilla.
    if hojas is not None:
        cfg.update(construir_cualitativos(hojas, siempre=True))

    usa_crudo = bool(files.get("prior") and files.get("current"))
    if usa_crudo:
        lansey = "null"
    else:
        # Respaldo: datasets ya parseados; los nombres de archivo quedan como string.
        cfg["files"] = {rol: (files.get(rol, {}) or {}).get("name") or f"{rol}.xlsx"
                        for rol, *_ in _ROLES}
        cfg["hasERI"] = bool((datasets or {}).get("resultados_mismo_corte"))
        lansey = json.dumps(construir_lansey(datasets or {}), ensure_ascii=False)

    with open(_TMPL, encoding="utf-8") as fh:
        tmpl = fh.read()
    titulo = (cfg.get("company") or "Planificación").replace("<", "").replace(">", "")
    solo = seccion if seccion in SECCIONES else None
    # Override de las secciones cualitativas: reasigna los globales RISKS/PERFIL (que la
    # plantilla trae con el ejemplo LANSEY) por los datos reales inyectados en AUDITIA,
    # ANTES de que el motor dibuje las pestañas. Vacío si no hay datos reales (usa LANSEY).
    # Reasigna por PRESENCIA de la clave (no por longitud): en una corrida real una sección
    # vacía debe quedar vacía (lo del cliente), nunca volver al ejemplo LANSEY.
    partes = []
    if "risks" in cfg:
        partes.append("RISKS=A.risks;")
    if "perfil" in cfg:
        partes.append("PERFIL=A.perfil;")
    if "prog" in cfg:
        partes.append("PROG=A.prog;")
    override = ("try{var A=AUDITIA;if(A){" + "".join(partes) + "}}catch(e){}") if partes else ""
    html = (tmpl
            .replace("__AUDITIA_TITLE__", _html.escape(titulo))
            .replace("__AUDITIA_CFG__", json.dumps(cfg, ensure_ascii=False))
            .replace("__AUDITIA_LANSEY__", lansey)
            .replace("__AUDITIA_SOLO__", json.dumps(solo))
            .replace("__AUDITIA_OVERRIDE__", override))
    return html.encode("utf-8")


def archivo_b64(contenido: bytes, nombre: str, sheet: str | None = None) -> dict:
    """Empaqueta un xlsx crudo para ``AUDITIA.files`` (base64 + nombre + hoja)."""
    d = {"b64": base64.b64encode(contenido or b"").decode("ascii"), "name": nombre or "balance.xlsx"}
    if sheet:
        d["sheet"] = sheet
    return d
