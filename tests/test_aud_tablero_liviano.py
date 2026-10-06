"""Tablero liviano (apertura rápida del HTML).

Decisión del dueño (2026-10-06): al ABRIR el tablero para verlo, el HTML NO incrusta
el Excel/Word/PowerPoint (que son lo pesado de generar) para que cargue rápido; cada
formato se descarga al momento desde la app (botones `data-remota` → `postMessage` a la
pestaña que lo abrió). La descarga del artefacto autónomo completo sí los incrusta.
"""
from backend.app.aud.niif import ejercicio_modelo as em
from backend.app.aud.niif.procesadores import PROCESADORES, libro


def _reg(pid):
    mod = PROCESADORES[pid]
    d = mod.definicion()
    ds, par, corte = em.escenario(mod)
    reg = em._reg(d, mod, ds, par, corte)
    return d, reg, reg["run"].get("exceptions", [])


def test_liviano_no_incrusta_office_y_trae_botones_remotos():
    d, reg, ev = _reg("efectivo_equivalentes")
    liviano = libro.html(d, reg, ev, 1, "APROBADO", incluir_adjuntos=False)
    completo = libro.html(d, reg, ev, 1, "APROBADO")
    # El liviano NO lleva ningún Office incrustado…
    assert b"data:application" not in liviano
    # …pero sí ofrece descargarlos (uno por formato: xlsx, docx, pptx, csv).
    for ext in (b'data-remota="xlsx"', b'data-remota="docx"', b'data-remota="pptx"', b'data-remota="csv"'):
        assert ext in liviano, ext
    # El completo (artefacto autónomo) sí los incrusta como enlaces data: base64.
    assert completo.count(b"data:application") == 4
    assert b"data-remota=" not in completo
    # El liviano pesa mucho menos (no carga los binarios Office).
    assert len(liviano) < len(completo) / 2


def test_liviano_sigue_siendo_html_valido_y_con_panel():
    d, reg, ev = _reg("efectivo_equivalentes")
    liviano = libro.html(d, reg, ev, 1, "APROBADO", incluir_adjuntos=False).decode("utf-8")
    assert liviano.lstrip().lower().startswith("<!doctype html")
    assert "</html>" in liviano
    assert "auditia-descargar-papel" in liviano   # el puente de descargas remotas está cableado


def test_pdf_no_cambia_sin_adjuntos_ni_botones_remotos():
    # El HTML para PDF (para_pdf=True) nunca incrusta Office ni muestra botones remotos.
    d, reg, ev = _reg("efectivo_equivalentes")
    pdf_html = libro.html(d, reg, ev, 1, "APROBADO", para_pdf=True)
    assert b"data:application" not in pdf_html
    assert b"data-remota=" not in pdf_html
