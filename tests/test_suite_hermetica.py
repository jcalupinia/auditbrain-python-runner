"""La suite NUNCA debe correr contra la base de desarrollo.

Regresión de un defecto real (2026-08-06): ``backend/app/db/session.py``
resuelve ``DATABASE_URL`` con default ``sqlite:///./auditbrain.db``, y los
tests no lo sobreescribían. Consecuencias observadas en la máquina del
desarrollador:

- ``pytest`` escribía en la MISMA base que usa ``uvicorn app:app`` en local:
  1.957 clientes y ~700 usuarios basura acumulados.
- 6 tests fallaban de forma permanente a partir de la segunda corrida, porque
  insertan filas con nombre fijo ("ACME Corp", "Cliente Demo", "X", "CB",
  "Cliente A") contra un índice único ``(organization_id, name)``, y porque el
  listado de usuarios reventaba al serializar correos inválidos que quedaron
  guardados de corridas viejas (``admin@local.test``).
- En CI no se veía: el checkout es limpio, la base nace vacía en cada corrida.

Estos tests fijan el contrato: la sesión de pytest usa una base propia.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_DESARROLLO = REPO_ROOT / "auditbrain.db"


def _ruta_sqlite(url: str) -> Path | None:
    """Ruta en disco de una URL SQLite, o ``None`` si no es SQLite."""
    prefijo = "sqlite:///"
    if not url.startswith(prefijo):
        return None
    return Path(url[len(prefijo):]).resolve()


def test_la_suite_no_usa_la_base_de_desarrollo():
    from backend.app.db.session import DATABASE_URL

    ruta = _ruta_sqlite(DATABASE_URL)
    if ruta is None:
        return  # Postgres explícito (TEST_DATABASE_URL): fuera de este contrato.

    assert ruta.name != BASE_DESARROLLO.name, (
        f"pytest está escribiendo en {ruta}, que es la base de desarrollo. "
        "conftest.py debe apuntar DATABASE_URL a una base de tests propia."
    )
    assert ruta != BASE_DESARROLLO


def test_database_url_del_entorno_coincide_con_la_del_engine():
    """El override va en ``os.environ``, no sólo en el módulo ya importado.

    Cualquier módulo que vuelva a leer ``DATABASE_URL`` (o un subproceso)
    tiene que ver la misma base que el engine en uso; si no, la mitad de la
    suite hablaría con una base y la otra mitad con otra.
    """
    from backend.app.db.session import DATABASE_URL

    assert os.environ.get("DATABASE_URL", "").strip() == DATABASE_URL
