import json
import pytest
import fakeredis
from app import keys

@pytest.fixture(autouse=True)
def no_rabbitmq(monkeypatch):
    # en tests, publicar_tarea no hace nada (no toca RabbitMQ)
    monkeypatch.setattr("app.chain.publicar_tarea", lambda task: None)


@pytest.fixture
def r():
    cliente = fakeredis.FakeStrictRedis(decode_responses=True)
    # sembrar genesis minimo (como seed_genesis pero en el fake)
    cliente.hset(keys.GENESIS, mapping={
        "type": "genesis",
        "previous_hash": "0" * 16,
        "difficulty": "00",
        "emisores_autorizados": json.dumps(["Hoyts_0xA1b2"]),
        "quorum_requerido": 1,
        "tokens_por_entrada": 10,
        "timestamp": "2026-01-01T00:00:00Z",
    })
    cliente.set(keys.CHAIN_HEIGHT, 0)
    # dificultad movil (Mejora 1): key propia, separada del genesis (ver keys.py) - arranca
    # igual que genesis.difficulty, como hace seed_genesis.py en real.
    cliente.set(keys.CHAIN_DIFFICULTY, "00")
    # registrar las wallets que usan los tests (validar_tx exige que el destinatario
    # este registrado: r.exists(keys.pubkey(wallet))). El cine emisor tambien.
    for w in ("Hoyts_0xA1b2", "Alice", "Bob", "Carol"):
        cliente.set(keys.pubkey(w), "test-public-key")
    return cliente
