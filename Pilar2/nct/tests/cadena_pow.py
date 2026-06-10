from app.chain import cadena_pow

def test_cadena_pow_excluye_nonce_y_hash():
    bloque = {"index": 1, "previous_hash": "abc", "timestamp": "t",
              "transactions": "[]", "nonce": 5, "block_hash": "zzz"}
    cadena = cadena_pow(bloque)
    assert "nonce" not in cadena
    assert "block_hash" not in cadena

def test_cadena_pow_determinista():
    # mismo bloque (claves en distinto orden) -> misma cadena
    b1 = {"index": 1, "previous_hash": "abc", "timestamp": "t", "transactions": "[]"}
    b2 = {"transactions": "[]", "timestamp": "t", "previous_hash": "abc", "index": 1}
    assert cadena_pow(b1) == cadena_pow(b2)
