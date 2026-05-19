"""Capa cognitiva (chat multi-agente) de AuditBrain.

Persistencia de conversaciones/mensajes en Postgres y cliente LLM
server-side (Anthropic Claude por defecto; OpenAI como fallback). Las
claves de proveedor NUNCA llegan al navegador.
"""
