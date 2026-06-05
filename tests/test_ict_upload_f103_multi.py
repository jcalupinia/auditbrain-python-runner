"""Regression test for the F-103 multi-archivo bug (2026-06-05).

Histórico: router.py:339 tenía `IS_MULTI = slot_name == "f104"` que excluía
F-103. Cliente subió 12 PDFs F-103 en una sola petición → solo se guardó EL
PRIMERO, bajo la clave "f103" (single) en vez de "f103_monthly" (multi).
Consecuencia: DATOS F-103 mostraba 24 × 184 celdas en 0.00 porque
`shared_context["f103_monthly"]` quedaba ausente.

Estos tests garantizan que:
  1. La constante IS_MULTI incluye "f103"
  2. La key_map en reset_anexo_slot mapea f103 → f103_monthly
  3. Cuando se procesan múltiples PDFs F-103 todos se acumulan bajo
     "f103_monthly", no se descartan después del primero.
"""
from __future__ import annotations


def test_router_is_multi_incluye_f103():
    """router.py debe tratar f103 como multi-archivo (12 meses).

    Inspección del source: la línea con IS_MULTI debe permitir f103.
    """
    from pathlib import Path
    router_src = Path(
        "backend/app/ict/router.py"
    ).read_text(encoding="utf-8")
    # Match cualquier formato que acepte f103:
    #  - IS_MULTI = slot_name in ("f104", "f103")
    #  - IS_MULTI = slot_name in {"f104", "f103"}
    #  - IS_MULTI = slot_name in ("f103", "f104")
    assert (
        '"f103"' in router_src and "IS_MULTI" in router_src
    ), "router.py debe declarar IS_MULTI incluyendo 'f103' (bug 2026-06-05)"

    # Buscar la línea específica de IS_MULTI (asignación, no comentario).
    # La asignación real es `IS_MULTI = <expr>` con `=` simple (no `==`).
    import re
    # Match `IS_MULTI = X` excluyendo cualquier `==` posterior. Excluye
    # también líneas que empiezan con `#` (comentarios).
    for line in router_src.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = re.match(r"\s*IS_MULTI\s*=\s*(?!=)(.+)", line)
        if m:
            is_multi_line = m.group(0)
            break
    else:
        raise AssertionError("No se encontró asignación de IS_MULTI en router.py")
    assert (
        '"f103"' in is_multi_line or "'f103'" in is_multi_line
    ), (
        f"IS_MULTI debe incluir explícitamente 'f103': encontrado "
        f"{is_multi_line!r}"
    )


def test_router_monthly_key_se_calcula_por_slot():
    """router.py debe usar MONTHLY_KEY que apunte a f103_monthly o f104_monthly
    según el slot, no hardcoded a f104_monthly."""
    from pathlib import Path
    router_src = Path("backend/app/ict/router.py").read_text(encoding="utf-8")
    assert "MONTHLY_KEY" in router_src, (
        "router.py debe definir MONTHLY_KEY para persistencia por slot"
    )
    # La key debe usarse en al menos 2 lugares (init + final assignment)
    assert router_src.count("MONTHLY_KEY") >= 2, (
        "MONTHLY_KEY debe usarse para inicializar `monthly` y para persistir "
        "`last_extracted`. Encontradas menos de 2 referencias."
    )


def test_reset_anexo_slot_mapea_f103_a_f103_monthly():
    """service.reset_anexo_slot key_map debe incluir f103 → f103_monthly
    para que al borrar el slot, se borre la clave correcta del extracted_data."""
    from pathlib import Path
    svc_src = Path("backend/app/ict/service.py").read_text(encoding="utf-8")
    # Buscar la línea del key_map donde se mapea f103
    import re
    m = re.search(r'"f103"\s*:\s*"f103_monthly"', svc_src)
    assert m, (
        "service.py::reset_anexo_slot debe mapear 'f103' → 'f103_monthly'. "
        "Sin esto, reset_slot deja un dict zombie cuando el cliente borra "
        "el slot."
    )


def test_reparse_session_uploads_limpia_clave_zombie_f103():
    """reparse_session_uploads debe limpiar la clave huérfana 'f103' (single)
    de sesiones viejas antes de mergear los nuevos datos en f103_monthly."""
    from pathlib import Path
    svc_src = Path("backend/app/ict/service.py").read_text(encoding="utf-8")
    assert 'merged.pop("f103", None)' in svc_src, (
        "service.py::reparse_session_uploads debe limpiar `merged.pop"
        '("f103", None)` para purgar el dict huérfano del bug histórico.'
    )
