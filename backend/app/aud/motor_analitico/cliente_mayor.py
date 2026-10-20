"""Cliente de lectura del mayor normalizado para el Motor Analítico.

Solo lectura, paginación acotada y sin cargar todo el mayor en memoria.
La API valida JWT y permisos de organización/expediente en cada página.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterator

import httpx


class ErrorIntegracionMayor(RuntimeError):
    pass


def iterar_movimientos(
    *, api_base: str, token_jwt: str, project_id: int,
    lote_id: int, periodo: str, pagina: int = 500,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> Iterator[dict]:
    """Itera movimientos sin duplicarlos y valida identidad del lote en cada página."""
    if not 1 <= pagina <= 2000 or project_id < 1 or lote_id < 1:
        raise ValueError("Proyecto, lote o tamaño de página inválidos")
    if not api_base.startswith("https://") and not (
        api_base.startswith("http://localhost") or api_base.startswith("http://127.0.0.1")
    ):
        raise ValueError("La API debe utilizar HTTPS fuera de localhost")
    if not token_jwt or not periodo:
        raise ValueError("JWT y período obligatorios")
    url = (api_base.rstrip("/") +
           f"/api/v1/ingesta/mayores/{project_id}/lotes/{lote_id}/movimientos")
    offset = 0
    expected_total = None
    expected_hash = None
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=timeout, follow_redirects=False)
    try:
        while True:
            response = client.get(
                url,
                headers={"Authorization": f"Bearer {token_jwt}"},
                params={"periodo": periodo, "offset": offset, "limit": pagina},
            )
            response.raise_for_status()
            data = response.json()
            if (data.get("project_id") != project_id or
                data.get("lote_id") != lote_id or
                data.get("periodo") != periodo or
                data.get("offset") != offset):
                raise ErrorIntegracionMayor("Identidad o paginación inconsistente")
            total = data["total_movimientos"]
            huella = data["source_sha256"]
            if expected_total is None:
                expected_total, expected_hash = total, huella
            elif total != expected_total or huella != expected_hash:
                raise ErrorIntegracionMayor("El lote cambió durante la lectura")
            movimientos = data["movimientos"]
            if not isinstance(movimientos, list) or len(movimientos) > pagina:
                raise ErrorIntegracionMayor("Página inválida")
            if offset + len(movimientos) > total:
                raise ErrorIntegracionMayor("El lote contiene más filas de las declaradas")
            for m in movimientos:
                # Mantener precisión contable: nunca usar float.
                m["debe"] = Decimal(m["debe"])
                m["haber"] = Decimal(m["haber"])
                yield m
            offset += len(movimientos)
            if offset == total:
                break
            if not movimientos:
                raise ErrorIntegracionMayor("Paginación incompleta")
    finally:
        if own_client:
            client.close()


def resumen_por_cuenta(**kwargs) -> dict[str, Decimal]:
    """Acumulados por cuenta calculados por streaming."""
    saldos: dict[str, Decimal] = {}
    for m in iterar_movimientos(**kwargs):
        codigo = m["codigo"]
        saldos[codigo] = saldos.get(codigo, Decimal("0")) + m["debe"] - m["haber"]
    return saldos
