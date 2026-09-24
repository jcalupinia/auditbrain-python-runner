# P2-G · Gobierno agentic del encargo — hash-chain de la bitácora, roles reales y checkpoints de IA

> **For agentic workers:** REQUIRED SUB-SKILL: usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea por tarea. Los pasos usan checkbox (`- [ ]`) para seguimiento.
>
> **Entorno:** este plan corre en el **servidor** (`auditbrain-python-runner`), con FastAPI + SQLAlchemy + PostgreSQL/SQLite. Las dependencias NO corren en el contenedor donde se escribió el plan; cada tarea se lleva **a verde con `pytest`** en el servidor.

**Goal:** que la bitácora del encargo (`PruebaEvento`) sea una **cadena append-only verificable** (igual que `ForgeDecision`), que la **segregación de funciones se ejerza por rol real** (hoy todo entra como `ADMIN`) y que las **acciones de IA del ciclo dejen un checkpoint** firmado en esa cadena. Todo sin romper el ciclo existente ni sus tests "espejo" (`test_aud_ciclo_reglas.py`).

**Capacidades que cierra:** ENG-020 (encadenar la bitácora del encargo), ENG-005 (aprobación por rol que hoy no se ejerce), ENG-018 (permisos de agente en el encargo IA), ENG-019 (checkpoints de agente, hoy placeholders `None`).

## Architecture

- **Reutilización con contrato, no reimplementación.** El primitivo de hash ya está vendorizado y blindado con vectores fijos en `backend/app/forge/engine/governance/audit.py` (`compute_hash`, `GENESIS`, `_CAMPOS_FIRMADOS`). El ciclo firma otros campos que Forge, así que se crea `backend/app/aud/niif/ciclo/gobernanza.py` con **su propio contrato de campos firmados** (`_CAMPOS_EVENTO`) y su propia función pura `compute_hash_evento(entrada, prev_hash)`, calcada del patrón de Forge (mismo `sha256("|".join(...)|prev_hash)`), reusando `GENESIS`. No se toca el módulo de Forge.
- **Un solo punto de escritura.** Toda la bitácora pasa hoy por `servicio._evento(...)`. Ahí —y solo ahí— se calcula `seq`, `prev_hash` y `hash`. El resto del servicio no cambia su forma de registrar.
- **Append-only de verdad.** Como en Forge, la garantía dura es un trigger de BD que prohíbe `UPDATE`/`DELETE` sobre `aud_prueba_eventos` (`init_db()`); el código es la defensa en profundidad.
- **Rol real.** `reglas.transicion(t, accion, rol)` YA acepta `rol` y YA valida `PUEDEN_APROBAR`; el default `"ADMIN"` se conserva para el espejo. Lo que falta es que el **servicio le pase el rol real** del usuario autenticado en las acciones `approve*`, en vez de dejar el default. Se añade un mapeo `rol_de_usuario(User) -> str` y `accion(...)` lo propaga.
- **Checkpoint de IA.** Cada interpretación IA del ciclo (patrón `ict/audit/interpreter.py`) que se materialice en el encargo registra un `PruebaEvento` con `accion="ai_checkpoint"` (modelo, hash del input, confianza, `requiere_revision_humana`), quedando dentro de la misma cadena verificable. Una acción IA con `requiere_revision_humana=True` no habilita por sí sola una transición de aprobación.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic (o el mecanismo de migración vigente del repo), pytest. Repo `auditbrain-python-runner`, rama sugerida `p2g-gobierno-agentic`.

**Contexto obligatorio a leer antes de empezar:**
- `backend/app/forge/engine/governance/audit.py` y `.../plan_hash.py` — el primitivo a calcar.
- `backend/app/forge/governance_service.py` — `append_decision`/`verify_chain` como referencia de estilo.
- `backend/app/aud/niif/ciclo/models.py` (`PruebaEvento`), `servicio.py` (`_evento`, `crear_prueba`, `accion`), `reglas.py` (`transicion`, `PUEDEN_APROBAR`), `router.py` (`require_staff`).
- `tests/test_aud_ciclo_reglas.py` (el "espejo" — NO debe cambiar de resultado).

**Convenciones:** español en código y comentarios; `python -m pytest -q` desde la raíz; no romper los tests espejo ni los legacy ya documentados en `CLAUDE.md`.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `backend/app/aud/niif/ciclo/gobernanza.py` (crear) | `compute_hash_evento`, `_CAMPOS_EVENTO`, `entrada_firmada`, `verificar_cadena`, `rol_de_usuario` |
| `backend/app/aud/niif/ciclo/models.py` (modificar) | `PruebaEvento`: `+seq`, `+content_hash`, `+prev_hash`, `+hash`; `UniqueConstraint(prueba_id, seq)` |
| migración (crear) | columnas nuevas + backfill de la cadena histórica + trigger append-only |
| `backend/app/aud/niif/ciclo/servicio.py` (modificar) | `_evento` encadena; `accion(...)` propaga rol real; `checkpoint_ia(...)`; `verificar_bitacora(...)` |
| `backend/app/aud/niif/ciclo/router.py` (modificar) | pasar `user` a `accion`; endpoint `GET /pruebas/{id}/bitacora/verificar` |
| `backend/app/db/session.py` o `init_db` (modificar) | trigger append-only sobre `aud_prueba_eventos` |
| `tests/test_ciclo_gobernanza_hash.py` (crear) | vectores fijos + append + verify + detección de manipulación |
| `tests/test_ciclo_roles.py` (crear) | segregación por rol real |
| `tests/test_ciclo_checkpoint_ia.py` (crear) | checkpoint de IA en la cadena |

---

### Task 1: Primitivo de hash del ciclo (puro, con vectores fijos)

**Files:** Create `backend/app/aud/niif/ciclo/gobernanza.py`; Test `tests/test_ciclo_gobernanza_hash.py`.

- [ ] **Step 1: Pruebas que fallan**

```python
"""Hash de la cadena de la bitácora del encargo (P2-G)."""
from backend.app.aud.niif.ciclo.gobernanza import (
    GENESIS, compute_hash_evento, entrada_firmada,
)

def test_hash_es_estable_y_depende_del_prev():
    e = entrada_firmada(seq=1, ts="2026-09-24T00:00:00+00:00", actor="a@x.ec",
                        rol="SOCIO", accion="approve", prueba_id=7, revision=1,
                        estado_anterior="EN_REVISION", estado_nuevo="APROBADO",
                        content_hash="", comentario="ok")
    h1 = compute_hash_evento(e, GENESIS)
    assert len(h1) == 64 and h1 == compute_hash_evento(e, GENESIS)
    assert compute_hash_evento(e, h1) != h1  # encadena con el prev

def test_vector_fijo():
    # Blinda el contrato de campos/orden: si cambia, este vector cambia y avisa.
    e = entrada_firmada(seq=1, ts="2026-01-01T00:00:00+00:00", actor="x", rol="ADMIN",
                        accion="create", prueba_id=1, revision=1, estado_anterior=None,
                        estado_nuevo="PRUEBA_SELECCIONADA", content_hash="", comentario="")
    assert compute_hash_evento(e, GENESIS) == "<CONGELAR EN LA 1a CORRIDA>"
```

- [ ] **Step 2: Correr y ver que falla** — `ModuleNotFoundError: ...ciclo.gobernanza`. Congelar el vector con el hash real de la primera corrida (patrón `test_forge_governance_hash.py`).

- [ ] **Step 3: Implementar** `gobernanza.py`, calcado de `forge/engine/governance/audit.py`:
  - `GENESIS = "0" * 64` (reusar de Forge importándolo, o redeclarar con comentario de contrato).
  - `_CAMPOS_EVENTO = ("seq", "ts", "actor", "rol", "accion", "prueba_id", "revision", "estado_anterior", "estado_nuevo", "content_hash", "comentario")` — **orden fijo = contrato**; documentarlo.
  - `compute_hash_evento(entrada, prev_hash)`: `sha256("|".join(str(entrada.get(c,"")) for c in _CAMPOS_EVENTO) + "|" + prev_hash)`. Campo ausente = `""` (igual que Forge).
  - `entrada_firmada(**campos) -> dict`: arma el dict con las claves de `_CAMPOS_EVENTO`.

- [ ] **Step 4: Correr** — `pytest tests/test_ciclo_gobernanza_hash.py -q` verde.
- [ ] **Step 5: Commit** — `feat(ciclo): primitivo de hash de la bitácora con contrato de campos y vector fijo`.

---

### Task 2: `PruebaEvento` encadenado (modelo + migración + trigger append-only)

**Files:** Modify `models.py`; Create migración; Modify `init_db`. Test: reutiliza Task 3.

- [ ] **Step 1:** Añadir a `PruebaEvento`: `seq: int`, `content_hash: str = ""`, `prev_hash: str`, `hash: str`, y `__table_args__ = (UniqueConstraint("prueba_id", "seq", name="uq_prueba_evento_seq"),)`. La cadena es **por prueba** (`prueba_id`), reiniciando en `GENESIS` para cada prueba (una prueba es la unidad de trabajo; el `parent_id` versiona, no encadena entre versiones).
- [ ] **Step 2: Migración** con tres partes:
  1. `ADD COLUMN` para las cuatro columnas (nullable temporal).
  2. **Backfill**: por cada `prueba_id`, recorrer sus eventos ordenados por `id`, asignar `seq = 1..n`, recomputar `prev_hash`/`hash` con `compute_hash_evento` (la bitácora histórica no tenía cadena; se sella al migrar y a partir de ahí es inmutable). `content_hash=""` para los históricos.
  3. `ALTER COLUMN ... SET NOT NULL` en `seq`, `prev_hash`, `hash`.
  4. **Trigger append-only** sobre `aud_prueba_eventos` que haga `RAISE`/`ABORT` en `UPDATE` y `DELETE` (portar el patrón exacto del trigger de `forge_decisions` de `init_db`). En SQLite de desarrollo, replicar con el mecanismo equivalente que ya usa Forge.
- [ ] **Step 3:** Verificar que `init_db()` crea el trigger también en entornos nuevos.
- [ ] **Step 4:** `pytest tests/ -k ciclo -q` sigue verde (el modelo nuevo no rompe lecturas existentes).
- [ ] **Step 5: Commit** — `feat(ciclo): PruebaEvento append-only con seq/prev_hash/hash y trigger de BD`.

---

### Task 3: `_evento` encadena y el servicio expone `verificar_bitacora`

**Files:** Modify `servicio.py`; Test `tests/test_ciclo_gobernanza_hash.py` (ampliar con BD en memoria).

- [ ] **Step 1: Pruebas que fallan**

```python
def test_cadena_de_una_prueba_verifica(db):
    p = crear_prueba(db, project_id, "vnr", tributario=False, actor="a@x.ec")
    # ... avanzar el ciclo con acciones válidas ...
    filas = verificar_bitacora(db, p.id)          # no lanza
    assert [f.seq for f in filas] == list(range(1, len(filas) + 1))
    assert filas[0].prev_hash == GENESIS

def test_manipular_un_evento_rompe_la_verificacion(db):
    p = crear_prueba(db, project_id, "vnr", tributario=False, actor="a@x.ec")
    ev = eventos(db, p.id)[0]
    # forzar por SQL crudo (el ORM no puede por el trigger) un cambio de 'actor'
    db.execute(text("UPDATE aud_prueba_eventos SET actor='otro' WHERE id=:i"), {"i": ev.id})
    with pytest.raises(ChainError):
        verificar_bitacora(db, p.id)
```

- [ ] **Step 2: Correr y ver que falla.**
- [ ] **Step 3: Implementar** en `servicio.py`:
  - `_evento(...)`: antes de `db.add`, leer el último evento de la prueba (`max(seq)`), calcular `seq`, `prev_hash`, `ts` (ISO 8601 UTC, como Forge), `content_hash` (opcional: hash del `comentario`/payload relevante), y `hash = compute_hash_evento(entrada_firmada(...), prev_hash)`. Añadir `rol` a la firma de `_evento` (default `"ADMIN"` para no romper llamadas existentes hasta la Task 4).
  - `verificar_bitacora(db, prueba_id) -> list[PruebaEvento]`: recalcula desde `GENESIS`, lanza `ChainError` (reusar/espejar la de Forge) ante `seq` fuera de orden, `prev_hash` roto o `hash` alterado.
  - `_evento` sigue siendo el **único** escritor de la bitácora: no crear otras rutas de `db.add(PruebaEvento(...))`.
- [ ] **Step 4:** `pytest tests/test_ciclo_gobernanza_hash.py -q` verde; suite `-k ciclo` verde.
- [ ] **Step 5: Commit** — `feat(ciclo): la bitácora se escribe encadenada y se puede verificar`.

---

### Task 4: Segregación de funciones por rol real (ENG-005)

**Files:** Modify `gobernanza.py` (`rol_de_usuario`), `servicio.py` (`accion`), `router.py`. Test `tests/test_ciclo_roles.py`.

- [ ] **Step 1: Pruebas que fallan**

```python
def test_rol_operador_no_puede_aprobar(db):
    # Un usuario cuyo rol mapea fuera de PUEDEN_APROBAR no cierra 'approve'.
    p = _prueba_lista_para_aprobar(db)
    with pytest.raises(ReglaIncumplida, match="Su rol no permite aprobar"):
        accion(db, p.id, "approve", user=usuario(rol="user"), ...)

def test_rol_socio_si_aprueba(db):
    p = _prueba_lista_para_aprobar(db)
    r = accion(db, p.id, "approve", user=usuario(rol="socio"), ...)
    assert r.estado == "APROBADO"

def test_el_espejo_no_cambia():
    # transicion(t, accion) sin rol sigue usando ADMIN: los tests espejo pasan igual.
    import tests.test_aud_ciclo_reglas  # su ejecución no cambia de resultado
```

- [ ] **Step 2: Correr y ver que falla.**
- [ ] **Step 3: Implementar**:
  - `rol_de_usuario(user) -> str`: mapea el rol del portal (`admin`/`user`/`client` + roles de encargo si existen) al vocabulario de `PUEDEN_APROBAR` (`REVISOR`/`GERENTE`/`SOCIO`/`ADMIN`). **Decisión del dueño (2026-09-21):** admin y operadores aprueban; conservar ese comportamiento como default y añadir el gate solo donde el encargo defina roles finos. Documentar el mapa en el docstring.
  - `accion(db, prueba_id, accion, *, user, ...)`: obtener `rol = rol_de_usuario(user)` y pasarlo a **todas** las llamadas `reglas.transicion({...}, accion, rol)`. Registrar el `rol` en `_evento(...)`.
  - `router.py`: `accion(prueba_id, body, ..., user=Depends(require_staff))` ya tiene `user`; propagarlo al servicio.
  - **No cambiar** `reglas.transicion` ni su default `"ADMIN"`: el espejo depende de esa firma.
- [ ] **Step 4:** `pytest tests/test_ciclo_roles.py -q` verde; **`pytest tests/test_aud_ciclo_reglas.py -q` sin cambios** (crítico); suite `-k ciclo` verde.
- [ ] **Step 5: Commit** — `feat(ciclo): la aprobación ejerce el rol real del usuario sin romper el espejo`.

---

### Task 5: Checkpoint de las acciones de IA del ciclo (ENG-018/019)

**Files:** Modify `servicio.py` (`checkpoint_ia`); punto de integración con el interpreter del encargo. Test `tests/test_ciclo_checkpoint_ia.py`.

- [ ] **Step 1: Pruebas que fallan**

```python
def test_checkpoint_ia_entra_en_la_cadena(db):
    p = crear_prueba(db, project_id, "vnr", tributario=False, actor="a@x.ec")
    checkpoint_ia(db, p.id, modelo="claude-sonnet-4-5-20250929",
                  hash_input="abc123", confianza="media",
                  requiere_revision_humana=False, actor="ia@sistema")
    ev = eventos(db, p.id)[-1]
    assert ev.accion == "ai_checkpoint"
    assert verificar_bitacora(db, p.id)  # la cadena sigue íntegra

def test_ia_que_pide_revision_no_habilita_aprobacion(db):
    # Un checkpoint con requiere_revision_humana=True no cambia el estado ni
    # satisface por sí solo el gate de 'approve' (sigue exigiendo humano).
    ...
```

- [ ] **Step 2: Correr y ver que falla.**
- [ ] **Step 3: Implementar**:
  - `checkpoint_ia(db, prueba_id, *, modelo, hash_input, confianza, requiere_revision_humana, actor, comentario="")`: escribe un `PruebaEvento` vía `_evento(...)` con `accion="ai_checkpoint"`, `content_hash=hash_input` y el resto del payload en `comentario` (JSON compacto). NO transiciona estado.
  - Enganchar en el punto donde el encargo materializa una interpretación IA (mismo patrón y disclaimers que `ict/audit/interpreter.py`: schema Pydantic, audit trail, disclaimer, confianza, `requiere_revision_humana`). El checkpoint es la parte de **traza**; los 6 controles de IA de `CLAUDE.md` se mantienen aparte.
  - Regla de gobierno: una acción IA nunca es aprobación humana. El gate de `transicion("approve")` sigue exigiendo `conclusionReviewed`, notas resueltas, etc. — no se relaja.
- [ ] **Step 4:** `pytest tests/test_ciclo_checkpoint_ia.py -q` verde; suite `-k ciclo` verde; **suite completa** sin nuevos fallos respecto de la línea base de `CLAUDE.md`.
- [ ] **Step 5: Commit** — `feat(ciclo): checkpoint firmado de las acciones de IA en la bitácora del encargo`.

---

## Criterio de aceptación (P2-G)

- La bitácora de toda prueba verifica desde `GENESIS`; manipular una fila por SQL crudo rompe `verificar_bitacora`.
- `aud_prueba_eventos` rechaza `UPDATE`/`DELETE` por trigger.
- `approve*` ejerce el rol real; los tests espejo (`test_aud_ciclo_reglas.py`) **no cambian de resultado**.
- Cada acción de IA materializada deja un `ai_checkpoint` en la cadena y ninguna sustituye la aprobación humana.
- Sin nuevos fallos frente a la lista de tests legacy documentada en `CLAUDE.md`.

## Qué queda para el servidor

Todo este plan (migración, trigger, endpoints, pytest) se ejecuta en el servidor: aquí solo queda **escrito**. No se corrió `pytest` ni se aplicó migración en el contenedor de origen porque las dependencias (FastAPI/SQLAlchemy/DB) no corren en él.
