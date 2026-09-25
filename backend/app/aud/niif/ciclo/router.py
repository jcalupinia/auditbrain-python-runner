"""Rutas HTTP del ciclo real de una prueba (E6).

Permisos: ``require_staff`` (admin y operadores), por decisión del dueño del
2026-09-21; además, el usuario tiene que poder acceder al proyecto, con la misma
regla que el resto del portal (``user_can_access_project``).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.niif import procesadores
from backend.app.aud.niif.ciclo import almacen, datos, modelo, servicio
from backend.app.aud.niif.ciclo.models import Prueba, PruebaArchivo
from backend.app.aud.niif.ciclo.reglas import ReglaIncumplida
from backend.app.aud.niif.models import NiifFicha
from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.context.service import get_project, user_can_access_project
from backend.app.db.session import get_db

router = APIRouter(prefix="/aud/ciclo", tags=["aud-ciclo"])


class NuevaPruebaIn(BaseModel):
    origen: str = Field(min_length=1, max_length=40)
    tributario: bool = False


class AccionIn(BaseModel):
    accion: str = Field(min_length=1, max_length=40)
    revision: int
    datos: dict = Field(default_factory=dict)


class DefinicionIn(BaseModel):
    definicion: dict
    filas: list[dict]
    # La fecha de corte de la corrida (`cutoff`), para los cálculos `days`.
    parametros: dict = Field(default_factory=dict)


def _proyecto(db: Session, user: User, project_id: int):
    p = get_project(db, project_id, user.organization_id) if user.organization_id else None
    if p is None or not user_can_access_project(db, user, p):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    if (p.module_code or "").upper() != "AUD":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Las pruebas NIIF se aplican a proyectos del módulo AUD.")
    return p


def _prueba(db: Session, user: User, prueba_id: int) -> Prueba:
    p = db.get(Prueba, prueba_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Prueba no encontrada.")
    _proyecto(db, user, p.project_id)
    return p


def _salida(p: Prueba) -> dict:
    return {
        "id": p.id, "project_id": p.project_id, "version": p.version, "estado": p.estado,
        "origen": p.origen, "definicion": p.definicion, "registro": p.registro,
        "revision": p.revision, "creada_por": p.creada_por,
        "creada_en": p.creada_en.isoformat() if p.creada_en else None,
        "actualizada_en": p.actualizada_en.isoformat() if p.actualizada_en else None,
    }


def _regla(fn):
    try:
        return fn()
    except ReglaIncumplida as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except servicio.Conflicto as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/proyectos/{project_id}/ficha")
def leer_ficha(project_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    _proyecto(db, user, project_id)
    return {"ficha": servicio.leer_ficha(db, project_id)}


@router.put("/proyectos/{project_id}/ficha")
def guardar_ficha(project_id: int, body: dict, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    _proyecto(db, user, project_id)
    return {"ficha": _regla(lambda: servicio.guardar_ficha(db, project_id, body, user.email))}


@router.get("/encargos")
def encargos(db: Session = Depends(get_db), user: User = Depends(require_staff)) -> list[dict]:
    """Encargos NIIF (proyectos AUD) que el usuario ve, sin depender del Workspace activo."""
    return servicio.listar_encargos(db, user)


@router.post("/encargos", status_code=status.HTTP_201_CREATED)
def crear_encargo(body: dict, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    return _regla(lambda: servicio.crear_encargo(db, user, body))


@router.get("/herramientas")
def herramientas(db: Session = Depends(get_db), user: User = Depends(require_staff)) -> list[dict]:
    return servicio.herramientas_disponibles(db)


@router.get("/proyectos/{project_id}/pruebas")
def listar(project_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> list[dict]:
    _proyecto(db, user, project_id)
    filas = db.execute(
        select(Prueba).where(Prueba.project_id == project_id).order_by(Prueba.id.desc())
    ).scalars()
    return [
        {"id": p.id, "nombre": p.definicion.get("name"), "origen": p.origen, "estado": p.estado,
         "version": p.version, "revision": p.revision,
         "actualizada_en": p.actualizada_en.isoformat() if p.actualizada_en else None}
        for p in filas
    ]


@router.post("/proyectos/{project_id}/pruebas", status_code=status.HTTP_201_CREATED)
def crear(project_id: int, body: NuevaPruebaIn, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    _proyecto(db, user, project_id)
    return _salida(_regla(lambda: servicio.crear_prueba(db, project_id, body.origen, body.tributario, user.email)))


@router.get("/pruebas/{prueba_id}")
def leer(prueba_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    p = _prueba(db, user, prueba_id)
    todos = servicio.archivos(db, p.id)
    lista = [a for a in todos if a.clase == "source"]
    papeles = [a for a in todos if a.clase == "workpaper"]
    reqs = p.registro.get("requests") or []
    docs = [{"id": a.id, "requestId": a.requerimiento, "component": a.componente} for a in lista]
    rechazados = [a.id for a in lista if a.estado == "rechazado"]
    return {
        **_salida(p),
        "archivos": [
            {"id": a.id, "requerimiento": a.requerimiento, "componente": a.componente, "nombre": a.nombre,
             "tamano": a.tamano, "sha256": a.sha256, "estado": a.estado, "subido_por": a.subido_por,
             "subido_en": a.subido_en.isoformat() if a.subido_en else None}
            for a in lista
        ],
        "papeles": [{"id": a.id, "nombre": a.nombre, "sha256": a.sha256, "tamano": a.tamano,
                     "subido_por": a.subido_por, "subido_en": a.subido_en.isoformat() if a.subido_en else None}
                    for a in papeles],
        # Requerimientos que alimentan el cálculo: tienen modelo Excel (E10).
        "modelos": list(modelo.requerimientos_de_calculo(reqs, p.definicion)),
        # Versión siguiente, si existe: una aprobada solo origina una.
        "sucesora": db.execute(select(Prueba.id).where(Prueba.parent_id == p.id)).scalar(),
        # La cobertura la calcula el servidor con la regla del sitio: la pantalla solo la pinta.
        "cobertura": datos.tool_coverage(reqs, docs, rechazados) if reqs else [],
        "huecos": datos.tool_gaps(reqs, docs, rechazados) if reqs else [],
        "eventos": [
            {"accion": e.accion, "estado_anterior": e.estado_anterior, "estado_nuevo": e.estado_nuevo,
             "actor": e.actor, "comentario": e.comentario, "revision": e.revision,
             "fecha": e.creado_en.isoformat() if e.creado_en else None}
            for e in servicio.eventos(db, p.id)
        ],
    }


@router.post("/pruebas/{prueba_id}/acciones")
def accion(prueba_id: int, body: AccionIn, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    p = _prueba(db, user, prueba_id)
    # Acciones que no son un paso del circuito (route.ts las atiende antes).
    especiales = {
        "new_version": lambda: _salida(servicio.nueva_version(db, p, body.revision, user.email)),
        "erase": lambda: _salida(servicio.encerar(db, p, body.revision, body.datos, user.email)),
        "delete": lambda: servicio.eliminar(db, p, body.revision, body.datos),
        "edit_context": lambda: _salida(servicio.editar_contexto(db, p, body.revision, body.datos, user.email)),
    }
    if body.accion in especiales:
        return _regla(especiales[body.accion])
    return _salida(_regla(lambda: servicio.aplicar_accion(db, p, body.accion, body.revision, body.datos, user.email)))


@router.post("/pruebas/{prueba_id}/papel")
async def guardar_papel(
    prueba_id: int,
    revision: int = Form(...),
    xlsx: UploadFile = File(...),
    html: UploadFile = File(...),
    docx: UploadFile | None = File(None),
    pptx: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> dict:
    p = _prueba(db, user, prueba_id)
    a = await xlsx.read(almacen.MAX_ARCHIVO + 1)
    b = await html.read(almacen.MAX_ARCHIVO + 1)
    w = await docx.read(almacen.MAX_ARCHIVO + 1) if docx else None
    s = await pptx.read(almacen.MAX_ARCHIVO + 1) if pptx else None
    return _salida(_regla(lambda: servicio.guardar_papel(db, p, revision, a, b, user.email, docx=w, pptx=s)))


class PapelDeclarativoIn(BaseModel):
    # Lo que arma ``cargaPapel`` (frontend/src/aud/niif/papelDeclarativo.js).
    herramienta: dict
    cedulas: dict


class PapelDeclarativoGuardarIn(PapelDeclarativoIn):
    revision: int


_TIPOS_PAPEL = {"xlsx": almacen.TIPOS["xlsx"], "html": "text/html; charset=utf-8", "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


@router.post("/papel-declarativo")
def papel_declarativo(body: PapelDeclarativoIn, formato: str = "xlsx", user: User = Depends(require_staff)) -> Response:
    """Papel de una prueba declarativa (catálogo o ficha sin procesador) con el diseño de las
    pruebas con procesador: Excel con fórmulas (portada = panel del HTML), HTML autónomo, Word,
    PowerPoint o PDF. Sirve al papel en curso y al estudio de una ficha: no lee ni guarda nada."""
    from backend.app.aud.niif.procesadores import declarativo, libro

    if formato not in _TIPOS_PAPEL:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Formato no disponible.")
    try:
        contenido = declarativo.archivo(body.model_dump(), formato)
    except declarativo.CargaInvalida as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except libro.PDFNoDisponible as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return Response(contenido, media_type=_TIPOS_PAPEL[formato],
                    headers={"Content-Disposition": f'attachment; filename="Papel.{formato}"'})


@router.post("/pruebas/{prueba_id}/papel-declarativo")
def guardar_papel_declarativo(prueba_id: int, body: PapelDeclarativoGuardarIn, db: Session = Depends(get_db),
                              user: User = Depends(require_staff)) -> dict:
    """Guarda el papel aprobado de una prueba declarativa, armado por el servidor con el diseño nuevo."""
    p = _prueba(db, user, prueba_id)
    carga = {"herramienta": body.herramienta, "cedulas": body.cedulas}
    return _salida(_regla(lambda: servicio.guardar_papel_declarativo(db, p, body.revision, carga, user.email)))


@router.get("/bandejas")
def bandejas(db: Session = Depends(get_db), user: User = Depends(require_staff)) -> list[dict]:
    """Pruebas en revisión y aprobadas de los proyectos AUD que el usuario ve."""
    from backend.app.context.models import Client, Project

    if not user.organization_id:
        return []
    filas = db.execute(
        select(Prueba, Project, Client)
        .join(Project, Project.id == Prueba.project_id)
        .join(Client, Client.id == Project.client_id)
        .where(Project.organization_id == user.organization_id, Prueba.estado.in_(("EN_REVISION", "APROBADO")))
        .order_by(Prueba.actualizada_en.desc())
    ).all()
    return [
        {"id": p.id, "nombre": p.definicion.get("name"), "estado": p.estado, "version": p.version,
         "proyecto": pr.name, "project_id": pr.id, "cliente": c.name,
         "notas_abiertas": sum(1 for n in p.registro.get("notes") or [] if n.get("status") != "RESUELTO"),
         "aprobada_por": p.registro.get("approvedBy"),
         "actualizada_en": p.actualizada_en.isoformat() if p.actualizada_en else None}
        for p, pr, c in filas
        if (pr.module_code or "").upper() == "AUD" and user_can_access_project(db, user, pr)
    ]


@router.get("/procesadores")
def procesadores_disponibles(db: Session = Depends(get_db), user: User = Depends(require_staff)) -> list[dict]:
    """Procesadores especializados que se pueden instalar en una ficha, con el
    resultado de su ejemplo numérico de control (la prueba de que calcula)."""
    from backend.app.aud.niif.procesadores import PROCESADORES

    salida = []
    for k, m in PROCESADORES.items():
        if getattr(m, "RUBRO", None):
            continue  # herramientas del catálogo: se usan directo (proc:<id>), no se instalan en fichas
        d = m.definicion()
        ej = m.ejecutar(m.EJEMPLO["datasets"], m.EJEMPLO.get("parametros", {}), m.EJEMPLO["corte"])
        salida.append({"id": k, "nombre": d["name"], "rubro": d["area"], "marcos": d.get("frameworks") or [],
                       "resumen": d.get("summary", ""), "definicion": d,
                       "ejemplo": {"totales": ej["totals"], "etiquetas": ej["labels"],
                                   "resultado": {"etiqueta": ej["labels"][m.TOTAL_EJEMPLO], "valor": ej["totals"][m.TOTAL_EJEMPLO]},
                                   "tasas": [x for x in ej["detalle"]["tasas"] if x["tasa"] is not None]}})
    return salida


@router.put("/fichas/{ficha_id}/definicion")
def guardar_definicion(ficha_id: int, body: DefinicionIn, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    ficha = db.get(NiifFicha, ficha_id)
    if ficha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ficha no encontrada.")
    try:
        servicio.guardar_definicion_ficha(db, ficha, body.definicion, body.filas, body.parametros)
    except ReglaIncumplida as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (ValueError, KeyError, ArithmeticError, StopIteration) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e) or "La definición no se pudo ejecutar.")
    return {"id": ficha.id, "definicion_guardada": True}


@router.post("/pruebas/{prueba_id}/archivos", status_code=status.HTTP_201_CREATED)
async def subir(
    prueba_id: int,
    revision: int = Form(...),
    requerimiento: str = Form(...),
    componente: str = Form(""),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> dict:
    p = _prueba(db, user, prueba_id)
    contenido = await archivo.read(almacen.MAX_ARCHIVO + 1)
    a = _regla(lambda: servicio.subir_archivo(db, p, revision, requerimiento, componente, archivo.filename or "", contenido, user.email))
    return {"id": a.id, "sha256": a.sha256, "revision": p.revision}


@router.get("/pruebas/{prueba_id}/archivos/{archivo_id}")
def descargar(prueba_id: int, archivo_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> Response:
    p = _prueba(db, user, prueba_id)
    a = db.get(PruebaArchivo, archivo_id)
    if a is None or a.prueba_id != p.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado.")
    try:
        contenido = almacen.leer(a.ruta)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="El archivo ya no está en el almacenamiento.")
    nombre = a.nombre.encode("ascii", "replace").decode().replace('"', "_")
    return Response(contenido, media_type=a.tipo, headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/pruebas/{prueba_id}/modelo/{requerimiento}")
def descargar_modelo(prueba_id: int, requerimiento: str, db: Session = Depends(get_db),
                     user: User = Depends(require_staff)) -> Response:
    """Modelo Excel para que el cliente entregue la información en el formato
    que «Procesar» reconoce (E10)."""
    p = _prueba(db, user, prueba_id)
    reqs = p.registro.get("requests") or []
    campos = modelo.requerimientos_de_calculo(reqs, p.definicion).get(requerimiento)
    req = next((r for r in reqs if r["id"] == requerimiento), None)
    if req is None or campos is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Este requerimiento es de soporte: no alimenta el cálculo y no tiene modelo.")
    contenido = modelo.construir(p.definicion, req, campos, p.registro.get("engagement") or {})
    nombre = f"Modelo_{requerimiento}.xlsx".encode("ascii", "replace").decode()
    return Response(contenido, media_type=almacen.TIPOS["xlsx"], headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/pruebas/{prueba_id}/libro")
def descargar_libro(prueba_id: int, formato: str = "xlsx", db: Session = Depends(get_db),
                    user: User = Depends(require_staff)) -> Response:
    """Papel en curso de una prueba con procesador, armado por el servidor:
    Excel con fórmulas, Word, PowerPoint o HTML autónomo (funciona sin internet
    y trae dentro los demás formatos)."""
    from backend.app.aud.niif.procesadores import libro

    tipos = {"xlsx": (almacen.TIPOS["xlsx"], "xlsx", "xlsx"),
             "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx", "docx"),
             "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx", "pptx"),
             "pdf": ("application/pdf", "pdf", "pdf"),
             "csv": ("application/zip", "csv_zip", "zip"),   # un CSV por cédula en un ZIP
             "html": ("text/html; charset=utf-8", "html", "html")}
    if formato not in tipos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Formato no disponible.")
    mime, funcion, ext = tipos[formato]
    p = _prueba(db, user, prueba_id)
    if not p.definicion.get("processor") or not (p.registro.get("run") or {}).get("hojas"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Procese la prueba antes de descargar su papel.")
    try:
        contenido = getattr(libro, funcion)(*servicio.args_papel(db, p))
    except libro.PDFNoDisponible as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return Response(contenido, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="Papel_v{p.version}.{ext}"'})


@router.get("/pruebas/{prueba_id}/ejercicio-modelo")
def ejercicio_modelo_de(prueba_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    """Recorrido completo de la prueba con datos de ejemplo (SOLO LECTURA): corre
    el procesador sobre sus ejemplos y devuelve los 9 pasos. No modifica la
    prueba ni el estado del ciclo."""
    from backend.app.aud.niif import ejercicio_modelo as em

    p = _prueba(db, user, prueba_id)
    mod = procesadores.de(p.definicion)
    if mod is None:
        return {"disponible": False}
    return em.recorrido(p.definicion, mod)


@router.get("/pruebas/{prueba_id}/ejercicio-modelo/libro")
def ejercicio_modelo_libro(prueba_id: int, formato: str = "xlsx", db: Session = Depends(get_db),
                           user: User = Depends(require_staff)) -> Response:
    """Papel de muestra del ejercicio modelo en Excel/Word/PowerPoint/HTML (SOLO LECTURA)."""
    from backend.app.aud.niif import ejercicio_modelo as em

    tipos = {"xlsx": almacen.TIPOS["xlsx"],
             "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
             "html": "text/html; charset=utf-8"}
    if formato not in tipos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Formato no disponible.")
    p = _prueba(db, user, prueba_id)
    mod = procesadores.de(p.definicion)
    if mod is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Esta prueba no tiene ejercicio modelo.")
    try:
        contenido = em.libro_modelo(p.definicion, mod, formato)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return Response(contenido, media_type=tipos[formato],
                    headers={"Content-Disposition": f'attachment; filename="Ejercicio_modelo.{formato}"'})
