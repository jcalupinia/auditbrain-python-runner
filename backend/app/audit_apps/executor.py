"""Ejecutor de una Audit App declarada (inputs → steps → outputs) — SCAFFOLD.

Corre una app del registro contra el **motor determinista**: resuelve cada
``StepSpec.engine_ref`` a un callable puro de ``motor``/``backend.app.aud``, le
pasa los insumos leídos y los parámetros validados, encadena lo que cada paso
``produces`` y arma las salidas declaradas. El LLM no interviene en el cálculo
(§6): un paso solo puede apuntar a una función determinista, nunca a un prompt.

**El ejecutor no reimplementa la orquestación.** Se apoya en el Execution engine
(Agente D, ``backend/app/execution/``): cada corrida es un ``ExecutionRun`` con
``app_id``/``app_version``/``engine_version``/``input_hashes``/``parameter_snapshot``
/``output_hashes`` congelados, para reproducibilidad y lineage (§6). Aquí se
declara la interfaz; el enganche a la cola/persistencia y a los lectores de
insumos (``motor/ingesta``, parsers ICT, ``inventarios_vnr``) se implementa a
verde en el servidor.

**Estado: scaffold tipado.** Importa solo ``manifest`` (Python puro) en tiempo de
módulo; ``motor`` y la BD se resuelven en ejecución (import diferido) para no
romper el import en un contenedor sin dependencias.

Contrato de resolución de ``engine_ref`` (a implementar):

- Allow-list de raíces permitidas: ``motor.*`` y ``backend.app.aud.*`` (nunca
  ``backend.app.forge``, la web, ni módulos con efectos de red). Un ``engine_ref``
  fuera de la allow-list se rechaza ANTES de importarlo (evita RCE por manifest).
- El callable resuelto debe ser determinista y devolver datos serializables; su
  versión entra en ``engine_version`` para congelar la corrida.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .manifest import AuditAppManifest, StepSpec


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _hash_valor(v: Any) -> str:
    if isinstance(v, (bytes, bytearray)):
        return _hash_bytes(bytes(v))
    blob = json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

#: Raíces de import permitidas para ``engine_ref`` (defensa contra RCE por manifest).
ENGINE_ALLOWLIST = ("motor.", "backend.app.aud.")


class ExecutorError(RuntimeError):
    """La corrida no se puede completar. El caller marca la corrida como fallida."""


class EngineRefNotAllowedError(ExecutorError):
    """El ``engine_ref`` del paso apunta fuera de la allow-list determinista."""


class StepDependencyError(ExecutorError):
    """Un paso pide un insumo/intermedio que ningún paso anterior produjo."""


class InsufficientInputError(ExecutorError):
    """Un insumo requerido falta o no trae las columnas mínimas del paso.

    El ejecutor NO inventa columnas ni ceros (regla de oro de ``motor/ingesta``):
    deja el paso como no disponible y lo reporta, en vez de dar "sin excepciones"
    con datos incompletos.
    """


@dataclass(frozen=True)
class StepResult:
    """Resultado de un paso: lo que ``produces`` (para pasos siguientes/salidas)
    y su huella, para el lineage de la corrida."""

    step_id: str
    produces: str
    value: Any = None
    output_hash: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    """Resultado de correr la app: artefactos por salida, resultados por paso,
    aceptaciones evaluadas y las huellas que congelan la corrida.

    Es el material del que el Execution engine arma el ``ExecutionRun`` inmutable
    y del que el Workpaper (Agente F) toma las salidas para sellar el libro.
    """

    app_id: str
    app_version: str
    engine_version: str
    input_hashes: Mapping[str, str] = field(default_factory=dict)
    parameter_snapshot: Mapping[str, Any] = field(default_factory=dict)
    output_hashes: Mapping[str, str] = field(default_factory=dict)
    steps: tuple[StepResult, ...] = ()
    outputs: Mapping[str, bytes] = field(default_factory=dict)
    acceptance: tuple[dict[str, Any], ...] = ()
    disponibles: tuple[str, ...] = ()
    no_disponibles: tuple[str, ...] = ()


class AuditAppExecutor:
    """Corre una Audit App validada contra el motor determinista. SCAFFOLD."""

    def __init__(
        self,
        *,
        engine_version: str = "",
        resolver: Callable[[StepSpec], Callable[..., Any]] | None = None,
    ) -> None:
        self._engine_version = engine_version
        # Inyección de dependencia: en producción se cablea el motor
        # (import co-localizado o proxy HTTP al servicio del motor); en tests se
        # inyectan funciones deterministas. Sin resolver, se usa el import con
        # allow-list de `resolve_engine_ref`.
        self._resolver = resolver

    def run(
        self,
        manifest: AuditAppManifest,
        *,
        inputs: Mapping[str, bytes],
        parameters: Mapping[str, Any],
        executed_by: str,
    ) -> ExecutionResult:
        """Ejecuta la app y devuelve el ``ExecutionResult``.

        Pasos (a implementar a verde en el servidor):
          1. ``manifest.validate()`` — no se corre una app mal declarada.
          2. Validar/convertir ``parameters`` contra ``manifest.parameters``
             (tipos + restricciones, patrón ``motor/parametros.py``; ``Decimal``
             para importes; sin defaults salvo los declarados).
          3. Leer cada insumo (``motor/ingesta``, parsers ICT, VNR) y evaluar
             suficiencia contra ``InputSpec.columns``; sha256 de cada archivo →
             ``input_hashes`` (cierra DATA-008 también fuera del mayor).
          4. Por cada ``StepSpec`` en orden: resolver ``engine_ref`` con
             ``resolve_engine_ref`` (allow-list), pasarle insumos/intermedios/
             parámetros, guardar lo que ``produces``. Un paso sin sus columnas
             queda en ``no_disponibles`` (no se fuerza).
          5. Materializar ``outputs`` desde los pasos ``from_step``; sellar las
             ``sealed`` (versión/timestamp/hash).
          6. Evaluar ``acceptance_tests`` sobre el resultado y dejarlas en trace.

        No hace ``commit`` ni encola: eso lo orquesta el Execution engine (D),
        que envuelve esta corrida en un ``ExecutionRun`` inmutable.

        Convención de llamada de cada paso: el callable resuelto se invoca como
        ``fn(ctx)`` con ``ctx = {"inputs", "intermediates", "parameters"}`` y
        devuelve el valor que el paso ``produces``. En producción el callable es
        un adaptador delgado sobre una función del motor; en tests se inyecta.
        """
        # 1. Manifest válido.
        manifest.validate()

        # 2. Parámetros: los requeridos deben venir; se congelan tal cual.
        parameter_snapshot: dict[str, Any] = dict(parameters)
        for par in manifest.parameters:
            if par.required and par.id not in parameter_snapshot:
                raise InsufficientInputError(f"falta el parámetro requerido '{par.id}'")

        # 3. Insumos por hash + suficiencia (presencia; las columnas las evalúa el lector).
        input_hashes: dict[str, str] = {
            k: _hash_bytes(v) for k, v in inputs.items()
        }
        disponibles: list[str] = []
        no_disponibles: list[str] = []
        for inp in manifest.inputs:
            if inp.id in inputs:
                disponibles.append(inp.id)
            elif inp.required:
                no_disponibles.append(inp.id)

        # 4. Pasos en orden; cada paso consume insumos/intermedios/parámetros.
        intermedios: dict[str, Any] = {}
        steps_result: list[StepResult] = []
        for st in manifest.steps:
            faltan = [
                ref for ref in st.inputs
                if ref not in inputs and ref not in intermedios
            ]
            if faltan:
                # No se fuerza: el paso queda no disponible y se informa.
                if st.produces:
                    no_disponibles.append(st.produces)
                continue
            fn = self._resolver(st) if self._resolver is not None else self.resolve_engine_ref(st)
            ctx = {
                "inputs": {ref: inputs[ref] for ref in st.inputs if ref in inputs},
                "intermediates": {ref: intermedios[ref] for ref in st.inputs if ref in intermedios},
                "parameters": {pid: parameter_snapshot.get(pid) for pid in st.parameters},
            }
            valor = fn(ctx)
            if st.produces:
                intermedios[st.produces] = valor
            steps_result.append(StepResult(
                step_id=st.id, produces=st.produces, value=valor,
                output_hash=_hash_valor(valor),
            ))

        # 5. Salidas declaradas desde los pasos que produjeron.
        outputs: dict[str, bytes] = {}
        output_hashes: dict[str, str] = {}
        for out in manifest.outputs:
            paso = next((s for s in manifest.steps if s.id == out.from_step), None)
            if paso is None or not paso.produces or paso.produces not in intermedios:
                continue
            valor = intermedios[paso.produces]
            crudo = valor if isinstance(valor, (bytes, bytearray)) else json.dumps(
                valor, ensure_ascii=False, default=str).encode("utf-8")
            outputs[out.id] = bytes(crudo)
            output_hashes[out.id] = _hash_bytes(bytes(crudo))

        # 6. Aceptaciones: se dejan en el trace (evaluación declarativa pendiente
        #    de un evaluador de expresiones; nunca se marcan "cumplidas" a ciegas).
        acceptance = tuple(
            {"id": at.id, "description": at.description, "expects": at.expects,
             "evaluado": False, "resultado": "pendiente de evaluación humana/servidor"}
            for at in manifest.acceptance_tests
        )

        return ExecutionResult(
            app_id=manifest.id,
            app_version=manifest.version,
            engine_version=self._engine_version,
            input_hashes=input_hashes,
            parameter_snapshot=parameter_snapshot,
            output_hashes=output_hashes,
            steps=tuple(steps_result),
            outputs=outputs,
            acceptance=acceptance,
            disponibles=tuple(disponibles),
            no_disponibles=tuple(no_disponibles),
        )

    def resolve_engine_ref(self, step: StepSpec) -> Callable[..., Any]:
        """Resuelve ``step.engine_ref`` a un callable determinista, validando la
        allow-list ANTES de importar. Lanza ``EngineRefNotAllowedError`` si la
        ruta cae fuera de ``ENGINE_ALLOWLIST`` (evita ejecución arbitraria por un
        manifest hostil)."""
        ref = step.engine_ref or ""
        if not any(ref.startswith(prefijo) for prefijo in ENGINE_ALLOWLIST):
            raise EngineRefNotAllowedError(
                f"engine_ref '{ref}' fuera de la allow-list {ENGINE_ALLOWLIST}"
            )
        modulo_path, _, attr = ref.rpartition(".")
        try:
            modulo = importlib.import_module(modulo_path)
            fn = getattr(modulo, attr)
        except (ImportError, AttributeError) as e:
            raise ExecutorError(f"no se pudo resolver engine_ref '{ref}': {e}") from e
        if not callable(fn):
            raise ExecutorError(f"engine_ref '{ref}' no es un callable")
        return fn
