"""Modelos Pydantic de request para la API v1."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PythonRunRequest(BaseModel):
    script: str = Field(default="", description="Código Python a ejecutar.")
    inputs: Dict[str, Any] = Field(default_factory=dict)
    response_mode: Optional[str] = Field(default=None)


class DocumentGenerateRequest(BaseModel):
    result: Any = Field(default=None, description="Datos a documentar.")
    output_expectations: Dict[str, Any] = Field(default_factory=dict)
    execution_context: Dict[str, Any] = Field(default_factory=dict)
    document_service: Dict[str, Any] = Field(default_factory=dict)


class RouterExecuteRequest(BaseModel):
    target: str = Field(..., description="Módulo destino.")
    payload: Dict[str, Any] = Field(default_factory=dict)
