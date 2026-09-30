"""Motor de extracción por IA (carta de control interno / informe del año anterior
en PDF/Word → filas de la planificación). Se prueba con un cliente Anthropic falso
(sin red ni API key) y verificando que las filas extraídas pasan la validación real
del procesador."""
import io

import pytest

from backend.app.aud.niif.ciclo import extraccion_ia as ex
from backend.app.aud.niif.procesadores import planificacion_nia as m


# --------------------------------------------------------------------------- #
#  Cliente Anthropic falso                                                     #
# --------------------------------------------------------------------------- #
class _Bloque:
    def __init__(self, entrada):
        self.type = "tool_use"
        self.input = entrada


class _Respuesta:
    def __init__(self, entrada):
        self.content = [_Bloque(entrada)]


class _ClienteFalso:
    """Devuelve siempre `filas` fijas y guarda el prompt/esquema para inspección."""

    def __init__(self, filas):
        self._filas = filas
        self.ultimo = {}
        self.messages = self

    def create(self, **kwargs):
        self.ultimo = kwargs
        return _Respuesta({"filas": self._filas})


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
#  Extracción de filas (cliente falso)                                         #
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
    cli = _ClienteFalso(filas)
    out = ex.extraer_filas(m.CAMPOS["carta_control_interno"], "texto de la carta", cliente=cli)
    rows = out["rows"]
    assert out["n"] == 2
    # Numeración de filas y coerción de numéricos a entero.
    assert rows[0]["_row"] == 1 and rows[0]["probabilidad"] == 4 and isinstance(rows[0]["probabilidad"], int)
    # Los null se vuelven cadena vacía (regla: sin dato, celda vacía; nunca 0).
    assert rows[1]["impacto"] == "" and rows[1]["respuesta"] == ""
    # Las filas extraídas pasan la validación real del procesador.
    v = m.validar_filas("carta_control_interno", rows)
    assert v["ok"], v["errors"]


def test_extraer_informe_normaliza_contra_validacion():
    filas = [
        {"concepto": "Jubilación patronal", "tipo": "Salvedad",
         "detalle": "La provisión no se ajustó al cálculo actuarial.", "importe": 18500.0,
         "fuente": "Informe 2024 · Fundamento de la opinión", "enfoque": "Ampliar pruebas."},
        {"concepto": "Empresa en funcionamiento", "tipo": "Énfasis", "detalle": "Capital de trabajo negativo.",
         "importe": None, "fuente": "Nota 1", "enfoque": None},
    ]
    cli = _ClienteFalso(filas)
    out = ex.extraer_filas(m.CAMPOS["informe_anterior"], "texto del informe",
                           enums={"tipo": m.TIPOS_INFORME}, cliente=cli)
    v = m.validar_filas("informe_anterior", out["rows"])
    assert v["ok"], v["errors"]
    # El esquema forzado limita el tipo a los valores válidos.
    esquema = cli.ultimo["tools"][0]["input_schema"]
    assert "enum" in esquema["properties"]["filas"]["items"]["properties"]["tipo"]


def test_extraer_descarta_claves_desconocidas():
    filas = [{"id": "R01", "proceso": "X", "hallazgo": "Y", "inventado": "no debería pasar"}]
    out = ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t", cliente=_ClienteFalso(filas))
    assert "inventado" not in out["rows"][0]


def test_respuesta_sin_tool_use_falla():
    class _Vacio:
        def __init__(self):
            self.messages = self

        def create(self, **k):
            class R:
                content = []
            return R()

    with pytest.raises(ex.ExtraccionError):
        ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t", cliente=_Vacio())


# --------------------------------------------------------------------------- #
#  Degradación elegante                                                        #
# --------------------------------------------------------------------------- #
def test_sin_api_key_no_disponible(monkeypatch):
    monkeypatch.setattr(ex, "EXTRACCION_ENABLED", True)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ex.ExtraccionNoDisponible):
        ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t")


def test_apagada_no_disponible(monkeypatch):
    monkeypatch.setattr(ex, "EXTRACCION_ENABLED", False)
    with pytest.raises(ex.ExtraccionNoDisponible):
        ex.extraer_filas(m.CAMPOS["carta_control_interno"], "t")
