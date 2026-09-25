"""Manifests de ejemplo de Audit Apps.

``AUD_INV_VNR`` es el manifest de la prueba de Valor Neto de Realización de
inventarios (benchmark §4.4), declarado como dict Python. El mismo contenido vive
en ``aud_inv_vnr.yaml`` para el catálogo/servidor (se carga con ``yaml.safe_load``
+ ``AuditAppManifest.from_dict`` cuando PyYAML esté disponible). El dict es la
copia canónica para pruebas: no depende de PyYAML.
"""

from __future__ import annotations

from .aud_cxc_cartera import AUD_CXC_CARTERA
from .aud_inv_vnr import AUD_INV_VNR

__all__ = ["AUD_INV_VNR", "AUD_CXC_CARTERA"]
