"""
Tests del fix de la Mejora 6: el lock por wallet en validar_tx() (ver validation.py) que
cierra la ventana de doble gasto concurrente (TOCTOU entre leer el saldo y encolar la tx).
La proteccion "de base" (secuencial, via calcular_saldo incluyendo el pool pendiente) ya
estaba cubierta por test_validation_saldo.py::test_doble_gasto_se_rechaza - estos tests
apuntan especificamente al caso concurrente y al comportamiento del lock en si.
"""
import threading
from app.validation import validar_tx

EMISION = {"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
           "tokens": 10, "motivo": "compra", "pelicula": "Dune",
           "timestamp": "2026-06-10T10:00:00Z"}


def test_tx_se_rechaza_si_la_wallet_ya_tiene_una_seccion_critica_en_curso(r):
    # simula lo que veria una segunda request si otra, de la MISMA wallet, ya esta a mitad
    # de validar_tx() (esto es lo que en el ataque real pasa en paralelo, sin que ninguna
    # de las dos termino de encolar todavia).
    r.set("lock:tx:Alice", "1", nx=True, ex=5)

    tx = {"type": "transferencia", "from": "Alice", "to": "Bob",
          "tokens": 1, "timestamp": "2026-06-10T11:00:00Z"}
    ok, motivo = validar_tx(tx, r)

    assert ok is False
    assert "procesándose" in motivo


def test_lock_se_libera_despues_de_procesar_y_no_bloquea_la_siguiente(r):
    validar_tx(dict(EMISION), r)
    ok, _ = validar_tx({"type": "transferencia", "from": "Alice", "to": "Bob",
                         "tokens": 1, "timestamp": "2026-06-10T11:00:00Z"}, r)
    assert ok is True
    assert r.exists("lock:tx:Alice") == 0   # no quedo trabado para la proxima tx de Alice


def test_doble_gasto_concurrente_solo_una_de_las_dos_pasa(r):
    # el "ataque deliberado": Alice tiene 10, y dispara DOS transferencias de 10 en paralelo
    # (a destinos distintos, para que no choquen con el anti-duplicado por tx_id identico) -
    # sin el lock, las dos podrian leer saldo=10 antes de que cualquiera encole la suya.
    validar_tx(dict(EMISION), r)

    resultados = []
    barrera = threading.Barrier(2)

    def intentar(destino, minuto):
        barrera.wait()  # arrancan lo mas sincronizadas posible
        tx = {"type": "transferencia", "from": "Alice", "to": destino,
              "tokens": 10, "timestamp": f"2026-06-10T11:0{minuto}:00Z"}
        ok, _ = validar_tx(tx, r)
        resultados.append(ok)

    t1 = threading.Thread(target=intentar, args=("Bob", 0))
    t2 = threading.Thread(target=intentar, args=("Carol", 1))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert resultados.count(True) == 1
    assert resultados.count(False) == 1
