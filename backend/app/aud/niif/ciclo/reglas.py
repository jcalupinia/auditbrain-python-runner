"""Reglas del ciclo de una prueba — puerto a Python de las del sitio AuditBrain.

El backend del portal es solo Python (Render), así que la autoridad del ciclo
vive aquí y no en el JavaScript del sitio. Cada regla dice de dónde sale:

- ``transicion``, ``crear_programa``: ``lib/tools/domain.mjs`` (transition,
  createProgram). Vigiladas por ``espejo.json``, que genera el propio
  JavaScript del sitio: ``tests/test_aud_ciclo_reglas.py`` exige el mismo
  resultado, caso por caso.
- ``fuentes_oficiales``, ``verificar_fuentes``: ``lib/tools/research.ts``
  (officialSources, checkSources). Ese archivo importa el Worker de Cloudflare
  y no se puede ejecutar fuera del sitio: se portan a mano y sus pruebas repiten
  los mensajes literales.
- ``validar_ficha_encargo``: ``lib/engagement-context.ts`` (parseEngagement).
- ``validar_programa``: la acción ``save_program`` de ``app/api/tools/route.ts``.

Diferencia deliberada con el sitio, decisión del dueño (2026-09-21): aprueban
admin y operadores. El portal llama siempre con ``rol="ADMIN"``; el parámetro se
conserva para que el espejo pueda probar también el rechazo por rol.
"""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from urllib.parse import urlparse

_AQUI = Path(__file__).resolve().parent

CATALOGO: dict = json.loads((_AQUI / "catalogo.json").read_text(encoding="utf-8"))

ESTADOS = (
    "PRUEBA_SELECCIONADA", "PROGRAMA_PROPUESTO", "PROGRAMA_APROBADO",
    "REQUERIMIENTO_GENERADO", "REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA",
    "DOCUMENTACION_VALIDADA", "PRUEBA_CONFIGURADA", "METODOLOGIA_APROBADA",
    "PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS", "EN_REVISION", "APROBADO",
)
PUEDEN_APROBAR = ("REVISOR", "GERENTE", "SOCIO", "ADMIN")

_MAPA = {
    "generate_program": ("PRUEBA_SELECCIONADA", "PROGRAMA_PROPUESTO"),
    "approve_program": ("PROGRAMA_PROPUESTO", "PROGRAMA_APROBADO"),
    "generate_request": ("PROGRAMA_APROBADO", "REQUERIMIENTO_GENERADO"),
    "approve_request": ("REQUERIMIENTO_GENERADO", "REQUERIMIENTO_APROBADO"),
    "validate": ("DOCUMENTACION_RECIBIDA", "DOCUMENTACION_VALIDADA"),
    "configure": ("DOCUMENTACION_VALIDADA", "PRUEBA_CONFIGURADA"),
    "approve_methodology": ("PRUEBA_CONFIGURADA", "METODOLOGIA_APROBADA"),
    "execute": ("METODOLOGIA_APROBADA", "PRUEBA_EJECUTADA"),
    "analyze": ("PRUEBA_EJECUTADA", "RESULTADOS_ANALIZADOS"),
    "submit": ("RESULTADOS_ANALIZADOS", "EN_REVISION"),
    "approve": ("EN_REVISION", "APROBADO"),
}


class ReglaIncumplida(ValueError):
    """Una regla del ciclo rechazó la acción. El mensaje es el del sitio."""


def _texto(v) -> str:
    return v if isinstance(v, str) else ""


def _ok(obj, clave) -> bool:
    return bool(isinstance(obj, dict) and obj.get(clave))


def transicion(t: dict, accion: str, rol: str = "ADMIN") -> str:
    """Estado siguiente, o ``ReglaIncumplida``. Puerto literal de ``transition``."""
    if t.get("state") == "APROBADO":
        raise ReglaIncumplida("La versión aprobada es inmutable. Cree una nueva versión.")
    if accion not in _MAPA or _MAPA[accion][0] != t.get("state"):
        raise ReglaIncumplida("Acción no disponible en el estado actual.")
    if accion.startswith("approve") and rol not in PUEDEN_APROBAR:
        raise ReglaIncumplida("Su rol no permite aprobar. Solicite revisión.")
    if accion == "approve_program" and (not t.get("program") or not t.get("sourcesVerified")):
        raise ReglaIncumplida("Verifique las fuentes y complete el programa antes de aprobar.")
    if accion == "validate" and (not _ok(t.get("validation"), "ok") or not _ok(t.get("reconciliation"), "resolved")):
        raise ReglaIncumplida("Resuelva validaciones y conciliación antes de aprobar información.")
    if accion == "execute" and (not _ok(t.get("validation"), "ok") or not _ok(t.get("reconciliation"), "resolved")):
        raise ReglaIncumplida("Los datos deben estar validados y conciliados.")
    if accion == "approve":
        notas = t.get("notes") or []
        if (
            not t.get("run")
            or not _texto(t.get("analysis")).strip()
            or not _texto(t.get("conclusion")).strip()
            or not t.get("conclusionReviewed")
            or not _ok(t.get("validation"), "ok")
            or not _ok(t.get("reconciliation"), "resolved")
            or any(n.get("status") != "RESUELTO" or not _texto(n.get("response")).strip() for n in notas)
        ):
            raise ReglaIncumplida(
                "Cierre bloqueado: revise conclusión, ejecución, conciliaciones y respuesta de todos los puntos."
            )
    return _MAPA[accion][1]


def crear_programa(d: dict, encargo: dict) -> list[dict]:
    """Programa propuesto. Puerto literal de ``createProgram``."""
    if encargo.get("framework") == "NIIF para las PYMES":
        fuente = d.get("source_pymes") or {
            "organization": "IFRS Foundation",
            "document": "NIIF para las PYMES — verificar edición aplicable y sección correspondiente",
            "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/",
            "type": "Norma contable",
            "date": "",
        }
    else:
        fuente = d.get("source")
    # Una ficha con programa propio (la que redacta el encargo NIIF) se usa tal cual.
    if isinstance(d.get("program"), list) and d["program"]:
        propios = []
        for x in d["program"]:
            p = {"code": x["code"], "objective": x["objective"], "risk": x["risk"], "assertion": x["assertion"],
                 "procedure": x["procedure"], "evidence": x["evidence"], "criterion": x["criterion"],
                 "reference": x["source"] if isinstance(x.get("source"), str) else ""}
            if fuente is not None:
                p["source"] = fuente
            p["state"] = "PROPUESTO"
            propios.append(p)
        return propios
    # Una definición del Diseñador no trae `description`: sin respaldo, el
    # procedimiento quedaba vacío y guardar el programa lo rechazaba.
    procedimiento_02 = d.get("description") or (
        f"Recalcular {d['name']} aplicando las reglas y parámetros declarados, partida por partida, "
        "y contrastar el resultado contra la evidencia del cliente."
    )
    filas = [
        ("01", "Integridad de población", "Población incompleta", "Integridad",
         "Conciliar la población con el saldo contable al corte.", "Auxiliar y mayor contable",
         "Diferencia dentro de tolerancia aprobada o aceptación documentada."),
        ("02", "Valorar las partidas", "Valoración incorrecta", "Valoración", procedimiento_02,
         "Detalle por partida y sustento de parámetros", "Aplicar las reglas y parámetros aprobados por partida."),
        ("03", "Evaluar evidencia y excepciones", "Supuestos sin sustento", "Exactitud",
         "Verificar documentos y supuestos, evaluar excepciones y posibles ajustes.",
         "Soportes de precios, tasas, estimaciones y saldos registrados",
         "Resolver excepciones y documentar conclusión."),
    ]
    programa = []
    for n, objetivo, riesgo, afirmacion, proc, evidencia, criterio in filas:
        p = {
            "code": f"{d['id'].upper()}-{n}", "objective": objetivo, "risk": riesgo, "assertion": afirmacion,
            "procedure": proc, "evidence": evidencia, "criterion": criterio, "state": "PROPUESTO",
        }
        # JSON.stringify omite `source` cuando es undefined: el espejo lo compara así.
        if fuente is not None:
            p["source"] = fuente
        programa.append(p)
    return programa


def fuentes_oficiales(d: dict, marco: str, pais: str, tributario: bool) -> list[dict]:
    """Fuentes propuestas por marco. Puerto de ``officialSources`` (research.ts)."""
    pymes = marco == "NIIF para las PYMES"
    fuente = d.get("source") or {}
    if pymes:
        url_niif = "https://www.ifrs.org/content/dam/ifrs/publications/html-standards/english/2025/issued/html-ifrs-for-smes.html"
    else:
        url_niif = (fuente.get("url") if d.get("id") in ("vnr", "pce") else "https://www.ifrs.org/issued-standards/") or "https://www.ifrs.org/issued-standards/"
    fuentes = [
        {"category": "NIIF", "organization": "IFRS Foundation",
         "document": "NIIF para las PYMES: edición y sección aplicables" if pymes else (fuente.get("document") or "Norma contable aplicable"),
         "url": url_niif, "section": "", "date": "", "verified": False, "procedures": []},
        {"category": "NIA", "organization": "IAASB",
         "document": "Handbook IAASB 2025 — seleccionar NIA y párrafos aplicables al ejercicio",
         "url": "https://www.iaasb.org/publications/2025-handbook-international-quality-management-auditing-review-other-assurance-and-related-services",
         "section": "", "date": "", "verified": False, "procedures": []},
    ]
    if tributario:
        ecuador = pais == "Ecuador"
        fuentes.append({
            "category": "TRIBUTARIA",
            "organization": "SRI" if ecuador else "Administración tributaria del país",
            "document": "Legislación tributaria aplicable al ejercicio: verifique ley, reglamento y reformas",
            "url": "https://www.sri.gob.ec/normativa-tributaria-legislacion-nacional" if ecuador else "",
            "section": "", "date": "", "verified": False, "procedures": []})
    return fuentes


def _https(url) -> bool:
    return isinstance(url, str) and url.startswith("https://")


def verificar_fuentes(t: dict) -> bool:
    """Puerto de ``checkSources`` (research.ts): mismos controles, mismos mensajes."""
    fuentes = t.get("sources") or []
    for s in fuentes:
        url = s.get("url")
        procs = s.get("procedures")
        if (
            s.get("category") not in ("NIIF", "NIA", "TRIBUTARIA")
            or not isinstance(url, str)
            or (url and not url.startswith("https://"))
            or not isinstance(procs, list)
            or not all(isinstance(p, str) for p in procs)
        ):
            raise ReglaIncumplida("Cada fuente debe indicar categoría, enlace HTTPS y procedimientos asociados.")
    requeridas = ["NIIF", "NIA"] + (["TRIBUTARIA"] if t.get("taxApplicable") else [])
    for cat in requeridas:
        if not any(
            s.get("category") == cat and s.get("verified") and _https(s.get("url"))
            and _texto(s.get("document")).strip() and _texto(s.get("section")).strip() and _texto(s.get("date")).strip()
            for s in fuentes
        ):
            raise ReglaIncumplida(f"Verifique documento, párrafo/artículo y vigencia de la fuente {cat}.")

    def permitida(cat, url):
        host = urlparse(url).hostname or ""
        if cat == "NIIF":
            return re.search(r"(^|\.)ifrs\.org$", host) is not None
        if cat == "NIA":
            return re.search(r"(^|\.)(iaasb|ifac)\.org$", host) is not None
        return True

    for s in fuentes:
        if s.get("verified") and not permitida(s.get("category"), s.get("url")):
            raise ReglaIncumplida("Para NIIF/NIA use fuentes oficiales IFRS Foundation o IAASB/IFAC.")
    validar_tratamiento_tributario(t)
    return True


def validar_tratamiento_tributario(t: dict) -> bool:
    """Gate del recuadro «Tratamiento tributario revisado»: exige texto y que no
    queden citas «VERIFICAR» sin resolver. No se confirma solo."""
    if not t.get("taxApplicable"):
        return True
    tax = _texto(t.get("taxScope")).strip()
    if not tax:
        raise ReglaIncumplida("Describa el tratamiento tributario revisado y su sustento.")
    if "VERIFICAR" in tax.upper():
        raise ReglaIncumplida("Resuelva las citas marcadas «VERIFICAR» del tratamiento tributario antes de confirmar: "
                              "confírmelas contra la fuente oficial o quítelas.")
    return True


_CAMPOS_PROGRAMA = ("code", "objective", "risk", "assertion", "procedure", "evidence", "criterion")


def validar_programa(programa, fuentes) -> None:
    """Controles de ``save_program`` (route.ts), con sus mensajes."""
    if not isinstance(programa, list) or not programa or len(programa) > 50 or not isinstance(fuentes, list) or len(fuentes) > 50:
        raise ReglaIncumplida("Complete programa y fuentes.")
    for p in programa:
        for k in _CAMPOS_PROGRAMA:
            v = p.get(k) if isinstance(p, dict) else None
            if not isinstance(v, str) or not v.strip() or len(v) > 6000:
                raise ReglaIncumplida("Complete cada procedimiento del programa.")
    if len({p["code"] for p in programa}) != len(programa):
        raise ReglaIncumplida("Códigos de procedimiento duplicados.")


def vincular_fuentes(t: dict) -> list[dict]:
    """Al aprobar: cada procedimiento con su fuente verificada (route.ts, approve_program)."""
    fuentes = t.get("sources") or []
    for p in t["program"]:
        if not any(s.get("verified") and p["code"] in (s.get("procedures") or []) for s in fuentes):
            raise ReglaIncumplida(f"Vincule una fuente verificada al procedimiento {p['code']}.")
    return [
        {**p, "source": next(s for s in fuentes if s.get("verified") and p["code"] in (s.get("procedures") or [])), "state": "APROBADO"}
        for p in t["program"]
    ]


# --- Ficha del encargo (lib/engagement-context.ts, parseEngagement) ---------

MARCOS = ("NIIF completas", "NIIF para las PYMES")
FIRMAS = ("Audit Consulting", "Partner")
VISITAS = ("Preliminar", "Final")
ALCANCES = ("all", "selected", "one")
MENSAJE_FICHA = "Complete cliente, responsables, firma, marco, país, moneda, visita, edición y fecha válidos."


def _largo(v, minimo, maximo) -> bool:
    return isinstance(v, str) and minimo <= len(v.strip()) <= maximo


def validar_ficha_encargo(f: dict, completa: bool = True) -> dict:
    """Normaliza y valida la ficha. ``completa`` = ``contextEditSchema`` del sitio
    (exige además país, moneda, visita y edición); si no, ``engagementFields``."""
    try:
        anio = int(str(f.get("year", "")).strip())
    except ValueError:
        raise ReglaIncumplida(MENSAJE_FICHA)
    corte = str(f.get("cutoff") or "")
    try:
        fecha_ok = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", corte)) and datetime.date.fromisoformat(corte).isoformat() == corte
    except ValueError:
        fecha_ok = False
    ok = (
        _largo(f.get("client"), 2, 200) and _largo(f.get("ruc"), 3, 40) and _largo(f.get("activity"), 2, 200)
        and 2000 <= anio <= 2100 and fecha_ok
        and _largo(f.get("preparer"), 2, 150) and _largo(f.get("reviewer"), 2, 150)
        and f.get("firm") in FIRMAS and f.get("framework") in MARCOS
    )
    opcionales_ok = (
        (f.get("country") in (None, "") or _largo(f.get("country"), 2, 80))
        and (f.get("currency") in (None, "") or bool(re.fullmatch(r"[A-Z]{3}", str(f.get("currency")).strip())))
        and (f.get("visit") in (None, "") or f.get("visit") in VISITAS)
        and (f.get("edition") in (None, "") or _largo(f.get("edition"), 2, 180))
        and (f.get("adoption") in (None, "") or (isinstance(f.get("adoption"), str) and len(f["adoption"].strip()) <= 1000))
        and (f.get("reuseScope") in (None, "") or f.get("reuseScope") in ALCANCES)
    )
    if completa:
        opcionales_ok = opcionales_ok and all(f.get(k) not in (None, "") for k in ("country", "currency", "visit", "edition"))
    if not ok or not opcionales_ok:
        raise ReglaIncumplida(MENSAJE_FICHA)
    if int(corte[:4]) != anio:
        raise ReglaIncumplida("La fecha de corte debe corresponder al ejercicio.")
    pais = (f.get("country") or "").strip()
    if pais == "Ecuador" and not re.fullmatch(r"\d{13}", str(f.get("ruc")).strip()):
        raise ReglaIncumplida("Para Ecuador, indique un RUC de 13 dígitos.")
    return {
        "client": f["client"].strip(), "ruc": str(f["ruc"]).strip(), "activity": f["activity"].strip(),
        "year": anio, "cutoff": corte, "preparer": f["preparer"].strip(), "reviewer": f["reviewer"].strip(),
        "firm": f["firm"], "framework": f["framework"], "country": pais,
        "currency": (f.get("currency") or "").strip(), "visit": f.get("visit") or "",
        "edition": (f.get("edition") or "").strip(), "adoption": (f.get("adoption") or "").strip(),
        "reuseScope": f.get("reuseScope") or "one", "deferredTax": f.get("deferredTax") is True,
    }
