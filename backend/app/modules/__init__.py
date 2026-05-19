"""Registry de módulos sectoriales de AuditBrain (Fase 2 · M3).

Define el catálogo de módulos del Command Center con su identidad
cognitiva (system prompt especializado), descripción ejecutiva y
sugerencias de uso. El registry es estático (código), no de tenant:
todos los clientes ven el mismo catálogo. La asignación de módulos a
proyectos vive en la tabla ``projects.module_code``.
"""
