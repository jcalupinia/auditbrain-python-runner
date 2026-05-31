"""TAX.PLANIFICACION_UTILIDADES — pago a cuenta sobre utilidades no distribuidas.

Backend (stateless) de la herramienta de planificación tributaria que ya vive
en el frontend (frontend/src/tax). Expone dos capacidades:

1. Extracción (ingesta): subir un Formulario 101 (PDF) o un "balance resumido"
   (plantilla .xlsx del informe de auditoría externa) y devolver los datos
   mapeados a los MISMOS esquemas ESF/ER que usa el formulario del frontend.
2. Exportación: recibir el modelo actual (datos + palancas + parámetros) y
   devolver un Excel con FÓRMULAS NATIVAS interactivas que recalculan en vivo.

No hay base de datos ni jobs: el frontend mantiene el estado y recalcula en
vivo; el backend solo parsea y arma archivos.
"""
