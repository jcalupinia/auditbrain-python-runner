"""Contrato ``AuditAppManifest`` — la declaración versionada de una Audit App.

Una Audit App es una prueba de auditoría **declarada como dato**, no como código:
qué marcos y aserciones cubre, qué riesgos ataca, qué insumos consume, con qué
parámetros, qué pasos deterministas ejecuta el motor, qué salidas produce y qué
tiene que cumplir para darse por correcta. El manifest es la **única fuente de
verdad** de esa declaración; el registro (``registry.py``) la versiona y el
ejecutor (``executor.py``) la corre contra el motor determinista.

El contrato es el ``AuditAppManifest`` de la §2 de
``motor-auditoria-analitica/docs/ARQUITECTURA_CONVERGENCIA_v1.md``:

    id, name, version, owner, frameworks, assertions, risks, inputs,
    parameters, steps, outputs, permissions, requires_ai/ml, acceptance_tests.

**Principio no negociable (benchmark §6):** el manifest NO calcula cifras. Solo
declara. El cálculo lo hace Python en el motor; el LLM no recalcula. Todo paso
apunta a una función determinista del motor por ``engine_ref``, nunca a un prompt.

Esta capa es **Python puro** (stdlib): no importa FastAPI, SQLAlchemy ni el motor,
para que la validación del manifest se pueda probar aislada en el servidor sin
levantar dependencias. La persistencia (registry) y la ejecución (executor) sí
dependen del resto de la plataforma y se implementan a verde en el servidor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

# --- Reglas de forma (contratos de texto) -----------------------------------

#: ``id`` de app y de sub-entidades: slug estable, apto para URL y para clave de BD.
_SLUG = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
#: ``id`` de app del benchmark (AUD-INV-VNR, AUD-AST-DUP…): mayúsculas con guiones.
_APP_ID = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)+$")
#: Versión semver estricta (MAJOR.MINOR.PATCH). El registry ordena por ella.
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
#: ``engine_ref``: ruta punteada a un callable determinista del motor.
#: Ej.: ``aud.inventarios_vnr.engine.calculate`` · ``motor.programa.correr_disponibles``.
_ENGINE_REF = re.compile(r"^[a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)+$")

#: Tipos de parámetro admitidos (se validan y convierten en el ejecutor, con
#: ``Decimal`` para todo importe — regla de dinero del benchmark §6).
PARAM_TYPES = ("decimal", "int", "date", "bool", "text", "list_date", "enum")

#: Naturaleza de un insumo: define qué lector/parametrizador aplica el ejecutor.
INPUT_KINDS = (
    "mayor", "comprobantes", "ventas", "proveedores", "nomina",
    "inventario", "balance", "formulario_sri", "documento", "tabla",
)

#: Naturaleza de una salida (papel de trabajo / entregable).
OUTPUT_KINDS = ("excel", "html", "pdf", "json", "excepciones", "dataset_bi")


class ManifestValidationError(ValueError):
    """El manifest no cumple el contrato §2. Lleva la lista de problemas.

    El registro (``registry.register``) rechaza el alta y el ejecutor se niega a
    correr una app cuyo manifest no valida: una app mal declarada nunca llega a
    tocar datos del cliente.
    """

    def __init__(self, problemas: Sequence[str]) -> None:
        self.problemas: tuple[str, ...] = tuple(problemas)
        super().__init__("; ".join(self.problemas) or "manifest inválido")


# --- Sub-contratos ----------------------------------------------------------


@dataclass(frozen=True)
class InputSpec:
    """Un insumo declarado: qué base/archivo consume la app y con qué columnas.

    ``columns`` son las columnas mínimas que el paso necesita; el ejecutor las
    cruza con la suficiencia real del archivo (patrón ``motor/suficiencia.py``)
    y deja no disponible el paso al que le falten, en vez de inventar ceros.
    """

    id: str
    kind: str
    formats: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    required: bool = True
    description: str = ""


@dataclass(frozen=True)
class ParameterSpec:
    """Un parámetro del encargo (bloque U): sin valor por defecto salvo que se
    declare. El ejecutor exige los ``required`` y los congela con el resultado.
    """

    id: str
    type: str
    required: bool = True
    default: Any = None
    description: str = ""
    #: Restricciones declarativas (``{"min": "0", "le": "materialidad"}``…);
    #: el ejecutor las evalúa como en ``motor/parametros.py``.
    constraints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepSpec:
    """Un paso determinista: apunta a un callable del motor por ``engine_ref``.

    ``inputs``/``parameters`` referencian ids declarados en el manifest;
    ``produces`` nombra el artefacto/intermedio que deja para pasos siguientes o
    para las salidas. **Nunca** apunta a un prompt: el LLM no calcula (§6).
    """

    id: str
    engine_ref: str
    inputs: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()
    produces: str = ""
    description: str = ""


@dataclass(frozen=True)
class OutputSpec:
    """Una salida (papel de trabajo / entregable). ``sealed`` marca las que se
    sellan con versión/timestamp/hash (patrón ``sealing.py`` del Agente F)."""

    id: str
    kind: str
    from_step: str = ""
    sealed: bool = False
    description: str = ""


@dataclass(frozen=True)
class AcceptanceTest:
    """Criterio de aceptación de la app (benchmark §6): una comprobación que la
    corrida tiene que satisfacer (``A=P+Pa``, ``deterioro>=0``, conteo de cas…).
    El ejecutor la evalúa sobre el resultado y la deja en el trace de la corrida.
    """

    id: str
    description: str
    expects: str = ""


# --- Contrato principal -----------------------------------------------------


@dataclass(frozen=True)
class AuditAppManifest:
    """Declaración versionada de una Audit App (contrato §2).

    Es inmutable (``frozen``): una versión publicada no se edita, se sube otra
    (regla de outputs inmutables del §6). Construir con ``from_dict`` (dict/YAML)
    o con el constructor; ``validate()`` verifica el contrato y lanza
    ``ManifestValidationError`` con TODOS los problemas juntos.
    """

    id: str
    name: str
    version: str
    owner: str
    frameworks: tuple[str, ...]
    assertions: tuple[str, ...]
    risks: tuple[str, ...]
    inputs: tuple[InputSpec, ...]
    parameters: tuple[ParameterSpec, ...]
    steps: tuple[StepSpec, ...]
    outputs: tuple[OutputSpec, ...]
    permissions: tuple[str, ...]
    requires_ai: bool = False
    requires_ml: bool = False
    acceptance_tests: tuple[AcceptanceTest, ...] = ()

    # -- Construcción desde dict/YAML ---------------------------------------

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AuditAppManifest":
        """Construye el manifest desde un dict (el que sale de ``yaml.safe_load``
        o de un JSON de la API). Normaliza listas a tuplas y sub-dicts a sus
        dataclasses. NO valida el contenido — para eso está ``validate()`` —,
        solo la forma mínima para poder instanciar; un campo raíz ausente cae en
        ``ManifestValidationError`` con el nombre del campo.
        """
        faltan = [
            k for k in (
                "id", "name", "version", "owner", "frameworks", "assertions",
                "risks", "inputs", "parameters", "steps", "outputs", "permissions",
            )
            if k not in data
        ]
        if faltan:
            raise ManifestValidationError([f"falta el campo raíz '{k}'" for k in faltan])

        def _tabla(clave: str, tipo: type) -> tuple:
            filas = data.get(clave) or []
            if not isinstance(filas, (list, tuple)):
                raise ManifestValidationError([f"'{clave}' debe ser una lista"])
            hechas = []
            for i, cruda in enumerate(filas):
                if not isinstance(cruda, Mapping):
                    raise ManifestValidationError([f"'{clave}[{i}]' debe ser un objeto"])
                hechas.append(_construir_fila(tipo, cruda, f"{clave}[{i}]"))
            return tuple(hechas)

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            version=str(data["version"]),
            owner=str(data["owner"]),
            frameworks=tuple(data.get("frameworks") or ()),
            assertions=tuple(data.get("assertions") or ()),
            risks=tuple(data.get("risks") or ()),
            inputs=_tabla("inputs", InputSpec),
            parameters=_tabla("parameters", ParameterSpec),
            steps=_tabla("steps", StepSpec),
            outputs=_tabla("outputs", OutputSpec),
            permissions=tuple(data.get("permissions") or ()),
            requires_ai=bool(data.get("requires_ai", False)),
            requires_ml=bool(data.get("requires_ml", False)),
            acceptance_tests=_tabla("acceptance_tests", AcceptanceTest)
            if data.get("acceptance_tests") else (),
        )

    # -- Validación del contrato --------------------------------------------

    def validate(self) -> "AuditAppManifest":
        """Verifica el contrato §2 y devuelve ``self`` si está bien.

        Junta TODOS los problemas y lanza ``ManifestValidationError`` una sola
        vez (no falla en el primero): quien publica la app ve la lista completa.
        Comprueba forma (ids, semver, tipos) y **coherencia interna** (cada paso
        referencia insumos/parámetros que existen; cada salida, un paso que
        existe; ids únicos; ``engine_ref`` con forma de ruta punteada).
        """
        p: list[str] = []

        if not (_APP_ID.match(self.id) or _SLUG.match(self.id)):
            p.append(f"id inválido: {self.id!r} (use AUD-INV-VNR o slug)")
        if not _SEMVER.match(self.version):
            p.append(f"version no es semver MAJOR.MINOR.PATCH: {self.version!r}")
        for campo in ("name", "owner"):
            if not str(getattr(self, campo)).strip():
                p.append(f"'{campo}' no puede estar vacío")
        for campo in ("frameworks", "assertions", "risks", "permissions",
                      "inputs", "steps", "outputs"):
            if not getattr(self, campo):
                p.append(f"'{campo}' no puede estar vacío")

        input_ids = _ids_unicos(self.inputs, "inputs", p)
        param_ids = _ids_unicos(self.parameters, "parameters", p)
        step_ids = _ids_unicos(self.steps, "steps", p)
        _ids_unicos(self.outputs, "outputs", p)
        _ids_unicos(self.acceptance_tests, "acceptance_tests", p)

        for inp in self.inputs:
            if inp.kind not in INPUT_KINDS:
                p.append(f"input '{inp.id}': kind desconocido {inp.kind!r}")
        for par in self.parameters:
            if par.type not in PARAM_TYPES:
                p.append(f"parameter '{par.id}': type desconocido {par.type!r}")
        for out in self.outputs:
            if out.kind not in OUTPUT_KINDS:
                p.append(f"output '{out.id}': kind desconocido {out.kind!r}")
            if out.from_step and out.from_step not in step_ids:
                p.append(f"output '{out.id}': from_step '{out.from_step}' no existe")

        producidos: set[str] = set()
        for st in self.steps:
            if not _ENGINE_REF.match(st.engine_ref or ""):
                p.append(f"step '{st.id}': engine_ref inválido {st.engine_ref!r}")
            for ref in st.inputs:
                if ref not in input_ids and ref not in producidos:
                    p.append(f"step '{st.id}': input '{ref}' no declarado ni producido antes")
            for ref in st.parameters:
                if ref not in param_ids:
                    p.append(f"step '{st.id}': parameter '{ref}' no declarado")
            if st.produces:
                producidos.add(st.produces)

        if p:
            raise ManifestValidationError(p)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Serializa el manifest a un dict JSON-able (para la API y el registry)."""
        from dataclasses import asdict

        return asdict(self)


# --- Helpers privados -------------------------------------------------------


def _construir_fila(tipo: type, cruda: Mapping[str, Any], donde: str) -> Any:
    """Instancia una dataclass de sub-contrato desde un dict, tolerando claves
    extra (se ignoran) y normalizando las secuencias a tuplas."""
    campos = {f.name for f in tipo.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    kwargs: dict[str, Any] = {}
    for k, v in cruda.items():
        if k not in campos:
            continue
        kwargs[k] = tuple(v) if isinstance(v, list) else v
    try:
        return tipo(**kwargs)
    except TypeError as e:  # falta un campo obligatorio de la sub-dataclass
        raise ManifestValidationError([f"{donde}: {e}"]) from e


def _ids_unicos(filas: Sequence[Any], donde: str, problemas: list[str]) -> set[str]:
    """Reúne los ids de una tabla y anota en ``problemas`` los duplicados/ vacíos."""
    vistos: set[str] = set()
    for i, fila in enumerate(filas):
        fid = getattr(fila, "id", "")
        if not fid:
            problemas.append(f"{donde}[{i}]: id vacío")
        elif fid in vistos:
            problemas.append(f"{donde}: id duplicado {fid!r}")
        else:
            vistos.add(fid)
    return vistos
