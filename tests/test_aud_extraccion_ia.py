"""Motor de extracción por IA (carta de control interno / informe del año anterior
en PDF/Word → filas de la planificación). Se prueba con una función de chat falsa
(sin red ni proveedor real) y verificando que las filas extraídas pasan la
validación real del procesador. El motor usa el cliente compartido de proveedores,
que pone el servidor de IA local primero."""
import io
import json

import pytest

from backend.app.aud.niif.ciclo import extraccion_ia as ex
from backend.app.aud.niif.procesadores import planificacion_nia as m


# --------------------------------------------------------------------------- #
#  Función de chat falsa (imita providers.chat_complete)                        #
# --------------------------------------------------------------------------- #
class _Resp:
    def __init__(self, content, model="modelo-falso"):
        self.content = content
        self.model = model
        self.tokens_in = None
        self.tokens_out = None


class _ChatFalso:
    """Devuelve siempre el JSON dado y guarda el prompt para inspección."""

    def __init__(self, filas=None, content=None):
        self._content = content if content is not None else json.dumps({"filas": filas or []})
        self.ultimo = {}

    def __call__(self, messages, system=None):
        self.ultimo = {"messages": messages, "system": system}
        return _Resp(self._content)


# --------------------------------------------------------------------------- #
#  Texto del documento                                                         #
# --------------------------------------------------------------------------- #
def test_texto_docx_incluye_parrafos_y_tablas():
    docx = pytest.importorskip("docx")
    doc = docx.Document()
    doc.add_paragraph("Carta de control interno 2024")
    tabla = doc.add_table(rows=2, cols=3)
    tabla.rows[0].cells[0].text = "Código"
    tabla.rows[0].cells[1].text = "Hallazgo"
    tabla.rows[0].cells[2].text = "Impacto"
    tabla.rows[1].cells[0].text = "R01"
    tabla.rows[1].cells[1].text = "No hay tomas físicas"
    tabla.rows[1].cells[2].text = "4"
    buf = io.BytesIO()
    doc.save(buf)
    texto = ex.texto_de_documento("carta.docx", buf.getvalue())
    assert "Carta de control interno 2024" in texto
    assert "R01 | No hay tomas físicas | 4" in texto


def test_texto_formato_no_soportado():
    with pytest.raises(ex.ExtraccionError):
        ex.texto_de_documento("archivo.xlsx", b"cualquier cosa")


def test_texto_vacio_falla():
    with pytest.raises(ex.ExtraccionError):
        ex.texto_de_documento("nota.txt", b"   \n  ")


def test_doc_antiguo_avisa_convertir():
    with pytest.raises(ex.ExtraccionError, match="docx"):
        ex.texto_de_documento("carta.doc", b"algo")


# --------------------------------------------------------------------------- #
#  Extracción de filas (chat falso)                                            #
# --------------------------------------------------------------------------- #
def test_extraer_carta_produce_filas_validas():
    filas = [
        {"id": "R01", "proceso": "Inventarios", "hallazgo": "No se realizan tomas físicas periódicas.",
         "aseveraciones": "Existencia", "probabilidad": 4.0, "impacto": 4.0, "control": 2.0,
         "respuesta": "Observar la toma física al cierre.", "probar_control": "No"},
        {"id": "R02", "proceso": "Tesorería", "hallazgo": "Conciliaciones bancarias sin revisar.",
         "aseveraciones": None, "probabilidad": 3.0, "impacto": None, "control": None,
         "respuesta": None, "probar_control": None},
    ]
    out = ex.extraer_filas(m.CAMPOS["carta_control_interno"], "texto de la carta", chat=_ChatFalso(filas))
    rows = out["rows"]
    assert out["n"] == 2 and out["modelo"] == "modelo-falso"
    # Numeración de filas y coerción de numéricos a entero.
    assert rows[0]["_row"] == 1 and rows[0]["probabilidad"] == 4 and isinstance(rows[0]["probabilidad"], int)
    # Los null se vuelven cadena vacía (regla: sin dato, celda vacía; nunca 0).
    assert rows[1]["impacto"] == "" and rows[1]["respuesta"] == ""
    # Las filas extraídas pasan la validación real del procesador.
    v = m.validar_filas("carta_control_interno", rows)
    assert v["ok"], v["errors"]


def test_extraer_informe_incluye_enums_en_el_prompt():
    filas = [
        {"concepto": "Jubilación patronal", "tipo": "Salvedad",
         "detalle": "La provisión no se ajustó al cálculo actuarial.", "importe": 18500.0,
         "fuente": "Informe 2024 · Fundamento de la opinión", "enfoque": "Ampliar pruebas."},
        {"concepto": "Empresa en funcionamiento", "tipo": "Énfasis", "detalle": "Capital de trabajo negativo.",
         "importe": None, "fuente": "Nota 1", "enfoque": None},
    ]
    chat = _ChatFalso(filas)
    out = ex.extraer_filas(m.CAMPOS["informe_anterior"], "texto del informe",
                           enums={"tipo": m.TIPOS_INFORME}, chat=chat)
    v = m.validar_filas("informe_anterior", out["rows"])
    assert v["ok"], v["errors"]
    # El prompt le pasa al modelo los valores permitidos del tipo.
    prompt = chat.ultimo["messages"][0]["content"]
    assert "Salvedad" in prompt and "Identificación" in prompt


def test_extraer_notas_produce_filas_validas():
    filas = [
        {"nota": "3", "titulo": "Efectivo y equivalentes de efectivo", "codigos": "1101", "saldo_auditado": 176900.0},
        {"nota": "4", "titulo": "Cuentas por cobrar comerciales", "codigos": "1103, 1106", "saldo_auditado": 656500.0},
    ]
    out = ex.extraer_filas(m.CAMPOS["notas_estados_financieros"], "texto de las notas", chat=_ChatFalso(filas))
    v = m.validar_filas("notas_estados_financieros", out["rows"])
    assert v["ok"], v["errors"]
    assert out["rows"][0]["nota"] == "3"


def test_extraer_descarta_claves_desconocidas():
    filas = [{"id": "R01", "proceso": "X", "hallazgo": "Y", "inventado": "no debería pasar"}]
    out = ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t", chat=_ChatFalso(filas))
    assert "inventado" not in out["rows"][0]


def test_json_con_cercas_de_codigo_se_parsea():
    contenido = 'Claro, aquí está:\n```json\n{"filas": [{"id": "R09", "proceso": "P", "hallazgo": "H"}]}\n```'
    out = ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t", chat=_ChatFalso(content=contenido))
    assert out["rows"][0]["id"] == "R09"


def test_respuesta_no_json_falla():
    with pytest.raises(ex.ExtraccionError):
        ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t", chat=_ChatFalso(content="no soy json"))


# --------------------------------------------------------------------------- #
#  Rescate de JSON mal formado (modelo local)                                  #
# --------------------------------------------------------------------------- #
def test_salvar_filas_con_coma_faltante_entre_objetos():
    """El error real del cliente: «Expecting ',' delimiter». El modelo olvidó la
    coma entre dos filas; se deben rescatar AMBAS en vez de perder todo."""
    malo = '{"filas": [{"id": "R01", "hallazgo": "x"} {"id": "R02", "hallazgo": "y"}]}'
    import json as _json
    with pytest.raises(_json.JSONDecodeError):
        _json.loads(malo)  # confirma que es el caso que rompía
    filas = ex._salvar_filas(malo)
    assert [f["id"] for f in filas] == ["R01", "R02"]


def test_salvar_filas_con_json_truncado():
    """Salida cortada a mitad de la última fila: se rescatan las completas y se
    descarta solo la incompleta."""
    truncado = '{"filas": [{"id": "R01", "hallazgo": "ok"}, {"id": "R02", "hallazgo": "a medi'
    filas = ex._salvar_filas(truncado)
    assert [f["id"] for f in filas] == ["R01"]


def test_salvar_filas_respeta_llaves_dentro_de_strings():
    """Una llave '}' dentro del texto de un campo no debe cortar el objeto."""
    con_llave = '{"filas": [{"id": "R01", "hallazgo": "usa {llaves} en el texto"}]}'
    filas = ex._salvar_filas(con_llave)
    assert filas == [{"id": "R01", "hallazgo": "usa {llaves} en el texto"}]


def test_extraer_rescata_filas_de_json_con_coma_faltante():
    """De punta a punta: el chat devuelve JSON mal formado y la extracción
    recupera las filas válidas y las valida contra el procesador."""
    contenido = (
        '{"filas": ['
        '{"id": "R01", "proceso": "Inventarios", "hallazgo": "Sin tomas físicas."} '  # ← sin coma
        '{"id": "R02", "proceso": "Tesorería", "hallazgo": "Conciliaciones sin revisar."}'
        ']}'
    )
    out = ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t", chat=_ChatFalso(content=contenido))
    assert out["n"] == 2
    assert [r["id"] for r in out["rows"]] == ["R01", "R02"]
    v = m.validar_filas("carta_control_interno", out["rows"])
    assert v["ok"], v["errors"]


def test_json_irrescatable_sigue_fallando():
    """Si no hay ninguna fila rescatable, la extracción falla como antes."""
    with pytest.raises(ex.ExtraccionError):
        ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t",
                         chat=_ChatFalso(content='{"filas": [esto no es json]}'))


# --------------------------------------------------------------------------- #
#  Degradación elegante                                                        #
# --------------------------------------------------------------------------- #
def test_sin_proveedor_no_disponible(monkeypatch):
    from backend.app.chat import providers

    monkeypatch.setattr(ex, "EXTRACCION_ENABLED", True)
    monkeypatch.setattr(providers, "available_provider", lambda: None)
    with pytest.raises(ex.ExtraccionNoDisponible):
        ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t")


def test_con_proveedor_local_usa_la_cadena(monkeypatch):
    """Con un proveedor disponible, el motor usa el helper afinado de la cadena
    (``completar_para_extraccion``: streaming + temperature=0, local primero)."""
    from backend.app.chat import providers

    monkeypatch.setattr(ex, "EXTRACCION_ENABLED", True)
    monkeypatch.setattr(providers, "available_provider", lambda: "local")
    llamado = {}

    def fake_chat(messages, system=None):
        llamado["ok"] = True
        return _Resp(json.dumps({"filas": [{"id": "R01", "proceso": "P", "hallazgo": "H"}]}))

    monkeypatch.setattr(providers, "completar_para_extraccion", fake_chat)
    out = ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t")
    assert llamado.get("ok") and out["rows"][0]["id"] == "R01"


def test_apagada_no_disponible(monkeypatch):
    monkeypatch.setattr(ex, "EXTRACCION_ENABLED", False)
    with pytest.raises(ex.ExtraccionNoDisponible):
        ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t")
