"""
Experimento de doble gasto (Mejora 6): dispara K transferencias concurrentes que gastan el
mismo saldo, contra un NCT en funcionamiento, N veces, y reporta en cuantas corridas se
produjo doble gasto (tasa de exito del ataque). Guarda los datos crudos de cada corrida.

Doble gasto = el total aceptado supera el saldo con el que se financio la wallet
(aceptadas * monto > fondos).

Variaciones controladas (para medir el ancho de la ventana vulnerable):
    --concurrentes K   cantidad de transferencias disparadas en paralelo (default 2)
    --delay-ms D       espera entre el lanzamiento de una transferencia y la siguiente
                       (default 0 = arrancan sincronizadas con una barrera)
    --monto M          tokens por transferencia (default 10)
    --fondos F         saldo con el que se financia la wallet (default 10)
    --corridas N       repeticiones del mismo escenario (default 1)

Salida cruda (--out DIR): un JSON por corrida con los requests, las respuestas HTTP con
tiempos, el saldo final, el pool y los bloques que contienen las tx de esa wallet, mas un
resumen.csv con una fila por corrida.

Uso:
    python -m scripts.demo_doble_gasto --url http://localhost:8888
    python -m scripts.demo_doble_gasto --url https://poptoken.34.122.53.67.nip.io \
        --corridas 30 --delay-ms 0 --out ../../Propuesta/evidencia/doble_gasto/delay_0ms

Requiere un emisor autorizado para financiar la wallet de prueba - ver el docstring de
load_test.py (mismo mecanismo: EMISOR_WALLET / EMISOR_PRIVATE_KEY_PEM, o reclama un emisor
libre del genesis si la cadena es fresca).

OJO: contra produccion, cada corrida agrega 1 emision + las transferencias aceptadas a la
cadena real. Usar tandas acotadas.
"""
import argparse
import csv
import json
import pathlib
import threading
import time

from scripts.load_test import _generar_wallet, _registrar, _login, _post, _obtener_emisor


def _ahora():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_json(url, path, token=None):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url + path)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return None, {}


def _txs_de_la_wallet(wallet, txs):
    return [tx for tx in txs if tx.get("from") == wallet or tx.get("to") == wallet]


def _estado_final(url, wallet, token, esperar_sello):
    """Saldo final, tx en el pool y bloques sellados que contienen tx de la wallet."""
    _, saldo = _get_json(url, f"/balance/{wallet}", token)
    _, pool = _get_json(url, "/pool")
    en_pool = _txs_de_la_wallet(wallet, pool.get("pending", []))

    fin = time.time() + esperar_sello
    while True:
        _, chain = _get_json(url, "/chain")
        sellados = [
            {"index": b.get("index"), "block_hash": b.get("block_hash"),
             "transactions": _txs_de_la_wallet(wallet, b.get("transactions", []))}
            for b in chain.get("blocks", [])
            if _txs_de_la_wallet(wallet, b.get("transactions", []))
        ]
        if sellados or time.time() >= fin:
            break
        time.sleep(3)
    return {"saldo_final": saldo.get("saldo"), "tx_en_pool": en_pool,
            "bloques_con_tx_de_la_wallet": sellados,
            "altura_cadena": chain.get("height")}


def _correr_una(args, corrida, emisor_wallet, emisor_token, destinos):
    sufijo = f"{int(time.time())}_{corrida}"
    wallet = f"demo_doble_gasto_{sufijo}"
    priv, pub_pem = _generar_wallet()
    _registrar(args.url, wallet, pub_pem)
    token = _login(args.url, wallet, priv)
    if not token:
        print(f"[demo] corrida {corrida}: no se pudo autenticar la wallet, salteo.")
        return None

    emision = {
        "type": "emision", "from": emisor_wallet, "to": wallet, "tokens": args.fondos,
        "motivo": "demo_doble_gasto", "pelicula": "N/A", "timestamp": _ahora(),
    }
    status_em, body_em = _post(args.url, "/tx", emision, token=emisor_token)
    if status_em != 200:
        print(f"[demo] corrida {corrida}: la emision de fondos fue rechazada "
              f"({status_em} {body_em}), salteo.")
        return None

    k = args.concurrentes
    barrera = threading.Barrier(k) if args.delay_ms == 0 else None
    resultados = [None] * k
    t0 = time.time()

    def atacar(i):
        tx = {"type": "transferencia", "from": wallet, "to": destinos[i % len(destinos)],
              "tokens": args.monto, "timestamp": _ahora()}
        if barrera:
            barrera.wait()
        t_envio = time.time() - t0
        try:
            status, body = _post(args.url, "/tx", tx, token=token)
        except Exception as e:  # error de red: se registra, no cuenta como aceptada
            status, body = None, {"error": repr(e)}
        resultados[i] = {"request": tx, "status": status, "response": body,
                         "t_envio_s": round(t_envio, 4),
                         "t_respuesta_s": round(time.time() - t0, 4)}

    hilos = []
    for i in range(k):
        h = threading.Thread(target=atacar, args=(i,))
        hilos.append(h)
        h.start()
        if args.delay_ms and i < k - 1:
            time.sleep(args.delay_ms / 1000)
    for h in hilos:
        h.join()

    aceptadas = sum(1 for r in resultados if r["status"] == 200)
    doble_gasto = aceptadas * args.monto > args.fondos
    estado = _estado_final(args.url, wallet, token, args.esperar_sello)

    return {
        "corrida": corrida, "wallet": wallet, "fondos": args.fondos, "monto": args.monto,
        "concurrentes": k, "delay_ms": args.delay_ms,
        "emision": {"request": emision, "status": status_em, "response": body_em},
        "transferencias": resultados, "aceptadas": aceptadas, "doble_gasto": doble_gasto,
        **estado,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8888")
    ap.add_argument("--corridas", type=int, default=1)
    ap.add_argument("--concurrentes", type=int, default=2)
    ap.add_argument("--delay-ms", type=int, default=0)
    ap.add_argument("--monto", type=int, default=10)
    ap.add_argument("--fondos", type=int, default=10)
    ap.add_argument("--esperar-sello", type=int, default=0,
                    help="segundos a esperar que las tx aceptadas aparezcan en un bloque")
    ap.add_argument("--out", default=None, help="directorio donde guardar los datos crudos")
    args = ap.parse_args()

    emisor_wallet, emisor_priv = _obtener_emisor(args.url)
    if not emisor_wallet:
        return
    emisor_token = _login(args.url, emisor_wallet, emisor_priv)
    if not emisor_token:
        print("[demo] no se pudo autenticar el emisor, abortando.")
        return

    # destinos distintos por transferencia, para que los tx_id no colisionen con el
    # anti-duplicado (si fueran la misma tx se rechazaria por duplicada antes del saldo).
    # Se registran una sola vez y se reusan entre corridas (la wallet origen si es nueva).
    sufijo = int(time.time())
    destinos = []
    for i in range(args.concurrentes):
        nombre = f"demo_doble_gasto_dst_{sufijo}_{i}"
        _, pub_d = _generar_wallet()
        _registrar(args.url, nombre, pub_d)
        destinos.append(nombre)

    out = pathlib.Path(args.out) if args.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)

    corridas = []
    for n in range(1, args.corridas + 1):
        c = _correr_una(args, n, emisor_wallet, emisor_token, destinos)
        if c is None:
            continue
        corridas.append(c)
        detalle = ", ".join(f"{r['status']}" for r in c["transferencias"])
        print(f"[demo] corrida {n}/{args.corridas}: {c['aceptadas']}/{args.concurrentes} "
              f"aceptadas ({detalle}) saldo_final={c['saldo_final']} "
              f"-> {'DOBLE GASTO' if c['doble_gasto'] else 'ok'}")
        if out:
            (out / f"corrida_{n:03d}.json").write_text(
                json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")

    validas = len(corridas)
    if not validas:
        print("[demo] ninguna corrida valida.")
        return
    con_doble_gasto = sum(1 for c in corridas if c["doble_gasto"])
    print(f"\n[demo] RESUMEN concurrentes={args.concurrentes} delay_ms={args.delay_ms} "
          f"monto={args.monto} fondos={args.fondos}")
    print(f"[demo] doble gasto en {con_doble_gasto}/{validas} corridas "
          f"({100 * con_doble_gasto / validas:.1f}%)")

    if out:
        with open(out / "resumen.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["corrida", "concurrentes", "delay_ms", "monto", "fondos",
                        "aceptadas", "doble_gasto", "saldo_final"])
            for c in corridas:
                w.writerow([c["corrida"], c["concurrentes"], c["delay_ms"], c["monto"],
                            c["fondos"], c["aceptadas"], int(c["doble_gasto"]),
                            c["saldo_final"]])
        print(f"[demo] datos crudos guardados en {out}")


if __name__ == "__main__":
    main()
