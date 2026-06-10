from app.validation import validar_tx


def test_emision_valida_se_acepta(r):
    tx = {"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
          "tokens": 10, "motivo": "compra", "pelicula": "Dune",
          "timestamp": "2026-06-09T10:00:00Z"}
    ok, motivo = validar_tx(tx, r)
    assert ok is True


def test_tokens_negativos_se_rechaza(r):
    tx = {"type": "transferencia", "from": "Alice", "to": "Bob",
          "tokens": -5, "timestamp": "2026-06-09T10:00:00Z"}
    ok, motivo = validar_tx(tx, r)
    assert ok is False


def test_tipo_desconocido_se_rechaza(r):
    tx = {"type": "no_existe", "from": "A", "to": "B", "tokens": 5,
          "timestamp": "2026-06-09T10:00:00Z"}
    ok, motivo = validar_tx(tx, r)
    assert ok is False


def test_campo_faltante_se_rechaza(r):
    # emision sin 'pelicula'
    tx = {"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
          "tokens": 10, "motivo": "compra", "timestamp": "2026-06-09T10:00:00Z"}
    ok, motivo = validar_tx(tx, r)
    assert ok is False
