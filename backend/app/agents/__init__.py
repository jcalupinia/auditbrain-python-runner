"""Agentes especializados (Fase 2 · M4).

Catálogo estático en código (por módulo) + persistencia de ejecuciones
en Postgres. Async via FastAPI BackgroundTasks (sin worker externo en
esta fase; basta para runs de 5-60s). Cuando se necesite ejecución
distribuida con resiliencia a restarts, upgradear a Redis+RQ/Arq.
"""
