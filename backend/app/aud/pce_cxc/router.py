"""Endpoints de la matriz de pérdidas crediticias esperadas (AUD, staff).

Este es un papel de trabajo del auditor (no una pantalla del portal cliente):
todos los endpoints exigen ``require_staff`` (admin u operador).
"""
from __future__ import annotations

import io
import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.aud.pce_cxc import service
from backend.app.aud.pce_cxc.exporter import construir_excel
from backend.app.aud.pce_cxc.models import CorridaPCE, guardar_corrida
from backend.app.aud.pce_cxc.schemas import CorridaPCEOut
from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.db.session import get_db

router = APIRouter(prefix="/aud/pce-cxc", tags=["aud-pce-cxc"])

#: Límite por archivo, fijado con la medición de `scripts/bench_pce_cxc.py`
#: sobre un análisis de antigüedad real (132.946 filas). Lo que importa no es
#: leer un archivo sino los TRES de una petición, que el servicio mantiene en
#: memoria a la vez: la tabla de abajo se reproduce con `--tres` (ver el
#: docstring del script). Medido en el equipo de desarrollo, por petición completa:
#:
#:     7,2 MB c/u ( 60.000 filas)  ->  51,6 s  y 171 MB de pico
#:    10,8 MB c/u ( 90.000 filas)  ->  79,7 s  y 236 MB de pico
#:    16,0 MB c/u (132.941 filas)  -> 117,6 s  y 334 MB de pico
#:
#: El plan starter de Render tiene 512 MB para todo el proceso, así que el
#: techo de trabajo es 250 MB de pico: los 25 MB por archivo que había antes
#: dejaban pasar tres archivos de 133.000 filas y reventaban ese techo. 10 MB
#: es el escalón medido que sí entra: el de 10,8 MB ya quedó en 236 MB, y la
#: recta que forman las tres mediciones (unos 18 MB de memoria por cada MB de
#: archivo, más 38 MB de base) proyecta 222 MB para tres archivos de 10 MB, o
#: sea unos 28 MB de margen contra el techo. Quien suba este límite tiene que
#: rehacer la medición: cada MB de más se paga a unos 18 MB de memoria.
MAX_BYTES_POR_ARCHIVO = 10 * 1024 * 1024


def _mensaje_413(nombre_archivo: str | None) -> str:
    limite_mb = MAX_BYTES_POR_ARCHIVO // (1024 * 1024)
    return (
        f"{nombre_archivo}: supera el límite de {limite_mb} MB por archivo. "
        "Depure el análisis de antigüedad (por ejemplo, quite columnas u hojas que no "
        "aporten al cálculo) y vuelva a subirlo. Si aun depurado lo supera, el archivo "
        "excede lo que el servicio puede procesar en línea; divida el análisis por "
        "segmento o solicite el procesamiento por lotes."
    )


@router.post("/analizar")
async def analizar(archivos: list[UploadFile] = File(...),
                   parametros: str = Form("{}"),
                   db: Session = Depends(get_db),
                   user: User = Depends(require_staff)) -> dict:
    """Calcula la matriz ECL a partir de los tres cortes y guarda la corrida.

    ``archivos`` y las ``fechas`` de ``parametros`` viajan en el mismo orden
    posicional: índice 0 = cohorte más antigua (t-2), índice 2 = corte actual.
    Sin los tres cortes con sus tres fechas no hay una cohorte con ventana
    completa de 24 meses, así que no se calcula nada.
    """
    if len(archivos) != 3:
        raise HTTPException(
            400,
            "Se requieren los tres análisis de antigüedad de cartera (t-2, t-1 y el corte "
            "actual): suba los tres archivos para poder calcular la matriz.",
        )
    try:
        params = json.loads(parametros or "{}")
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"El campo 'parametros' no es JSON válido: {e}") from e

    fechas = params.get("fechas") or []
    if len(fechas) != 3:
        raise HTTPException(
            400,
            "Indique la fecha de corte de cada uno de los tres archivos: envíe 'fechas' como "
            "una lista de tres fechas (una por archivo, en el mismo orden).",
        )

    cortes = []
    for archivo, fecha in zip(archivos, fechas):
        # Primer filtro, sin leer ni un byte: Starlette ya conoce `archivo.size`
        # (lo va sumando mientras recibe el cuerpo multipart) antes de que el
        # handler se ejecute, así que consultarlo no cuesta I/O adicional.
        if archivo.size is not None and archivo.size > MAX_BYTES_POR_ARCHIVO:
            raise HTTPException(413, _mensaje_413(archivo.filename))
        # Segundo filtro, por si `archivo.size` no viniera informado: se lee
        # como máximo un byte de más que el límite, así que un archivo
        # desproporcionado nunca llega a materializarse entero en `contenido`
        # (en RAM) antes de compararlo contra el límite.
        contenido = await archivo.read(MAX_BYTES_POR_ARCHIVO + 1)
        if len(contenido) > MAX_BYTES_POR_ARCHIVO:
            raise HTTPException(413, _mensaje_413(archivo.filename))
        try:
            fecha_corte = date.fromisoformat(fecha)
        except ValueError as e:
            raise HTTPException(
                400,
                f"Fecha de corte inválida: '{fecha}'. Use el formato AAAA-MM-DD (p. ej. 2023-12-31)."
            ) from e
        cortes.append({"nombre": archivo.filename or "", "contenido": contenido,
                       "fecha": fecha_corte, "hoja": None, "mapeo": None})

    try:
        resultado = service.analizar(cortes, params)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    # Reutilizamos la fecha ya parseada del tercer corte (índice 2)
    fecha_corte_obj = cortes[2]["fecha"]
    corrida = guardar_corrida(db, project_id=params.get("project_id"), user_id=user.id,
                              entidad=str(params.get("entidad") or ""),
                              fecha_corte=fecha_corte_obj,
                              parametros=params, resultado=resultado)
    return {"corrida_id": corrida.id, **resultado}


@router.get("/corridas/{corrida_id}", response_model=CorridaPCEOut)
def obtener(corrida_id: int, db: Session = Depends(get_db),
            _user: User = Depends(require_staff)) -> dict:
    """Recupera una corrida guardada: reproduce el papel de trabajo sin recargar archivos."""
    corrida = db.get(CorridaPCE, corrida_id)
    if not corrida:
        raise HTTPException(404, "Corrida no encontrada")
    return {"corrida_id": corrida.id, "entidad": corrida.entidad,
            "fecha_corte": corrida.fecha_corte.isoformat() if corrida.fecha_corte else None,
            "parametros": corrida.parametros, "resultado": corrida.resultado,
            "created_at": corrida.created_at.isoformat()}


@router.get("/corridas/{corrida_id}/excel")
def excel(corrida_id: int, db: Session = Depends(get_db),
          _user: User = Depends(require_staff)) -> StreamingResponse:
    """Descarga el papel de trabajo de la corrida como libro Excel (trece hojas,
    fórmulas auditables). Reconstruye el libro a partir del resultado guardado,
    sin volver a cargar los archivos originales."""
    corrida = db.get(CorridaPCE, corrida_id)
    if not corrida:
        raise HTTPException(404, "Corrida no encontrada")
    binario = construir_excel(corrida.resultado, corrida.parametros)
    nombre = f"PT-PCE-CXC_{(corrida.entidad or 'entidad').replace(' ', '_')}_{corrida.fecha_corte}.xlsx"
    return StreamingResponse(
        io.BytesIO(binario),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
