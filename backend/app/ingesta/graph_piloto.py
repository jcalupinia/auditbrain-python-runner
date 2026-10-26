"""Puente opt-in Microsoft Graph -> archivo temporal local para ingesta.

Nunca recibe URLs arbitrarias o tokens del navegador. Permite solo la pareja
drive/item configurada para un piloto por el administrador de Preview. Requiere
una aplicacion Entra ID autorizada por la organizacion; no usa OAuth de ChatGPT.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException


def _config():
    keys = ("MS_GRAPH_TENANT_ID", "MS_GRAPH_CLIENT_ID", "MS_GRAPH_CLIENT_SECRET",
            "INGESTA_SP_DRIVE_ID", "INGESTA_SP_ITEM_ID")
    values = {k: os.environ.get(k, "").strip() for k in keys}
    if not all(values.values()):
        raise HTTPException(503, "Conector SharePoint no configurado en este entorno")
    return values


async def descargar_mayor_piloto():
    """Devuelve Path temporal y metadata; caller elimina el archivo en finally."""
    env = _config()
    tenant = env["MS_GRAPH_TENANT_ID"]
    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        token_response = await client.post(
            "https://login.microsoftonline.com/" + tenant + "/oauth2/v2.0/token",
            data={"client_id": env["MS_GRAPH_CLIENT_ID"],
                  "client_secret": env["MS_GRAPH_CLIENT_SECRET"],
                  "scope": "https://graph.microsoft.com/.default",
                  "grant_type": "client_credentials"})
        if token_response.status_code != 200:
            raise HTTPException(503, "Microsoft Graph: autenticacion de aplicacion fallida")
        bearer = token_response.json().get("access_token")
        if not bearer:
            raise HTTPException(503, "Microsoft Graph: token no disponible")
        headers = {"Authorization": "Bearer " + bearer}
        # UUIDs de drive/item son configuracion del servidor, no input del usuario.
        drive = env["INGESTA_SP_DRIVE_ID"]
        item = env["INGESTA_SP_ITEM_ID"]
        url = f"https://graph.microsoft.com/v1.0/drives/{drive}/items/{item}"
        info = await client.get(url, headers=headers)
        if info.status_code != 200:
            raise HTTPException(502, "Microsoft Graph: documento no accesible")
        meta = info.json()
        if not meta.get("name", "").lower().endswith(".xlsx"):
            raise HTTPException(422, "El documento permitido no es un XLSX")
        if int(meta.get("size", 0)) > 100 * 1024 * 1024:
            raise HTTPException(413, "Documento de SharePoint supera 100 MB")
        ruta = None
        try:
            with tempfile.NamedTemporaryFile(prefix="graph_mayor_", suffix=".xlsx", delete=False) as tmp:
                ruta = Path(tmp.name)
                n = 0
                async with client.stream("GET", url + "/content", headers=headers) as response:
                    if response.status_code != 200:
                        raise HTTPException(502, "Microsoft Graph: descarga rechazada")
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        n += len(chunk)
                        if n > 100 * 1024 * 1024:
                            raise HTTPException(413, "Documento supera 100 MB")
                        tmp.write(chunk)
            if n == 0:
                raise HTTPException(422, "Archivo SharePoint vacio")
            return ruta, {"nombre": meta["name"], "item_id": item, "e_tag": meta.get("eTag")}
        except Exception:
            if ruta is not None:
                ruta.unlink(missing_ok=True)
            raise
