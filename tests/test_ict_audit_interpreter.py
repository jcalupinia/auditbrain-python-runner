"""Tests for backend.app.ict.audit.interpreter — LLM motor with mocks."""
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.ict.audit.interpreter import (
    _fallback_interpretation,
    extract_anexo_data,
    interpret_anexo,
)
from backend.app.ict.audit.schemas import AnexoInterpretation


def test_fallback_interpretation_returns_valid_model():
    fb = _fallback_interpretation("A2", "Conciliación de Ingresos")
    assert isinstance(fb, AnexoInterpretation)
    assert fb.anexo_codigo == "A2"
    assert fb.confianza_modelo == "baja"
    assert fb.requiere_revision_humana is True
    assert fb.findings == []
    assert "no disponible" in fb.resumen_ejecutivo.lower()


def test_extract_anexo_data_returns_dict():
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    a2 = wb.create_sheet("A2")
    a2["A1"] = "Concepto"
    a2["B1"] = "Valor"
    a2["A2"] = "Ventas locales gravadas"
    a2["B2"] = 4200000.00
    data = extract_anexo_data(wb, "A2")
    assert isinstance(data, dict)
    assert data["codigo"] == "A2"
    assert "rows" in data
    assert len(data["rows"]) >= 1


@pytest.mark.asyncio
async def test_interpret_anexo_with_mock_client_returns_validated_model():
    """When Anthropic returns valid JSON via tool_use, we should parse it."""
    fake_response = MagicMock()
    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.name = "save_interpretation"
    fake_block.input = {
        "anexo_codigo": "A2",
        "anexo_nombre": "Conciliación de Ingresos",
        "resumen_ejecutivo": "Test resumen.",
        "findings": [],
        "confianza_modelo": "alta",
        "requiere_revision_humana": False,
        "timestamp_analisis": "2026-06-04T20:50:00",
        "modelo_usado": "claude-sonnet-4-7-20260101",
        "tokens_consumidos": 1234,
    }
    fake_response.content = [fake_block]
    fake_response.usage = MagicMock(input_tokens=500, output_tokens=734)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_response)

    result = await interpret_anexo(
        anexo_codigo="A2",
        anexo_data={"codigo": "A2", "rows": []},
        contexto={"a1_metrics": {}, "catalogo": {}, "razon_social": "X",
                  "ruc": "1", "periodo": "2025"},
        anthropic_client=fake_client,
    )
    assert isinstance(result, AnexoInterpretation)
    assert result.anexo_codigo == "A2"
    assert result.confianza_modelo == "alta"


@pytest.mark.asyncio
async def test_interpret_anexo_returns_fallback_on_api_exception():
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=Exception("API down"))
    result = await interpret_anexo(
        anexo_codigo="A2",
        anexo_data={"codigo": "A2", "rows": []},
        contexto={"a1_metrics": {}, "catalogo": {}, "razon_social": "X",
                  "ruc": "1", "periodo": "2025"},
        anthropic_client=fake_client,
        max_retries=2,
    )
    assert isinstance(result, AnexoInterpretation)
    assert result.confianza_modelo == "baja"
    assert result.requiere_revision_humana is True
