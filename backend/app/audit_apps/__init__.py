"""Audit Apps — pruebas de auditoría declaradas como dato, versionadas y ejecutables.

Paquete del Agente G (§1 capa 12 de ``ARQUITECTURA_CONVERGENCIA_v1.md``):

- ``manifest``  — el contrato ``AuditAppManifest`` (§2) + validación. Python puro.
- ``registry``  — catálogo versionado (AUT-002). Scaffold; persistencia en servidor.
- ``executor``  — corre inputs→steps→outputs contra el motor. Scaffold; motor en servidor.
- ``examples``  — manifest de ejemplo AUD-INV-VNR (benchmark §4.4) en dict y YAML.

Solo ``manifest`` (y ``examples``, que solo declara datos) se importan sin
dependencias de plataforma; ``registry`` y ``executor`` difieren sus imports.
"""

from __future__ import annotations

from .manifest import (
    AcceptanceTest,
    AuditAppManifest,
    InputSpec,
    ManifestValidationError,
    OutputSpec,
    ParameterSpec,
    StepSpec,
)

__all__ = [
    "AuditAppManifest",
    "InputSpec",
    "ParameterSpec",
    "StepSpec",
    "OutputSpec",
    "AcceptanceTest",
    "ManifestValidationError",
]
