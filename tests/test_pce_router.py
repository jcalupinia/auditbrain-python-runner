"""Endpoints de la herramienta de pérdidas esperadas (AUD, require_staff)."""
import io
import json
import uuid
from datetime import date

from openpyxl import Workbook, load_workbook

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db

BASE = "/api/v1/aud/pce-cxc"


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    ws.append(["Cliente", "Documento", "Tipo", "Emisión", "Vencimiento", "Saldo"])
    for f in filas:
        ws.append(list(f))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _archivos():
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)])
    c24 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 20000.0)])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0)])
    return [("archivos", ("2023.xlsx", c23)), ("archivos", ("2024.xlsx", c24)),
            ("archivos", ("2025.xlsx", c25))]


def _token(client, role=Role.user):
    init_db()
    tag = uuid.uuid4().hex[:6]
    email, pw = f"pce-{tag}@ex.com", "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return r.json()["access_token"]


def test_sin_rol_staff_no_se_puede_calcular(client):
    # El repo solo tiene tres roles: admin, user y client (Role.staff no existe).
    # admin y user SON staff para require_staff; el único rol no-staff es
    # "client" (portal del cliente), y ese lo rechaza get_current_user en
    # defensa en profundidad antes de llegar al chequeo de rol de
    # require_staff ("client-role JWTs must NEVER pass through staff
    # dependencies"), así que la respuesta es 401, no 403. Lo que importa acá
    # es que el cálculo NO se ejecute para un usuario de portal cliente.
    token = _token(client, Role.client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (401, 403), r.text


def test_calcula_y_guarda_la_corrida(client):
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"],
                                                    "entidad": "PRUEBA S.A."})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["corrida_id"]
    assert cuerpo["ecl_total"] >= 0
    g = client.get(f"{BASE}/corridas/{cuerpo['corrida_id']}", headers={"Authorization": f"Bearer {token}"})
    assert g.status_code == 200
    assert g.json()["resultado"]["ecl_total"] == cuerpo["ecl_total"]


def test_exige_los_tres_cortes(client):
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos()[:2],
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert "tres" in r.json()["detail"].lower()


def test_rechaza_fecha_en_formato_invalido(client):
    """Una fecha en formato inválido (ej: 31/12/2023) debe retornar 400 con mensaje claro."""
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["31/12/2023", "2024-12-31", "2025-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400, f"Se esperaba 400, se obtuvo {r.status_code}: {r.text}"
    detalle = r.json()["detail"].lower()
    # El mensaje debe mencionar la fecha inválida y el formato esperado
    assert "fecha" in detalle or "formato" in detalle or "aaaa-mm-dd" in detalle, \
        f"El mensaje no explica qué está mal: {r.json()['detail']}"


def test_rechaza_archivo_mayor_al_limite_413(client, monkeypatch):
    """Un archivo que supera MAX_BYTES_POR_ARCHIVO debe retornar 413 con mensaje explicativo."""
    from backend.app.aud.pce_cxc import router

    # Parchea el límite a algo muy pequeño para la prueba (1 KB)
    limite_pequeño = 1 * 1024  # 1 KB
    monkeypatch.setattr(router, "MAX_BYTES_POR_ARCHIVO", limite_pequeño)

    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 413, f"Se esperaba 413, se obtuvo {r.status_code}: {r.text}"
    detalle = r.json()["detail"].lower()
    # El mensaje debe mencionar el límite en MB
    assert "mb" in detalle, f"El mensaje no menciona el límite en MB: {r.json()['detail']}"
    # ...y decir qué hacer cuando el archivo depurado sigue sin entrar: quien sube
    # un análisis de 130.000 filas necesita la salida, no solo la negativa.
    assert "por segmento" in detalle and "lotes" in detalle, \
        f"El mensaje no indica cómo proceder con un archivo demasiado grande: {r.json()['detail']}"


def _instrumentar_lecturas(monkeypatch) -> list[int]:
    """Registra cuántos bytes trae cada llamada a ``UploadFile.read`` del router.

    Devuelve la lista (mutada in-place) donde se van anotando los tamaños.
    """
    from starlette.datastructures import UploadFile as StarletteUploadFile

    lecturas: list[int] = []
    read_original = StarletteUploadFile.read

    async def read_instrumentado(self, size: int = -1) -> bytes:
        datos = await read_original(self, size)
        lecturas.append(len(datos))
        return datos

    monkeypatch.setattr(StarletteUploadFile, "read", read_instrumentado)
    return lecturas


def test_rechaza_archivo_grande_por_tamano_declarado_sin_leer(client, monkeypatch):
    """Camino del PRIMER filtro: con ``archivo.size`` informado (el caso normal con
    ``TestClient``, que hace lo mismo que un cliente HTTP real informando el
    tamaño de cada parte del cuerpo multipart), el router rechaza sin llamar a
    ``UploadFile.read`` ni una sola vez.
    """
    limite_pequeño = 1 * 1024  # 1 KB
    monkeypatch.setattr("backend.app.aud.pce_cxc.router.MAX_BYTES_POR_ARCHIVO", limite_pequeño)
    lecturas = _instrumentar_lecturas(monkeypatch)

    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 413, f"Se esperaba 413, se obtuvo {r.status_code}: {r.text}"
    # El filtro por `archivo.size` rechazó antes de leer: ninguna llamada a
    # `.read()` llegó a ejecutarse.
    assert lecturas == [], f"se esperaban cero lecturas (filtro por tamaño), hubo: {lecturas}"


def test_rechaza_archivo_grande_sin_tamano_declarado_con_lectura_acotada(client, monkeypatch):
    """Camino del SEGUNDO filtro (el de respaldo): cuando ``archivo.size`` no viene
    informado, el router debe rechazar igual, y hacerlo con una lectura acotada
    (nunca materializando el archivo entero en ``contenido``).

    Fuerza el escenario parcheando ``UploadFile.__init__`` para que, tal como
    haría un cliente que no informa el tamaño de la parte multipart, cada
    ``UploadFile`` que llega al router quede con ``size = None``: como
    ``UploadFile.write`` solo suma a ``self.size`` cuando no es ``None``
    (``if self.size is not None: self.size += ...``), forzarlo a ``None`` desde
    el arranque hace que se quede en ``None`` durante todo el parseo, sin que
    haga falta tocar el resto de la máquina de multipart.
    """
    from starlette.datastructures import UploadFile as StarletteUploadFile

    limite_pequeño = 1 * 1024  # 1 KB
    monkeypatch.setattr("backend.app.aud.pce_cxc.router.MAX_BYTES_POR_ARCHIVO", limite_pequeño)
    lecturas = _instrumentar_lecturas(monkeypatch)

    init_original = StarletteUploadFile.__init__

    def init_sin_tamano(self, *args, **kwargs):
        init_original(self, *args, **kwargs)
        self.size = None

    monkeypatch.setattr(StarletteUploadFile, "__init__", init_sin_tamano)

    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 413, f"Se esperaba 413, se obtuvo {r.status_code}: {r.text}"
    # El segundo filtro sí tuvo que leer (a diferencia del primero): si esto
    # queda vacío, la prueba no está ejercitando el camino de respaldo.
    assert lecturas, "no hubo ninguna lectura: la prueba no ejercitó el filtro de respaldo"
    # ...pero ninguna lectura trajo más que límite + 1 bytes de una vez: el
    # archivo (varios KB, como los otros fixtures de este módulo) nunca se
    # materializó entero en `contenido` antes del rechazo.
    assert all(n <= limite_pequeño + 1 for n in lecturas), \
        f"alguna lectura trajo más de {limite_pequeño + 1} bytes de una vez: {lecturas}"


def test_sin_rol_staff_no_puede_consultar_corrida(client):
    """Un usuario sin rol staff no puede leer una corrida con GET /corridas/{id}."""
    # Primero, crear una corrida con un staff
    token_staff = _token(client)
    r_crear = client.post(f"{BASE}/analizar", files=_archivos(),
                          data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
                          headers={"Authorization": f"Bearer {token_staff}"})
    assert r_crear.status_code == 200, r_crear.text
    corrida_id = r_crear.json()["corrida_id"]

    # Ahora intentar leer con un usuario no-staff
    token_no_staff = _token(client, Role.client)
    r_leer = client.get(f"{BASE}/corridas/{corrida_id}",
                        headers={"Authorization": f"Bearer {token_no_staff}"})
    assert r_leer.status_code in (401, 403), \
        f"Se esperaba 401 o 403 para usuario no-staff, se obtuvo {r_leer.status_code}: {r_leer.text}"


def test_descarga_el_excel_del_papel_de_trabajo(client):
    """GET /corridas/{id}/excel devuelve un .xlsx válido con las trece hojas del papel de trabajo."""
    token = _token(client)
    r_crear = client.post(f"{BASE}/analizar", files=_archivos(),
                          data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"],
                                                          "entidad": "PRUEBA S.A."})},
                          headers={"Authorization": f"Bearer {token}"})
    assert r_crear.status_code == 200, r_crear.text
    corrida_id = r_crear.json()["corrida_id"]

    r = client.get(f"{BASE}/corridas/{corrida_id}/excel", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert ".xlsx" in r.headers["content-disposition"]

    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["00-Caratula", "01-Parametros", "02-Fuentes", "03-Cohorte", "04-Tasas",
                             "05-Matriz", "06-Individual", "07-Politica", "08-Conciliacion",
                             "09-Tributario", "10-Hallazgos", "11-Pendientes", "12-Bitacora"]


def test_excel_de_corrida_inexistente_da_404(client):
    token = _token(client)
    r = client.get(f"{BASE}/corridas/999999/excel", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_sin_rol_staff_no_puede_descargar_el_excel(client):
    """Un usuario de portal cliente no puede bajar el papel de trabajo interno."""
    token_staff = _token(client)
    r_crear = client.post(f"{BASE}/analizar", files=_archivos(),
                          data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
                          headers={"Authorization": f"Bearer {token_staff}"})
    assert r_crear.status_code == 200, r_crear.text
    corrida_id = r_crear.json()["corrida_id"]

    token_no_staff = _token(client, Role.client)
    r = client.get(f"{BASE}/corridas/{corrida_id}/excel", headers={"Authorization": f"Bearer {token_no_staff}"})
    assert r.status_code in (401, 403), \
        f"Se esperaba 401 o 403 para usuario no-staff, se obtuvo {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# I9 - Aislamiento entre organizaciones
# ---------------------------------------------------------------------------

def _organizacion_con_proyecto(client, role=Role.user):
    """Crea una organizacion propia con un operador y un proyecto.

    Devuelve (token, project_id). `ensure_user_has_organization` engancharia a
    todos a la organizacion por defecto, asi que aqui se crea una organizacion
    explicita por cada tenant para poder probar el aislamiento.
    """
    from backend.app.context import service as ctx_service
    from backend.app.context.models import Organization

    init_db()
    tag = uuid.uuid4().hex[:6]
    email, pw = f"pce-{tag}@ex.com", "Sup3rSecret!"
    db = SessionLocal()
    try:
        org = Organization(name=f"Org {tag}", slug=f"org-{tag}")
        db.add(org)
        db.commit()
        db.refresh(org)
        usuario = auth_service.create_user(db, email=email, password=pw, role=role)
        usuario.organization_id = org.id
        db.add(usuario)
        db.commit()
        cliente = ctx_service.create_client(db, organization_id=org.id, name=f"C-{tag}")
        proyecto = ctx_service.create_project(db, organization_id=org.id, client_id=cliente.id,
                                              name=f"P-{tag}", module_code="AUD")
        project_id, org_id = proyecto.id, org.id
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return r.json()["access_token"], project_id, org_id


def _operador_en_la_organizacion(client, organization_id, role=Role.user):
    """Segundo operador dentro de una organizacion ya existente."""
    tag = uuid.uuid4().hex[:6]
    email, pw = f"pce-{tag}@ex.com", "Sup3rSecret!"
    db = SessionLocal()
    try:
        usuario = auth_service.create_user(db, email=email, password=pw, role=role)
        usuario.organization_id = organization_id
        db.add(usuario)
        db.commit()
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return r.json()["access_token"]


def _crear_corrida(client, token, project_id=None):
    params = {"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"], "entidad": "PRUEBA S.A."}
    if project_id is not None:
        params["project_id"] = project_id
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps(params)},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()["corrida_id"]


def test_una_corrida_de_otra_organizacion_no_se_puede_leer(client):
    """Iterando ids, un operador de la organizacion A obtenia entidad, matriz
    completa, hallazgos y tasas de los clientes de la organizacion B."""
    token_a, proyecto_a, _org_a = _organizacion_con_proyecto(client)
    corrida_id = _crear_corrida(client, token_a, proyecto_a)

    token_b, _proyecto_b, _org_b = _organizacion_con_proyecto(client)
    r = client.get(f"{BASE}/corridas/{corrida_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 403, f"se esperaba 403, se obtuvo {r.status_code}: {r.text}"


def test_el_excel_de_otra_organizacion_no_se_puede_descargar(client):
    token_a, proyecto_a, _org_a = _organizacion_con_proyecto(client)
    corrida_id = _crear_corrida(client, token_a, proyecto_a)

    token_b, _proyecto_b, _org_b = _organizacion_con_proyecto(client)
    r = client.get(f"{BASE}/corridas/{corrida_id}/excel",
                   headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 403, f"se esperaba 403, se obtuvo {r.status_code}: {r.text}"


def test_la_corrida_propia_se_sigue_leyendo_y_descargando(client):
    token_a, proyecto_a, org_a = _organizacion_con_proyecto(client)
    corrida_id = _crear_corrida(client, token_a, proyecto_a)

    r = client.get(f"{BASE}/corridas/{corrida_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200, r.text
    r = client.get(f"{BASE}/corridas/{corrida_id}/excel",
                   headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200, r.text

    # Y un companero de la misma organizacion tambien: el papel de trabajo es de
    # la firma, no del operador que apreto el boton.
    token_companero = _operador_en_la_organizacion(client, org_a)
    r = client.get(f"{BASE}/corridas/{corrida_id}",
                   headers={"Authorization": f"Bearer {token_companero}"})
    assert r.status_code == 200, r.text


def test_no_se_guarda_una_corrida_en_un_proyecto_ajeno(client):
    """`project_id` se guardaba tal como venia en el cuerpo, sin validar que
    existiera ni que el usuario tuviera acceso."""
    _token_a, proyecto_a, _org_a = _organizacion_con_proyecto(client)
    token_b, _proyecto_b, _org_b = _organizacion_con_proyecto(client)

    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({
                        "fechas": ["2023-12-31", "2024-12-31", "2025-12-31"],
                        "project_id": proyecto_a})},
                    headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 403, f"se esperaba 403, se obtuvo {r.status_code}: {r.text}"


def test_un_proyecto_inexistente_no_se_guarda(client):
    token, _proyecto, _org = _organizacion_con_proyecto(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({
                        "fechas": ["2023-12-31", "2024-12-31", "2025-12-31"],
                        "project_id": 999999})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403, f"se esperaba 403, se obtuvo {r.status_code}: {r.text}"


def test_un_project_id_no_numerico_es_error_de_entrada(client):
    token, _proyecto, _org = _organizacion_con_proyecto(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({
                        "fechas": ["2023-12-31", "2024-12-31", "2025-12-31"],
                        "project_id": "el de siempre"})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400, f"se esperaba 400, se obtuvo {r.status_code}: {r.text}"
    assert "project_id" in r.json()["detail"]


def test_una_corrida_sin_proyecto_la_ve_la_organizacion_de_quien_la_creo(client):
    """Regla para las corridas sin proyecto asociado: no hay proyecto que acote
    el alcance, asi que las ve la organizacion de quien la creo, y nadie mas."""
    token_a, _proyecto_a, org_a = _organizacion_con_proyecto(client)
    corrida_id = _crear_corrida(client, token_a)  # sin project_id

    # El autor la ve.
    r = client.get(f"{BASE}/corridas/{corrida_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200, r.text

    # Un companero de su organizacion tambien.
    token_companero = _operador_en_la_organizacion(client, org_a)
    r = client.get(f"{BASE}/corridas/{corrida_id}",
                   headers={"Authorization": f"Bearer {token_companero}"})
    assert r.status_code == 200, r.text

    # Un operador de otra organizacion no.
    token_b, _proyecto_b, _org_b = _organizacion_con_proyecto(client)
    r = client.get(f"{BASE}/corridas/{corrida_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 403, f"se esperaba 403, se obtuvo {r.status_code}: {r.text}"
    r = client.get(f"{BASE}/corridas/{corrida_id}/excel",
                   headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 403, f"se esperaba 403, se obtuvo {r.status_code}: {r.text}"


def test_una_corrida_inexistente_sigue_dando_404(client):
    token, _proyecto, _org = _organizacion_con_proyecto(client)
    r = client.get(f"{BASE}/corridas/999999", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# M2 - Un parametro mal formado responde 400, nunca 500
# ---------------------------------------------------------------------------

def test_un_factor_prospectivo_mal_formado_responde_400_y_no_500(client):
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({
                        "fechas": ["2023-12-31", "2024-12-31", "2025-12-31"],
                        "factor_prospectivo": ["1.10"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400, f"se esperaba 400, se obtuvo {r.status_code}: {r.text}"
    assert "factor_prospectivo" in r.json()["detail"]
