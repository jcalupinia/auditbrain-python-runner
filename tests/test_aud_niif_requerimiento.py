"""Los mismos casos que `node lib/requirement.mjs` comprueba en el sitio.

La cobertura por ítems vive dos veces: en JavaScript dentro del sitio y en
Python dentro del portal. No hay forma de compartir el archivo, así que lo que
se comparte es la batería de casos: cada aserción de aquí es la misma que la
del bloque ejecutable al final de `lib/requirement.mjs`, con el mismo dato de
entrada y el mismo resultado esperado.

Si alguien cambia una regla en un solo lado, uno de los dos se pone rojo. Eso
es todo lo que se puede garantizar sin un repositorio común, y es mejor que
confiar en que nadie la toque.
"""
import pytest

from backend.app.aud.niif.requerimiento import (
    check_upload,
    coverage,
    gaps,
    parse_items,
    template_csv,
)

ITEMS_BASE = [
    {"text": "Mayor general", "formats": ["xlsx", "csv"], "components": ["enero", "febrero", "marzo"]},
    {"text": "Políticas contables", "formats": ["pdf", "md"]},
    {"text": "Fotos de bodega", "formats": ["jpg"], "required": False},
]


@pytest.fixture
def items():
    return parse_items(ITEMS_BASE)


def doc(item_id, component=None, state=None):
    d = {"kind": "source", "itemId": item_id}
    if component is not None:
        d["component"] = component
    if state is not None:
        d["state"] = state
    return d


# --- normalización de los ítems ---

def test_los_componentes_quedan_declarados(items):
    assert len(items[0]["components"]) == 3


def test_un_item_es_obligatorio_por_defecto(items):
    assert items[1]["required"] is True
    assert items[2]["required"] is False


def test_rechaza_un_item_repetido():
    with pytest.raises(ValueError, match="Ítem repetido"):
        parse_items([
            {"text": "Mayor general", "formats": ["csv"]},
            {"text": "mayor  general", "formats": ["csv"]},
        ])


def test_rechaza_un_formato_no_admitido():
    with pytest.raises(ValueError, match="Formato no admitido"):
        parse_items([{"text": "Mayor", "formats": ["exe"]}])


def test_exige_al_menos_un_formato():
    with pytest.raises(ValueError, match="al menos un formato"):
        parse_items([{"text": "Mayor", "formats": []}])


def test_exige_al_menos_un_item():
    with pytest.raises(ValueError, match="entre 1 y 40"):
        parse_items([])


# --- cobertura y huecos ---

def test_detecta_el_mes_faltante_y_el_item_sin_evidencia(items):
    faltantes = gaps(items, [doc("i1", "enero"), doc("i1", "marzo")])
    assert any("febrero" in g for g in faltantes)
    assert any("Políticas" in g for g in faltantes)


def test_un_item_sin_componentes_se_nombra_una_sola_vez(items):
    faltantes = gaps(items, [doc("i1", "enero"), doc("i1", "marzo")])
    assert "Políticas contables" in faltantes


def test_el_item_opcional_nunca_bloquea(items):
    faltantes = gaps(items, [doc("i1", "enero"), doc("i1", "marzo")])
    assert not any("Fotos" in g for g in faltantes)


def test_sin_huecos_cuando_esta_todo(items):
    completos = [doc("i1", "enero"), doc("i1", "marzo"), doc("i1", "febrero"), doc("i2")]
    assert gaps(items, completos) == []


def test_un_archivo_no_cubre_doce_meses(items):
    # Es el bug que el módulo entero existe para evitar: un solo mayor
    # entregado no tapa un ítem declarado por componentes.
    assert len(gaps(items, [doc("i1", "enero"), doc("i2")])) == 1


def test_la_cobertura_cuenta_recibidos_y_esperados(items):
    estado = coverage(items, [doc("i1", "enero"), doc("i1", "marzo")])
    assert estado[0]["received"] == 2
    assert estado[0]["expected"] == 3
    assert estado[0]["pending"] == ["febrero"]
    assert estado[0]["complete"] is False


# --- validación del archivo que se sube ---

def test_rechaza_un_formato_que_el_item_no_declaro(items):
    with pytest.raises(ValueError, match="XLSX, CSV"):
        check_upload(items, "i1", "enero", "mayor.pdf")


def test_rechaza_un_componente_inexistente(items):
    with pytest.raises(ValueError, match="no declarado"):
        check_upload(items, "i1", "abril", "mayor.xlsx")


def test_exige_indicar_el_componente_cuando_el_item_los_tiene(items):
    with pytest.raises(ValueError, match="por componentes"):
        check_upload(items, "i1", None, "mayor.xlsx")


def test_acepta_un_item_sin_componentes(items):
    assert check_upload(items, "i2", None, "politicas.md")["id"] == "i2"


def test_rechaza_vincular_a_un_item_que_no_existe(items):
    with pytest.raises(ValueError, match="Vincule el archivo"):
        check_upload(items, "i9", None, "cualquiera.pdf")


# --- fuentes alternativas (grupo) ---

ALTERNATIVAS = [
    {"text": "Costos de venta por ítem", "formats": ["xlsx"], "group": "Costos necesarios para vender"},
    {"text": "Estado de resultados con base de asignación", "formats": ["pdf"], "group": "Costos necesarios para vender"},
]


def test_el_grupo_sin_cubrir_reporta_un_solo_hueco_que_nombra_las_alternativas():
    alt = parse_items(ALTERNATIVAS)
    faltantes = gaps(alt, [])
    assert len(faltantes) == 1
    assert " o " in faltantes[0]


def test_una_alternativa_satisface_el_grupo():
    alt = parse_items(ALTERNATIVAS)
    assert gaps(alt, [doc("i2")]) == []


# --- plantilla generada del propio ítem ---

def test_la_plantilla_lleva_las_columnas_y_las_instrucciones():
    con_columnas = parse_items([{
        "text": "Inventario al corte", "formats": ["csv"],
        "columns": ["sku", "cantidad", "costo unitario"],
        "instructions": "Un renglón por SKU, sin totales.",
    }])
    csv = template_csv(con_columnas[0])
    assert '"sku","cantidad","costo unitario"' in csv
    assert csv.startswith("# Un renglón")


def test_sin_columnas_no_hay_plantilla():
    assert template_csv({"columns": []}) is None


# --- un documento rechazado no tapa el hueco ---

def test_un_documento_rechazado_no_cubre():
    un_item = parse_items([{"text": "Mayor", "formats": ["csv"], "components": ["enero"]}])
    assert gaps(un_item, [doc("i1", "enero")]) == []
    assert len(gaps(un_item, [doc("i1", "enero", state="rechazado")])) == 1
