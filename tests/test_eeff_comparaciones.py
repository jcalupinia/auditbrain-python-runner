from backend.app.tax.planificacion_utilidades.comparaciones import build_comparaciones


def test_esf_encadenado():
    labels = ["may-26", "2025", "2024", "2023"]
    tipos = ["parcial", "anual", "anual", "anual"]
    pares = build_comparaciones(labels, tipos, "esf")
    assert pares == [("may-26", "2025"), ("2025", "2024"), ("2024", "2023")]


def test_eri_parcial_y_anual():
    labels = ["may-26", "may-25", "2025", "2024", "2023"]
    tipos = ["parcial", "parcial", "anual", "anual", "anual"]
    pares = build_comparaciones(labels, tipos, "eri")
    # parcial vs parcial, y anuales encadenados; nunca 5m vs 12m
    assert ("may-26", "may-25") in pares
    assert ("2025", "2024") in pares and ("2024", "2023") in pares
    assert ("may-26", "2025") not in pares  # jamás cruza parcial/anual
