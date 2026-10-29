#!/usr/bin/env python3
"""Recuperación administrativa de la clave de una cuenta de prueba del preview.

Úsalo cuando se perdió el archivo de contraseña de una cuenta de operador del
preview (el seeder solo AVISA en ese caso; no cambia la clave en el arranque).
Esta operación es EXPLÍCITA y controlada: la ejecuta quien tenga acceso al
contenedor del preview (``docker exec``), afecta SOLO a la cuenta indicada y
genera una contraseña aleatoria e independiente nueva.

Solo funciona en previews (``APP_ENV=preview``). No usa ninguna variable
persistente: no provoca restablecimientos repetidos en cada arranque.

Uso (dentro del contenedor backend del preview):

    python scripts/recuperar_clave_preview.py pr-op-01@preview.audit-ia.ec

Imprime la nueva clave UNA sola vez (compártela por canal seguro). También queda
guardada, con permisos 600, en PREVIEW_USER_SECRETS_DIR para futuras consultas.
"""
from __future__ import annotations

import sys

from backend.app.core import preview_seed
from backend.app.core.preview_users import PREVIEW_ACCOUNTS
from backend.app.db.session import SessionLocal


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Uso: python scripts/recuperar_clave_preview.py <alias>", file=sys.stderr)
        print(
            "Alias válidos: " + ", ".join(a["alias"] for a in PREVIEW_ACCOUNTS),
            file=sys.stderr,
        )
        return 2

    alias = argv[1].strip().lower()
    db = SessionLocal()
    try:
        password = preview_seed.reissue_password(db, alias)
    except RuntimeError as e:  # no es preview
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except KeyError as e:  # alias fuera de la matriz
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except LookupError as e:  # la cuenta no existe
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except OSError as e:  # no se pudo guardar el archivo
        print(f"ERROR: no se pudo guardar la clave ({e.__class__.__name__}).", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"Clave nueva para {alias} (cópiala ahora, no se vuelve a mostrar):")
    print(password)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
