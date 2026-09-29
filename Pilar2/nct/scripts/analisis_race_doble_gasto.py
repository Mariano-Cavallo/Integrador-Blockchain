"""
Mide empíricamente el hueco de doble gasto concurrente que cierra la Mejora 6, comparando
tres escenarios con `fakeredis` (misma librería que usa la suite de tests, en memoria, no
toca ningún Redis real): sin el lock con timing normal, sin el lock ensanchando a propósito
la ventana entre "leer el saldo" y "encolar la tx" (simula la latencia real de red que hay
entre 2 requests HTTP concurrentes en producción), y con el lock aplicado.

No requiere nada corriendo (ni Docker, ni Redis, ni RabbitMQ) - anda standalone.

Uso:
    python -m scripts.analisis_race_doble_gasto

Ver el resultado de referencia y la explicación completa en
Propuesta/REPORTE_MEJORAS_6_7.md.
"""
import json
import threading
import time
import unittest.mock

import fakeredis
from app import keys
import app.validation as validation_module
from app.validation import validar_tx

EMISION = {"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
           "tokens": 10, "motivo": "compra", "pelicula": "Dune",
           "timestamp": "2026-06-10T10:00:00Z"}


def _nuevo_r():
    cliente = fakeredis.FakeStrictRedis(decode_responses=True)
    cliente.hset(keys.GENESIS, mapping={
        "type": "genesis", "previous_hash": "0" * 16, "difficulty": "00",
        "emisores_autorizados": json.dumps(["Hoyts_0xA1b2"]),
        "quorum_requerido": 1, "tokens_por_entrada": 10,
        "timestamp": "2026-01-01T00:00:00Z",
    })
    cliente.set(keys.CHAIN_HEIGHT, 0)
    cliente.set(keys.CHAIN_DIFFICULTY, "00")
    for w in ("Hoyts_0xA1b2", "Alice", "Bob", "Carol", "Dave", "Erin"):
        cliente.set(keys.pubkey(w), "test-public-key")
    return cliente


DESTINOS = ("Bob", "Carol", "Dave", "Erin")


def _intentar_doble_gasto(con_lock: bool, ensanchar_ventana: bool = False,
                          concurrentes: int = 2, delay_s: float = 0.0,
                          ventana_s: float = 0.05):
    r = _nuevo_r()
    validar_tx(dict(EMISION), r)  # Alice recibe 10

    if not con_lock:
        # simula el codigo ANTERIOR a la Mejora 6: el lock nunca bloquea a nadie
        orig_set = r.set

        def set_sin_lock(name, *args, **kwargs):
            if isinstance(name, str) and name.startswith("lock:tx:"):
                return True
            return orig_set(name, *args, **kwargs)

        r.set = set_sin_lock

    parche = None
    if ensanchar_ventana:
        # ensancha a proposito la ventana entre "leer el saldo" y "encolar la tx" - en
        # produccion esa ventana la ensancha la latencia real de red entre 2 requests
        # concurrentes; aca, sin eso, hace falta forzarla para que el scheduler llegue a
        # interrumpir justo en el medio (tecnica estandar para reproducir race conditions
        # rapidas en memoria).
        original = validation_module.calcular_saldo

        def saldo_lento(*args, **kwargs):
            saldo = original(*args, **kwargs)
            time.sleep(ventana_s)
            return saldo

        parche = unittest.mock.patch.object(validation_module, "calcular_saldo", saldo_lento)
        parche.start()

    resultados = []
    barrera = threading.Barrier(concurrentes)

    def intentar(i):
        barrera.wait()
        time.sleep(delay_s * i)  # la i-esima tx arranca i*delay_s despues de la primera
        tx = {"type": "transferencia", "from": "Alice", "to": DESTINOS[i % len(DESTINOS)],
              "tokens": 10, "timestamp": f"2026-06-10T11:0{i}:00Z"}
        ok, _ = validar_tx(tx, r)
        resultados.append(ok)

    hilos = [threading.Thread(target=intentar, args=(i,)) for i in range(concurrentes)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    if parche is not None:
        parche.stop()

    return resultados


def _tasa(n, **kwargs):
    return sum(1 for _ in range(n) if _intentar_doble_gasto(**kwargs).count(True) > 1)


def barrido_delay(n):
    """Ancho de la ventana vulnerable: el ataque solo se cuela si la 2da tx llega antes de
    que la 1ra termine de encolarse. Se varia el desfase entre las dos tx (ventana de
    lectura->encolado fija en 50 ms) y se mide la tasa de doble gasto sin y con el lock."""
    print(f"\n=== Barrido de DELAY entre las 2 tx (ventana 50 ms, {n} corridas c/u) ===")
    print(f"{'delay_ms':>9} | {'sin lock':>9} | {'con lock':>9}")
    for delay_ms in (0, 10, 25, 40, 50, 60, 100):
        sin = _tasa(n, con_lock=False, ensanchar_ventana=True, delay_s=delay_ms / 1000)
        con = _tasa(n, con_lock=True, ensanchar_ventana=True, delay_s=delay_ms / 1000)
        print(f"{delay_ms:>9} | {sin:>4}/{n:<4} | {con:>4}/{n:<4}")


def barrido_concurrentes(n):
    """Mas tx en paralelo: Alice solo tiene saldo para UNA, cualquier aceptada extra es
    doble gasto. Se reporta en cuantas corridas hubo mas de una aceptada."""
    print(f"\n=== Barrido de CONCURRENTES (ventana 50 ms, delay 0, {n} corridas c/u) ===")
    print(f"{'K':>9} | {'sin lock':>9} | {'con lock':>9}")
    for k in (2, 3, 4):
        sin = _tasa(n, con_lock=False, ensanchar_ventana=True, concurrentes=k)
        con = _tasa(n, con_lock=True, ensanchar_ventana=True, concurrentes=k)
        print(f"{k:>9} | {sin:>4}/{n:<4} | {con:>4}/{n:<4}")


def barrido_ventana(n):
    """Ancho de la ventana lectura->encolado (proxy de latencia/carga del sistema)."""
    print(f"\n=== Barrido del ANCHO de ventana (delay 0, {n} corridas c/u) ===")
    print(f"{'ventana_ms':>10} | {'sin lock':>9} | {'con lock':>9}")
    for ventana_ms in (0, 1, 5, 20, 50, 100):
        sin = _tasa(n, con_lock=False, ensanchar_ventana=True, ventana_s=ventana_ms / 1000)
        con = _tasa(n, con_lock=True, ensanchar_ventana=True, ventana_s=ventana_ms / 1000)
        print(f"{ventana_ms:>10} | {sin:>4}/{n:<4} | {con:>4}/{n:<4}")


def main():
    n = 30

    print(f"=== SIN el lock, ventana normal (fakeredis, {n} corridas) ===")
    exitoso = sum(1 for _ in range(n) if _intentar_doble_gasto(con_lock=False).count(True) > 1)
    print(f"Las DOS transferencias pasaron juntas en {exitoso}/{n} corridas "
          f"(la ventana es demasiado angosta en memoria pura para verse sola).\n")

    print(f"=== SIN el lock, ventana ensanchada a proposito ({n} corridas) ===")
    ensanchado = sum(1 for _ in range(n)
                      if _intentar_doble_gasto(con_lock=False, ensanchar_ventana=True).count(True) > 1)
    print(f"Las DOS transferencias pasaron juntas en {ensanchado}/{n} corridas "
          f"(esto es lo que puede pasar en produccion, con latencia de red real entre 2 "
          f"requests concurrentes).\n")

    print(f"=== CON el lock (Mejora 6), MISMA ventana ensanchada ({n} corridas) ===")
    fix = sum(1 for _ in range(n)
              if _intentar_doble_gasto(con_lock=True, ensanchar_ventana=True).count(True) > 1)
    print(f"Las DOS transferencias pasaron juntas en {fix}/{n} corridas "
          f"(esperado: 0 - el lock cierra la ventana aunque sea ancha).")

    barrido_delay(n)
    barrido_concurrentes(n)
    barrido_ventana(n)


if __name__ == "__main__":
    main()
