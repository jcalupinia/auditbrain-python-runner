"""Generación de herramientas NIIF — fichas de diseño compartidas.

La ficha describe una prueba de auditoría antes de que exista su código:
identificación, qué se le pide al cliente y qué cédulas produce
(``docs/pruebas/ESTRUCTURA_HERRAMIENTA.md``, bloques 2 y 4).

Vive en la base de datos —no en el navegador— porque el circuito que pidió
el dueño exige que quien marca la ficha como «probada» pueda ser alguien
distinto de quien la diseñó.

Aquí NO hay motor de cálculo: la ficha se diseña, se prueba, se marca
probada y se genera el encargo para que un asistente escriba la herramienta.
"""
