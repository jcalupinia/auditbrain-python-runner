# backend/app/aud/informe_cumplimiento_tributario/docx_assembler.py
"""Ensambla el informe Word rellenando la plantilla docxtpl de la firma."""

from __future__ import annotations

import io
from pathlib import Path

from docxtpl import DocxTemplate

from backend.app.aud.informe_cumplimiento_tributario.helpers import marco_phrase

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATES = {
    "audit_consulting": TEMPLATES_DIR / "opinion_audit_consulting.docx",
    "partner_auditing": TEMPLATES_DIR / "opinion_partner.docx",
}


def assemble(
    *,
    firma_auditora: str,
    razon_social: str,
    ejercicio: str,
    fecha_emision: str | None,
    fecha_declaracion_ir: str | None,
    fecha_carga_sri: str | None,
    marco_contable: str,
    bloque_otros_asuntos: str,
    bloque_parte_iii: str,
) -> bytes:
    tpl_path = TEMPLATES.get(firma_auditora)
    if not tpl_path or not tpl_path.exists():
        raise ValueError(f"Plantilla no encontrada para firma '{firma_auditora}'")

    doc = DocxTemplate(str(tpl_path))
    ctx = {
        "razon_social": razon_social,
        "ejercicio": str(ejercicio),
        "fecha_cierre": f"31 de diciembre de {ejercicio}",
        "fecha_cierre_mayus": f"31 DE DICIEMBRE DE {ejercicio}",
        "fecha_emision": fecha_emision or "",
        "fecha_declaracion_ir": fecha_declaracion_ir or "",
        "fecha_carga_sri": fecha_carga_sri or "",
        "marco_contable": marco_phrase(marco_contable),
        "bloque_otros_asuntos": bloque_otros_asuntos,
        "bloque_parte_iii": bloque_parte_iii,
    }
    doc.render(ctx)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
