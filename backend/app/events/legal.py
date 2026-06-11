"""Textos legales reutilizables del módulo de eventos (LOPDP Ecuador)."""

from __future__ import annotations


def data_protection_text(contacto: str) -> str:
    """Aviso informativo de protección de datos (sin checkbox de consentimiento)."""
    return (
        "Audit Consulting Group trata tus datos (nombre, correo, teléfono, "
        "identificación, empresa) para gestionar tu inscripción y enviarte "
        "información de la charla, conforme a la Ley Orgánica de Protección de "
        "Datos Personales del Ecuador. Podés ejercer tus derechos de acceso, "
        f"rectificación y eliminación escribiendo a {contacto}."
    )
