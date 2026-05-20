"""Capa de contexto operativo (multi-tenant) de AuditBrain.

Modelo de datos:
- Organization: tenant raíz. Todo usuario pertenece a UNA organización.
- Client: cliente externo del que la organización audita/asesora.
- Project: proyecto concreto para un cliente (con período y equipo).
- Period: ventana temporal del proyecto (Q1 2026, AF 2025, etc.).
- ProjectMember: usuarios habilitados en cada proyecto (scoping fino).
- User.organization_id: pertenencia del usuario al tenant.
- User.active_project_id: workspace activo persistido.

El bootstrap crea una organización por defecto para cualquier usuario
existente que aún no tenga `organization_id`, preservando 100% el
comportamiento legacy.
"""
