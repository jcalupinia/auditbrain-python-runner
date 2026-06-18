"""Tests for the service.generate_excel split into (bytes_sri, bytes_papel_trabajo).

These tests validate the REGLA "Separación SRI vs Papel de trabajo del auditor"
(CLAUDE.md): the Excel that gets uploaded to the SRI portal must NOT contain
internal audit sheets.
"""
from io import BytesIO

import openpyxl

from backend.app.ict.service import INTERNAL_SHEETS_FOR_SRI


def test_internal_sheets_constant_documents_separation_rule():
    """The constant INTERNAL_SHEETS_FOR_SRI is the explicit contract: every
    sheet name here is removed from the Excel before it is sent to the SRI.

    NOTA 2026-06-17: las hojas AUDITORÍA DE ANEXOS, ARTEFACTO A1 y
    ARTEFACTO AUDITORIA fueron eliminadas del flujo de generación. Ya no
    se crean, así que tampoco hace falta declararlas como "internas". Si
    se reactivan, agregarlas a INTERNAL_SHEETS_FOR_SRI y a este set.
    """
    expected = {
        "VERIFICACIÓN A1", "TRAZABILIDAD",
    }
    assert set(INTERNAL_SHEETS_FOR_SRI) == expected


def test_split_workbook_removes_internal_sheets_for_sri():
    """Build a workbook with internal sheets + business sheets, then apply
    the same load+remove+save approach used in generate_excel. Confirm the
    SRI output is missing internal sheets but keeps business sheets."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    # Business sheets that MUST stay in the SRI output
    for name in ["INDICE", "A1", "A2", "A3"]:
        wb.create_sheet(name)
    # Internal sheets that MUST be removed
    for name in INTERNAL_SHEETS_FOR_SRI:
        wb.create_sheet(name)

    # Serialize → reload → remove internal sheets → re-serialize
    buf_full = BytesIO()
    wb.save(buf_full)
    bytes_full = buf_full.getvalue()

    wb_sri = openpyxl.load_workbook(BytesIO(bytes_full))
    for sn in INTERNAL_SHEETS_FOR_SRI:
        if sn in wb_sri.sheetnames:
            del wb_sri[sn]
    buf_sri = BytesIO()
    wb_sri.save(buf_sri)
    bytes_sri = buf_sri.getvalue()

    wb_sri_reloaded = openpyxl.load_workbook(BytesIO(bytes_sri))
    sri_sheets = set(wb_sri_reloaded.sheetnames)

    # Internal sheets must be gone
    for forbidden in INTERNAL_SHEETS_FOR_SRI:
        assert forbidden not in sri_sheets, (
            f"Hoja interna '{forbidden}' aún presente en el Excel SRI"
        )

    # Business sheets must remain
    for required in ["INDICE", "A1", "A2", "A3"]:
        assert required in sri_sheets, (
            f"Hoja de negocio '{required}' fue eliminada por error"
        )


def test_generate_excel_signature_returns_tuple():
    """generate_excel's signature is documented to return tuple[bytes, bytes].

    We can't easily execute generate_excel here without a full DB+session
    fixture, but we can verify the return annotation is preserved."""
    import inspect
    from backend.app.ict.service import generate_excel
    sig = inspect.signature(generate_excel)
    ann = sig.return_annotation
    # Pydantic-style: tuple[bytes, bytes]
    annotation_str = str(ann).replace(" ", "")
    assert "tuple" in annotation_str.lower()
    assert "bytes" in annotation_str.lower()
