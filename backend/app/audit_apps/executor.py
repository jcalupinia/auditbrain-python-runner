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

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .manifest import AuditAppManifest, StepSpec

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

    def __init__(self, *, engine_version: str = "") -> None:
        self._engine_version = engine_version

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
        """
        raise NotImplementedError(
            "audit_apps.executor.run: implementar contra el motor/execution engine en el servidor"
        )

    def resolve_engine_ref(self, step: StepSpec) -> Callable[..., Any]:
        """Resuelve ``step.engine_ref`` a un callable determinista, validando la
        allow-list ANTES de importar. Lanza ``EngineRefNotAllowedError`` si la
        ruta cae fuera de ``ENGINE_ALLOWLIST`` (evita ejecución arbitraria por un
        manifest hostil)."""
        raise NotImplementedError(
            "audit_apps.executor.resolve_engine_ref: implementar import diferido con allow-list"
        )
