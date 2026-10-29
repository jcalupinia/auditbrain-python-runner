#!/usr/bin/env python3
"""Recuperación / consulta de claves de las cuentas de prueba del preview.

Solo funciona en previews (``APP_ENV=preview``) y solo opera sobre cuentas listadas
en el archivo de identidades aislado del PR. No usa variables persistentes.

Uso (dentro del contenedor backend del preview):

    # Re-emitir (clave nueva aleatoria) la cuenta de un correo:
    python scripts/recuperar_clave_preview.py correo@dominio

    # Listar correo→clave de TODAS las cuentas configuradas (para distribuir en privado):
    python scripts/recuperar_clave_preview.py --listar

La re-emisión imprime la clave nueva UNA sola vez y la guarda con permisos 600.
"""
from __future__ import annotations

import sys

from backend.app.core import preview, preview_seed
from backend.app.db.session import SessionLocal


def _listar() -> int:
    if not preview.is_preview():
        print("ERROR: solo disponible en previews.", file=sys.stderr)
        return 2
    ident = preview_seed._load_identities()
    correos = ([ident["admin"]] if ident["admin"] else []) + list(ident["operators"])
    if not correos:
        print("No hay archivo de identidades válido (sin cuentas configuradas).", file=sys.stderr)
        return 1
    print("correo\tclave (o estado)")
    for c in correos:
        f = preview_seed._secrets_dir() / preview_seed._email_slug(c)
        try:
            print(f"{c}\t{f.read_text(encoding='utf-8').strip()}")
        except OSError:
            print(f"{c}\t<sin clave; usa la recuperación por correo>")
    return 0


def _reemitir(email: str) -> int:
    db = SessionLocal()
    try:
        password = preview_seed.reissue_password(db, email)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except KeyError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except LookupError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except OSError:
        print("ERROR: no se pudo guardar la clave.", file=sys.stderr)
        return 1
    finally:
        db.close()
    print(f"Clave nueva para {email} (cópiala ahora, no se vuelve a mostrar):")
    print(password)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Uso: recuperar_clave_preview.py <correo> | --listar", file=sys.stderr)
        return 2
    if argv[1] == "--listar":
        return _listar()
    return _reemitir(argv[1].strip().lower())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
