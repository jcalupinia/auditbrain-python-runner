"""Ingesta tabular incremental: normalizacion por lote y persistencia transaccional.

Modulo opt-in: NO modifica la API historica, NO ejecuta DDL al importar.
El llamador aporta un Engine SQLAlchemy y confirma un mapeo canonico.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, JSON, MetaData, String,
    Table, UniqueConstraint, create_engine, func, select, update,
)

from backend.app.ingesta.mapeo.esquemas import resolver_esquema
from backend.app.ingesta.mapeo.mayores_auto import separar_importe_firmado
from backend.app.ingesta.normalizer import normalizar_valor
from backend.app.ingesta.streaming_lotes import DEFAULT_BATCH_ROWS, iterar_lotes

metadata = MetaData()
datasets = Table(
    "ingesta_masiva_datasets", metadata,
    Column("id", String(36), primary_key=True),
    Column("cliente_id", String(128), nullable=False),
    Column("encargo_id", String(128), nullable=False),
    Column("periodo", String(32), nullable=False),
    Column("tipo_documento", String(64), nullable=False),
    Column("archivo", String(512), nullable=False),
    Column("sha256_archivo", String(64), nullable=False),
    Column("estado", String(32), nullable=False),
    Column("total_filas", Integer, nullable=False, default=0),
    Column("filas_revision", Integer, nullable=False, default=0),
    Column("error", String(2000)),
    Column("creado_en", DateTime(timezone=True), nullable=False),
)
filas = Table(
    "ingesta_masiva_filas", metadata,
    Column("dataset_id", String(36), ForeignKey("ingesta_masiva_datasets.id"), nullable=False),
    Column("numero_fila", Integer, nullable=False),
    Column("datos", JSON, nullable=False),
    Column("errores", JSON, nullable=False),
    UniqueConstraint("dataset_id", "numero_fila", name="uq_ingesta_masiva_fila"),
)


def crear_tablas(engine) -> None:
    """DDL explicito; llamar solo sobre base autorizada de desarrollo."""
    metadata.create_all(engine, tables=[datasets, filas])


def _sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _jsonable(valor):
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return valor


def normalizar_bloque(bloque, mapeo, esquema, *, primera_fila=1, positivo_es=None):
    """Generador: nunca construye una lista de la poblacion completa."""
    for offset, origen in enumerate(bloque):
        registro, errores = {}, []
        for campo in esquema.campos:
            indice = mapeo.get(campo.nombre)
            if indice is None:
                if campo.obligatorio:
                    errores.append(f"{campo.nombre}: sin columna asignada")
                registro[campo.nombre] = None
                continue
            if not isinstance(indice, int) or indice < 0:
                raise ValueError(f"indice de columna invalido: {campo.nombre}")
            crudo = origen[indice] if indice < len(origen) else None
            if crudo is None or (isinstance(crudo, str) and not crudo.strip()):
                registro[campo.nombre] = None
                if campo.obligatorio:
                    errores.append(f"{campo.nombre}: obligatorio vacio")
                continue
            valor, _ = normalizar_valor(crudo, campo.tipo)
            registro[campo.nombre] = _jsonable(valor)
            if valor is None:
                errores.append(f"{campo.nombre}: normalizacion fallida")
        if "importe" in mapeo:
            indice_importe = mapeo["importe"]
            crudo_importe = origen[indice_importe] if indice_importe < len(origen) else None
            registro["importe_original"] = str(crudo_importe) if crudo_importe is not None else None
            try:
                debe, haber = separar_importe_firmado(crudo_importe, positivo_es=positivo_es)
                registro["debe"], registro["haber"] = str(debe), str(haber)
                errores = [e for e in errores if not e.startswith(("debe:", "haber:"))]
            except ValueError:
                errores.append("importe: normalizacion fallida")
        yield {"numero_fila": primera_fila + offset, "datos": registro, "errores": errores}


def ingerir_archivo(
    engine, archivo, *, cliente_id, encargo_id, periodo,
    tipo_documento, mapeo_confirmado, lote=DEFAULT_BATCH_ROWS,
    saltar_filas=1, hoja=None, positivo_es=None,
):
    """Persiste por lote; retorna metadatos, nunca filas completas.

    No reintenta automaticamente: ante error queda estado 'error' con lotes
    confirmados para diagnostico. Una nueva invocacion crea otro dataset.
    """
    if not all([cliente_id, encargo_id, periodo]):
        raise ValueError("cliente_id, encargo_id y periodo son obligatorios")
    if type(saltar_filas) is not int or saltar_filas < 0:
        raise ValueError("saltar_filas debe ser un entero no negativo")
    if type(lote) is not int or not 1 <= lote <= 10_000:
        raise ValueError("lote debe ser un entero entre 1 y 10000")
    esquema = resolver_esquema(tipo_documento)
    firmado = esquema.tipo_documento.value == 'mayor' and 'importe' in mapeo_confirmado
    permitidos = {c.nombre for c in esquema.campos} | ({'importe'} if esquema.tipo_documento.value == 'mayor' else set())
    if not mapeo_confirmado or set(mapeo_confirmado) - permitidos:
        raise ValueError("mapeo_confirmado vacio o contiene campos desconocidos")
    if any(type(indice) is not int or indice < 0 for indice in mapeo_confirmado.values()):
        raise ValueError("los indices del mapeo deben ser enteros no negativos")
    if len(set(mapeo_confirmado.values())) != len(mapeo_confirmado):
        raise ValueError("una columna no puede asignarse a varios campos")
    if firmado and positivo_es not in ('debe', 'haber'):
        raise ValueError('importe firmado requiere positivo_es confirmado: debe o haber')
    if firmado and ('debe' in mapeo_confirmado or 'haber' in mapeo_confirmado):
        raise ValueError('no mezclar importe firmado con debe/haber')
    for campo in esquema.obligatorios:
        if firmado and campo.nombre in ('debe', 'haber'):
            continue
        if campo.nombre not in mapeo_confirmado:
            raise ValueError(f"falta confirmar campo obligatorio: {campo.nombre}")
    ruta = Path(archivo)
    dataset_id = str(uuid4())
    ahora = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(datasets.insert().values(
            id=dataset_id, cliente_id=str(cliente_id), encargo_id=str(encargo_id),
            periodo=str(periodo), tipo_documento=esquema.tipo_documento.value,
            archivo=ruta.name, sha256_archivo=_sha256(ruta), estado="procesando",
            total_filas=0, filas_revision=0, creado_en=ahora,
        ))
    total = revision = 0
    pendientes_saltar = saltar_filas
    numero_fila = 1
    try:
        for bloque in iterar_lotes(ruta, lote=lote, hoja=hoja):
            if pendientes_saltar:
                quitar = min(pendientes_saltar, len(bloque))
                bloque = bloque[quitar:]
                numero_fila += quitar
                pendientes_saltar -= quitar
            if not bloque:
                continue
            registros = list(normalizar_bloque(
                bloque, mapeo_confirmado, esquema, primera_fila=numero_fila, positivo_es=positivo_es
            ))
            n_revision = sum(bool(r["errores"]) for r in registros)
            with engine.begin() as conn:
                conn.execute(filas.insert(), [
                    {"dataset_id": dataset_id, **r} for r in registros
                ])
                conn.execute(datasets.update().where(datasets.c.id == dataset_id).values(
                    total_filas=total + len(registros),
                    filas_revision=revision + n_revision,
                ))
            total += len(registros)
            revision += n_revision
            numero_fila += len(registros)
        with engine.begin() as conn:
            conn.execute(datasets.update().where(datasets.c.id == dataset_id).values(estado="completado" if revision == 0 else "requiere_revision"))
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(datasets.update().where(datasets.c.id == dataset_id).values(
                estado="error", error=f"{type(exc).__name__}: {str(exc)[:1800]}"
            ))
        raise
    return {"dataset_id": dataset_id, "estado": "completado" if revision == 0 else "requiere_revision",
            "total_filas": total, "filas_revision": revision}


def consultar_filas(engine, dataset_id, *, cliente_id, encargo_id, limite=100, desde_fila=0):
    """Consulta paginada y segregada por cliente y encargo."""
    if not 1 <= limite <= 1000 or desde_fila < 0:
        raise ValueError("paginacion invalida")
    with engine.connect() as conn:
        permitido = conn.execute(select(datasets.c.id).where(
            datasets.c.id == dataset_id,
            datasets.c.cliente_id == str(cliente_id),
            datasets.c.encargo_id == str(encargo_id),
        )).scalar_one_or_none()
        if permitido is None:
            raise LookupError("dataset inexistente o fuera del encargo")
        resultado = conn.execute(select(
            filas.c.numero_fila, filas.c.datos, filas.c.errores
        ).where(
            filas.c.dataset_id == dataset_id,
            filas.c.numero_fila > desde_fila,
        ).order_by(filas.c.numero_fila).limit(limite)).mappings().all()
    return [dict(r) for r in resultado]
