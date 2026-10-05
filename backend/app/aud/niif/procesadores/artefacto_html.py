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
    prelim = str(p.get("tipoRevision") or e.get("mode") or "").strip().lower().startswith("prelim")
    hay_eri = bool(files.get("eri"))
    per = {
        "prior": str(e.get("periodoAnterior") or p.get("periodoAnterior") or "Cierre anterior"),
        "current": str(e.get("periodoCorte") or p.get("periodoCorte") or "Corte"),
        "eri": str(e.get("periodoEri") or p.get("periodoEri") or "Mismo corte anterior"),
    }
    # Meses transcurridos del ejercicio: con revisión preliminar y SIN estado de resultados al mismo
    # corte, el motor prorratea el ERI del año anterior (diciembre ÷ 12 × meses). En la final son 12.
    try:
        meses = int(float(p.get("mesesTranscurridos") or e.get("mesesTranscurridos") or (8 if prelim else 12)))
    except (TypeError, ValueError):
        meses = 8 if prelim else 12
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


# Pestañas válidas del artefacto (whitelist para el modo "sección única"; evita
# inyectar nada arbitrario en el HTML por el parámetro ``seccion``).
SECCIONES = ("dashboard", "perfil", "situacion", "resultados", "analitico",
             "ratios", "materia", "riesgos", "notas", "control", "programa")


def render(files: dict, engagement: dict, parametros: dict, datasets: dict | None = None,
           seccion: str | None = None) -> bytes:
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
    html = (tmpl
            .replace("__AUDITIA_TITLE__", _html.escape(titulo))
            .replace("__AUDITIA_CFG__", json.dumps(cfg, ensure_ascii=False))
            .replace("__AUDITIA_LANSEY__", lansey)
            .replace("__AUDITIA_SOLO__", json.dumps(solo)))
    return html.encode("utf-8")


def archivo_b64(contenido: bytes, nombre: str, sheet: str | None = None) -> dict:
    """Empaqueta un xlsx crudo para ``AUDITIA.files`` (base64 + nombre + hoja)."""
    d = {"b64": base64.b64encode(contenido or b"").decode("ascii"), "name": nombre or "balance.xlsx"}
    if sheet:
        d["sheet"] = sheet
    return d
