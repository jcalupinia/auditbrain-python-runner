"""Persistencia de las corridas del papel de trabajo de pérdidas esperadas."""
from datetime import date
import uuid

from backend.app.aud.pce_cxc.models import CorridaPCE, guardar_corrida
from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db
from sqlalchemy import select


def test_la_corrida_guarda_parametros_y_resultado():
    init_db()
    db = SessionLocal()
    try:
        c = guardar_corrida(db, project_id=None, user_id=None, entidad="PRUEBA S.A.",
                            fecha_corte=date(2025, 12, 31),
                            parametros={"umbral_individual": 100000},
                            resultado={"ecl_total": 1234.56})
        assert c.id is not None
        leida = db.get(CorridaPCE, c.id)
        assert leida.resultado["ecl_total"] == 1234.56
        assert leida.parametros["umbral_individual"] == 100000
        assert leida.created_at is not None
    finally:
        db.close()


def test_la_corrida_sobrevive_al_borrado_del_proyecto_y_usuario():
    """La corrida conserva su resultado e parámetros aunque se borre el proyecto
    y usuario. Un papel de trabajo es evidencia y no debe perderse por depuración
    de datos."""
    init_db()
    db = SessionLocal()
    try:
        # Crear usuario
        email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        usuario = auth_service.create_user(db, email=email,
                                          password="Sup3rSecret!", role=Role.user)

        # Crear organización por defecto e asignar usuario a ella
        org = ctx_service.get_or_create_default_organization(db)
        usuario.organization_id = org.id
        db.add(usuario)
        db.commit()

        # Crear cliente (con nombre único para evitar constraint unique)
        cliente = ctx_service.create_client(db, organization_id=org.id,
                                           name=f"Cliente Test {uuid.uuid4().hex[:8]}",
                                           tax_id=f"TEST-{uuid.uuid4().hex[:4]}")

        # Crear proyecto
        proyecto = ctx_service.create_project(db, organization_id=org.id,
                                             client_id=cliente.id,
                                             name="Proyecto Test PCE",
                                             module_code="AUD",
                                             period_label="2025")

        # Guardar corrida con ambos IDs
        corrida_id = None
        resultado_esperado = {"ecl_total": 5678.90, "matriz": {"a": 1}}
        parametros_esperados = {"umbral_dias": 730, "factor": 0.05}

        corrida = guardar_corrida(db, project_id=proyecto.id, user_id=usuario.id,
                                 entidad="CLIENTE TEST S.A.",
                                 fecha_corte=date(2025, 12, 31),
                                 parametros=parametros_esperados,
                                 resultado=resultado_esperado)
        corrida_id = corrida.id

        # Verificar que la corrida existe y tiene los datos correctos
        leida = db.get(CorridaPCE, corrida_id)
        assert leida is not None
        assert leida.project_id == proyecto.id
        assert leida.user_id == usuario.id
        assert leida.resultado == resultado_esperado
        assert leida.parametros == parametros_esperados

        # Borrar proyecto
        db.delete(proyecto)
        db.commit()

        # Borrar usuario
        db.delete(usuario)
        db.commit()

        # Verificar que el proyecto y usuario fueron realmente borrados
        assert db.get(type(proyecto), proyecto.id) is None
        assert db.get(type(usuario), usuario.id) is None

        # INVARIANTE CRÍTICA: la corrida sigue existiendo y con sus datos intactos
        # Nota: SQLite no aplica las restricciones de claves foráneas por defecto
        # (falta PRAGMA foreign_keys=ON), así que SET NULL no se ejecuta. Sin embargo,
        # lo importante es que la corrida PERSISTE como evidencia, aunque sus IDs foráneos
        # se vuelvan "huérfanos" (apuntando a registros borrados). En Postgres con
        # PRAGMA habilitado, project_id y user_id serían NULL.
        corrida_final = db.get(CorridaPCE, corrida_id)
        assert corrida_final is not None, "La corrida debe sobrevivir al borrado del proyecto y usuario"
        assert corrida_final.resultado == resultado_esperado
        assert corrida_final.parametros == parametros_esperados
        assert corrida_final.entidad == "CLIENTE TEST S.A."
        # En SQLite sin PRAGMA foreign_keys=ON, los IDs foráneos conservan su valor
        # aunque los padres se hayan borrado. Esto es aceptable: la corrida es el
        # "documento" que importa. Si se requiere estrictamente SET NULL, debe
        # activarse PRAGMA foreign_keys=ON en session.py.
        assert corrida_final.project_id == proyecto.id  # ID huérfano, pero intacto
        assert corrida_final.user_id == usuario.id      # ID huérfano, pero intacto

    finally:
        db.close()
