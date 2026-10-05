"""Ruteo de dos niveles del agente AUDIT-IA.

Contrato:
  1. El clasificador manda una consulta simple al nivel "consulta" y una de
     análisis/juicio al nivel "razonamiento" (ante la duda, razonamiento).
  2. Cada nivel usa su proveedor+modelo (por defecto DeepSeek flash / v4-pro),
     configurable por env var.
  3. ``responder_agente`` fuerza ese proveedor+modelo a chat_complete, pero el
     modelo forzado solo aplica al proveedor preferido (el respaldo usa el suyo).
  4. Si el proveedor del nivel está caído, cae por la cadena habitual (M16).
"""
import pytest

from backend.app.chat import providers, ruteo

_ENV = ("AGENTE_PROVEEDOR_CONSULTA", "AGENTE_MODELO_CONSULTA",
        "AGENTE_PROVEEDOR_RAZONAMIENTO", "AGENTE_MODELO_RAZONAMIENTO")


@pytest.fixture
def limpio(monkeypatch):
    for k in _ENV:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


# --- 1. Clasificador --------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "Hola, buenos días",
    "¿Cuándo vence el F-104 de este mes?",
    "¿Qué casillero uso para las ventas 12%?",
    "¿Qué significa NIIF?",
    "gracias",
])
def test_consulta_simple_va_a_consulta(texto):
    assert ruteo.clasificar(texto) == ruteo.CONSULTA


@pytest.mark.parametrize("texto", [
    "Analiza si me conviene acogerme al régimen RIMPE",
    "¿Por qué mi utilidad bajó respecto al año pasado?",
    "Compara el tratamiento tributario de un leasing vs una compra",
    "¿Cómo contabilizo una baja de activo fijo con pérdida?",
    "Recomiéndame cómo optimizar el anticipo de impuesto a la renta",
])
def test_pregunta_de_juicio_va_a_razonamiento(texto):
    assert ruteo.clasificar(texto) == ruteo.RAZONAMIENTO


def test_texto_sin_tildes_tambien_se_detecta():
    # Sin acentos ("analiza" / "por que") debe seguir escalando.
    assert ruteo.clasificar("analiza mi balance por que no cuadra") == ruteo.RAZONAMIENTO


def test_texto_muy_largo_escala_a_razonamiento():
    largo = "necesito ayuda con esto " + " ".join(f"dato{i}" for i in range(70))
    assert ruteo.clasificar(largo) == ruteo.RAZONAMIENTO


def test_vacio_no_gasta_el_modelo_fuerte():
    assert ruteo.clasificar("") == ruteo.CONSULTA
    assert ruteo.clasificar("   ") == ruteo.CONSULTA


def test_nivel_de_usa_el_ultimo_turno_del_usuario():
    conv = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "¿en qué te ayudo?"},
        {"role": "user", "content": "analiza mis estados financieros"},
    ]
    assert ruteo.nivel_de(conv) == ruteo.RAZONAMIENTO


# --- 2 y 3. responder_agente fuerza proveedor+modelo por nivel --------------

def test_consulta_usa_flash_de_deepseek(limpio):
    capturado = {}

    def _fake(messages, system=None, *, temperature=None, exclude=(),
              preferir=None, modelo=None):
        capturado.update(preferir=preferir, modelo=modelo)
        return providers.LLMResponse(content="ok", model=modelo,
                                     tokens_in=None, tokens_out=None)

    limpio.setattr(providers, "chat_complete", _fake)
    limpio.setattr(ruteo, "chat_complete", _fake)

    r = ruteo.responder_agente([{"role": "user", "content": "¿cuándo vence el F-104?"}])
    assert r.nivel == ruteo.CONSULTA
    assert capturado == {"preferir": "deepseek", "modelo": "deepseek-flash"}
    assert r.modelo_pedido == "deepseek-flash"


def test_razonamiento_usa_v4_pro_de_deepseek(limpio):
    capturado = {}

    def _fake(messages, system=None, *, temperature=None, exclude=(),
              preferir=None, modelo=None):
        capturado.update(preferir=preferir, modelo=modelo)
        return providers.LLMResponse(content="ok", model=modelo,
                                     tokens_in=None, tokens_out=None)

    limpio.setattr(ruteo, "chat_complete", _fake)

    r = ruteo.responder_agente(
        [{"role": "user", "content": "analiza si me conviene el RIMPE"}]
    )
    assert r.nivel == ruteo.RAZONAMIENTO
    assert capturado == {"preferir": "deepseek", "modelo": "deepseek-v4-pro"}


def test_env_vars_sobrescriben_proveedor_y_modelo(limpio):
    limpio.setenv("AGENTE_PROVEEDOR_RAZONAMIENTO", "anthropic")
    limpio.setenv("AGENTE_MODELO_RAZONAMIENTO", "claude-sonnet-4-6")
    capturado = {}

    def _fake(messages, system=None, *, temperature=None, exclude=(),
              preferir=None, modelo=None):
        capturado.update(preferir=preferir, modelo=modelo)
        return providers.LLMResponse(content="ok", model=modelo,
                                     tokens_in=None, tokens_out=None)

    limpio.setattr(ruteo, "chat_complete", _fake)
    ruteo.responder_agente([{"role": "user", "content": "analiza mi balance"}])
    assert capturado == {"preferir": "anthropic", "modelo": "claude-sonnet-4-6"}


def test_forzar_nivel_salta_el_clasificador(limpio):
    capturado = {}

    def _fake(messages, system=None, *, temperature=None, exclude=(),
              preferir=None, modelo=None):
        capturado.update(modelo=modelo)
        return providers.LLMResponse(content="ok", model=modelo,
                                     tokens_in=None, tokens_out=None)

    limpio.setattr(ruteo, "chat_complete", _fake)
    # "hola" sería consulta, pero forzamos razonamiento.
    r = ruteo.responder_agente([{"role": "user", "content": "hola"}],
                               forzar_nivel=ruteo.RAZONAMIENTO)
    assert r.nivel == ruteo.RAZONAMIENTO
    assert capturado["modelo"] == "deepseek-v4-pro"


# --- 4. El modelo forzado NO viaja al proveedor de respaldo -----------------

def test_modelo_forzado_solo_aplica_al_proveedor_preferido(limpio):
    """Si el preferido cae, el respaldo usa su propio modelo (no el ID de DeepSeek)."""
    limpio.setattr(providers, "_providers_with_keys", lambda: ["deepseek", "gemini"])
    modelos_por_proveedor = {}

    def _call_deepseek(messages, system, temperature=None, model=None):
        modelos_por_proveedor["deepseek"] = model
        raise providers.ProviderUnavailable("deepseek caído")

    def _call_gemini(messages, system, temperature=None, model=None):
        modelos_por_proveedor["gemini"] = model
        return providers.LLMResponse(content="respaldo", model="gemini-2.5-flash-lite",
                                     tokens_in=None, tokens_out=None)

    limpio.setattr(providers, "_call_deepseek", _call_deepseek)
    limpio.setattr(providers, "_call_gemini", _call_gemini)

    r = providers.chat_complete(
        [{"role": "user", "content": "x"}],
        preferir="deepseek", modelo="deepseek-v4-pro",
    )
    assert r.content == "respaldo"
    assert modelos_por_proveedor["deepseek"] == "deepseek-v4-pro"  # forzado al preferido
    assert modelos_por_proveedor["gemini"] is None                 # respaldo usa el suyo


def test_preferir_pone_al_proveedor_a_la_cabeza(limpio):
    limpio.setattr(providers, "_providers_with_keys", lambda: ["local", "deepseek"])
    orden = []

    def _mk(nombre):
        def _call(messages, system, temperature=None, model=None):
            orden.append(nombre)
            return providers.LLMResponse(content=nombre, model=model or nombre,
                                         tokens_in=None, tokens_out=None)
        return _call

    limpio.setattr(providers, "_call_local", _mk("local"))
    limpio.setattr(providers, "_call_deepseek", _mk("deepseek"))

    providers.chat_complete([{"role": "user", "content": "x"}], preferir="deepseek")
    assert orden[0] == "deepseek"  # el preferido va primero aunque local esté antes
