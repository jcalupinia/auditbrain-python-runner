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
#:     7,2 MB c/u ( 60.000 filas)  ->  52,3 s  y 196 MB de pico
#:    10,8 MB c/u ( 90.000 filas)  -> 121,4 s  y 261 MB de pico
#:
#: El plan starter de Render tiene 512 MB para todo el proceso, así que el
#: techo de trabajo es 250 MB de pico: los 25 MB por archivo que había al
#: principio dejaban pasar tres archivos de 133.000 filas (unos 16 MB cada
#: uno), que con la recta de ABAJO -la medición VIGENTE, ya con el control del
#: corte intermedio y la detección de documentos repetidos- proyectan unos
#: 355 MB. (Los 334 MB que decía este comentario eran la medición ANTERIOR a
#: esa regresión, y quedaron aquí sin actualizar.) El límite bajó primero a
#: 10 MB, y **vuelve a bajar a 7 MB** porque
#: el control del corte intermedio y la detección de documentos con número
#: repetido cuestan unos 25 MB más por petición: el escalón de 10,8 MB, que
#: antes quedaba en 236 MB, ahora llega a 261 MB y se pasa del techo.
#:
#: 7 MB es el escalón medido que sí entra (el de 7,2 MB quedó en 196 MB, con
#: unos 54 MB de margen). La recta de las dos mediciones son unos 18 MB de
#: memoria por cada MB de archivo sobre una base de unos 66 MB, o sea que tres
#: archivos de 10 MB proyectan 246 MB: entrarían raspando, sin margen para el
#: resto del proceso, que en producción ya tiene pandas cargado.
#:
#: Quien mueva este límite, o agregue cualquier estructura por documento, tiene
#: que rehacer la medición con `scripts/bench_pce_cxc.py --tres`: cada MB de
#: más se paga a unos 18 MB de memoria.
MAX_BYTES_POR_ARCHIVO = 7 * 1024 * 1024


#: Los tres análisis de antigüedad (t-2, t-1 y el corte actual).
ARCHIVOS_REQUERIDOS = 3


def _limite_mb() -> int:
    return MAX_BYTES_POR_ARCHIVO // (1024 * 1024)


def _mensaje_limite() -> str:
    """Qué límite hay y qué hacer si el archivo lo supera.

    La pantalla lo pide a `/limites` y lo pinta ANTES de que el auditor
    intente subir nada: el límite lo fija `MAX_BYTES_POR_ARCHIVO` y duplicar la
    cifra a mano en el frontend garantiza que un día digan cosas distintas.
    """
    return (
        f"Máximo {_limite_mb()} MB por archivo ({ARCHIVOS_REQUERIDOS} archivos por corrida). "
        "Si el análisis de antigüedad lo supera, depúrelo (quite columnas u hojas que no "
        "aporten al cálculo) y vuelva a subirlo. Si aun depurado lo supera, el archivo excede "
        "lo que el servicio puede procesar en línea; divida el análisis por segmento o "
        "solicite el procesamiento por lotes."
    )


def _mensaje_413(nombre_archivo: str | None) -> str:
    return f"{nombre_archivo}: supera el límite por archivo. {_mensaje_limite()}"


@router.get("/limites")
def limites(user: User = Depends(require_staff)) -> dict:
    """Límites de carga que la pantalla tiene que anunciar antes de la subida.

    Se exponen desde aquí -no se reescriben en el frontend- para que la cifra
    que ve el auditor y la que aplica el servidor sean, por construcción, la
    misma.
    """
    return {"max_bytes_por_archivo": MAX_BYTES_POR_ARCHIVO,
            "max_mb_por_archivo": _limite_mb(),
            "archivos_requeridos": ARCHIVOS_REQUERIDOS,
            "mensaje_limite": _mensaje_limite()}


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
    if len(archivos) != ARCHIVOS_REQUERIDOS:
        raise HTTPException(
            400,
            "Se requieren los tres análisis de antigüedad de cartera (t-2, t-1 y el corte "
            "actual): suba los tres archivos para poder calcular la matriz.",
        )
    try:
        params = json.loads(parametros or "{}")
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"El campo 'parametros' no es JSON válido: {e}") from e

    # JSON válido no es lo mismo que la forma esperada: `"5"`, `5` o `[1,2]`
    # parsean sin error y el `params.get` siguiente levantaba `AttributeError`,
    # o sea un 500 por un dato de entrada. Es el hermano de la guarda que ya
    # tiene el exportador, en la ENTRADA.
    if not isinstance(params, dict):
        raise HTTPException(
            400,
            f"El campo 'parametros' debe ser un objeto JSON con los parámetros de la corrida "
            f"(por ejemplo, {{\"fechas\": [\"2023-12-31\", \"2024-12-31\", \"2025-12-31\"]}}); "
            f"llegó un {type(params).__name__}.",
        )

    fechas = params.get("fechas") or []
    if len(fechas) != 3:
        raise HTTPException(
            400,
            "Indique la fecha de corte de cada uno de los tres archivos: envíe 'fechas' como "
            "una lista de tres fechas (una por archivo, en el mismo orden).",
        )

    # El proyecto se valida ANTES de leer los archivos: guardar el `project_id`
    # del cuerpo sin comprobar que existe y que el usuario tiene acceso dejaba
    # una corrida colgada de un proyecto ajeno (y, de paso, evita gastar memoria
    # leyendo tres análisis de antigüedad para una petición que no procede).
    project_id = params.get("project_id")
    if project_id is not None:
        try:
            project_id = int(project_id)
        except (TypeError, ValueError):
            raise HTTPException(
                400,
                f"El campo 'project_id' debe ser el identificador numérico del proyecto; llegó "
                f"{project_id!r}. Seleccione el proyecto en la pantalla y vuelva a calcular.",
            ) from None
        try:
            service.asegurar_acceso_a_proyecto(db, user, project_id)
        except PermissionError as e:
            raise HTTPException(403, str(e)) from e

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
    corrida = guardar_corrida(db, project_id=project_id, user_id=user.id,
                              entidad=str(params.get("entidad") or ""),
                              fecha_corte=fecha_corte_obj,
                              parametros=params, resultado=resultado)
    return {"corrida_id": corrida.id, **resultado}


def _corrida_autorizada(db: Session, user: User, corrida_id: int) -> CorridaPCE:
    """Recupera la corrida o traduce el motivo a su código HTTP."""
    try:
        return service.obtener_corrida(db, user, corrida_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


@router.get("/corridas/{corrida_id}", response_model=CorridaPCEOut)
def obtener(corrida_id: int, db: Session = Depends(get_db),
            user: User = Depends(require_staff)) -> dict:
    """Recupera una corrida guardada: reproduce el papel de trabajo sin recargar archivos."""
    corrida = _corrida_autorizada(db, user, corrida_id)
    return {"corrida_id": corrida.id, "entidad": corrida.entidad,
            "fecha_corte": corrida.fecha_corte.isoformat() if corrida.fecha_corte else None,
            "parametros": corrida.parametros, "resultado": corrida.resultado,
            "created_at": corrida.created_at.isoformat()}


@router.get("/corridas/{corrida_id}/excel")
def excel(corrida_id: int, db: Session = Depends(get_db),
          user: User = Depends(require_staff)) -> StreamingResponse:
    """Descarga el papel de trabajo de la corrida como libro Excel (trece hojas,
    fórmulas auditables). Reconstruye el libro a partir del resultado guardado,
    sin volver a cargar los archivos originales."""
    corrida = _corrida_autorizada(db, user, corrida_id)
    binario = construir_excel(corrida.resultado, corrida.parametros)
    nombre = f"PT-PCE-CXC_{(corrida.entidad or 'entidad').replace(' ', '_')}_{corrida.fecha_corte}.xlsx"
    return StreamingResponse(
        io.BytesIO(binario),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
