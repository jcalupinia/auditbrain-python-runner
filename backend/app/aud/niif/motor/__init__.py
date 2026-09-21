"""Motor de cálculo declarativo — copia vendorizada del sitio AuditBrain.

`audit_engine.py` es **el mismo archivo** que el sitio publica en
`public/engine/audit_engine.py` y que corre en Pyodide en el navegador del
auditor. No se edita aquí: si hay que cambiarlo, se cambia en el sitio y se
vuelve a copiar.

Por qué se copia en vez de reescribirlo: el motor ya vive en tres sitios que
tienen que dar el mismo dígito (`lib/tools/domain.mjs` en el Worker,
`audit_engine.py` en el navegador, `lib/tools/portable-engine.mjs` en el HTML
descargado). Un cuarto dialecto en el portal sería exactamente la divergencia
que ese diseño intenta evitar. Es stdlib puro (`json`, `decimal`, `datetime`),
así que se importa tal cual.

Procedimiento de sincronización:

    cp <auditbrain-site>/public/engine/audit_engine.py \
       backend/app/aud/niif/motor/audit_engine.py
    python -m pytest tests/test_aud_niif_motor.py -v

El test no compara bytes: contrasta el motor contra cuadros calculados de
forma independiente (fórmula cerrada). Si la copia quedó vieja y el
comportamiento cambió, falla; si cambió algo que no afecta el resultado, no
molesta.
"""
from .audit_engine import VERSION, calculate

__all__ = ["VERSION", "calculate"]
