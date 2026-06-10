from app.validation import validar_tx
from app.balances import calcular_saldo


def test_transferencia_sin_saldo_se_rechaza(r):
    # Alice no tiene nada todavia
    tx = {"type": "transferencia", "from": "Alice", "to": "Bob",
          "tokens": 10, "timestamp": "2026-06-09T11:00:00Z"}
    ok, motivo = validar_tx(tx, r)
    assert ok is False


def test_transferencia_con_saldo_se_acepta(r):
    # primero emitimos 10 a Alice
    validar_tx({"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
                "tokens": 10, "motivo": "compra", "pelicula": "Dune",
                "timestamp": "2026-06-09T10:00:00Z"}, r)
    # ahora Alice transfiere 4 (le alcanza)
    ok, motivo = validar_tx({"type": "transferencia", "from": "Alice",
                             "to": "Bob", "tokens": 4,
                             "timestamp": "2026-06-09T11:00:00Z"}, r)
    assert ok is True
    assert calcular_saldo("Alice", r) == 6
    assert calcular_saldo("Bob", r) == 4


def test_doble_gasto_se_rechaza(r):
    # Alice recibe 10
    validar_tx({"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
                "tokens": 10, "motivo": "compra", "pelicula": "Dune",
                "timestamp": "2026-06-09T10:00:00Z"}, r)
    # transfiere 8 (ok, queda con 2)
    validar_tx({"type": "transferencia", "from": "Alice", "to": "Bob",
                "tokens": 8, "timestamp": "2026-06-09T11:00:00Z"}, r)
    # intenta transferir otros 8 (debe fallar: solo le quedan 2)
    ok, motivo = validar_tx({"type": "transferencia", "from": "Alice",
                             "to": "Carol", "tokens": 8,
                             "timestamp": "2026-06-09T12:00:00Z"}, r)
    assert ok is False
