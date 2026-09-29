"""
Prueba de caos automatizada (Mejora 7): mata pods -y opcionalmente NODOS- del cluster
mientras hay carga real corriendo, y verifica al final que:

  1. el sistema se recupera (/health vuelve a "ok" en todo),
  2. la cadena queda consistente (altura secuencial, previous_hash bien encadenado),
  3. ninguna transaccion aceptada durante la corrida se perdio (ni sellada ni en el pool),
  4. el sistema SIGUIO AVANZANDO (crecio la altura de la cadena): una cadena "consistente"
     que dejo de avanzar no demuestra tolerancia a fallos,
  5. el trabajo en vuelo se REASIGNO y termino: el pool de pendientes se vacia y la cola
     `mining_tasks` queda en 0 listos / 0 sin ack (RabbitMQ reencola lo que no fue ackeado
     por el pod que murio, otro worker lo toma). Si nunca se mato un worker con una tarea
     realmente en vuelo, el criterio se informa como "NO EJERCITADO" en vez de OK.

No agrega resiliencia nueva - toda la recuperacion (RabbitMQ reencolando sin ack, K8s
recreando pods, MIG de GKE recreando nodos, Redis con AOF+PVC, el lock de auto_block con TTL)
ya existe. Este script es el arnes de prueba: mata cosas de forma controlada y deja un
registro reproducible (timeline de eventos + muestras de /health) en un JSON.

Uso:
    python chaos_test.py --url https://poptoken.34.122.53.67.nip.io --duracion 120
    python chaos_test.py --url ... --duracion 300 --nodos 1 --worker-en-vuelo

Requiere `kubectl` conectado al cluster correcto (ver Propuesta/DESPLIEGUE.md). Para matar
nodos (--nodos) requiere ademas `gcloud` autenticado con permiso `compute.instances.delete`
(los nodos de GKE son VMs de un managed instance group: GKE recrea el nodo borrado).
"""
import argparse
import hashlib
import json
import pathlib
import random
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

# reusa los helpers de registro/login/tx de load_test.py (mismo mecanismo de emisor,
# mismo protocolo) en vez de duplicarlos.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "Pilar2" / "nct"))
from scripts.load_test import _generar_wallet, _registrar, _login, _post, _obtener_emisor  # noqa: E402

PODS_OBJETIVO = ["nct-consumer", "worker-cpu", "redis"]  # label app=... a elegir al azar
COLA_MINADO = "mining_tasks"
T0 = time.time()
EVENTOS = []
_lock_eventos = threading.Lock()


def _evento(tipo, **datos):
    ev = {"t_s": round(time.time() - T0, 2), "tipo": tipo, **datos}
    with _lock_eventos:
        EVENTOS.append(ev)
    return ev


def _tx_id(data: dict) -> str:
    # misma formula que app/validation.py:tx_id() - se reimplementa liviano aca para no
    # acoplar este script (fuera del paquete nct) al codigo de la app.
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _get(url, path, timeout=10):
    try:
        with urllib.request.urlopen(url + path, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return None, {}


def _run(*cmd, timeout=120):
    # en Windows, gcloud/kubectl a veces son .cmd/.bat (no .exe): subprocess sin shell no
    # los encuentra por PATH aunque `where` si los vea. shutil.which resuelve la extension
    # correcta (PATHEXT) para que subprocess.run los pueda ejecutar sin shell=True.
    cmd = list(cmd)
    resuelto = shutil.which(cmd[0])
    if resuelto:
        cmd[0] = resuelto
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:  # kubectl/gcloud ausente o colgado
        return subprocess.CompletedProcess(cmd, 1, "", repr(e))


def _kubectl(*args):
    # timeout corto: con el cluster caido/inalcanzable kubectl se cuelga en vez de fallar.
    # 1 reintento: durante la ventana mas movida del caos, el apiserver puede tardar de mas
    # en una llamada puntual sin que signifique que el recurso realmente no existe.
    proc = _run("kubectl", "--request-timeout=25s", *args, timeout=35)
    if proc.returncode != 0:
        proc = _run("kubectl", "--request-timeout=25s", *args, timeout=35)
    return proc


# ---------------------------------------------------------------- RabbitMQ / cola

def estado_cola(cola=COLA_MINADO):
    """(ready, unacked) de la cola, via rabbitmqctl en cualquier replica viva; None si no se pudo."""
    for i in range(3):
        proc = _kubectl("exec", f"rabbitmq-{i}", "--", "rabbitmqctl", "list_queues",
                        "name", "messages_ready", "messages_unacknowledged", "--formatter",
                        "json")
        if proc.returncode != 0:
            continue
        try:
            for fila in json.loads(proc.stdout):
                if fila.get("name") == cola:
                    return int(fila["messages_ready"]), int(fila["messages_unacknowledged"])
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return None


def esperar_tarea_en_vuelo(timeout=60):
    """Espera a que haya una tarea de minado tomada y sin ack (la tiene un worker AHORA)."""
    fin = time.time() + timeout
    while time.time() < fin:
        est = estado_cola()
        if est and est[1] > 0:
            return est
        time.sleep(1)
    return None


# ---------------------------------------------------------------- inyeccion de fallas

def _pods(app_label):
    proc = _kubectl("get", "pods", "-l", f"app={app_label}", "-o",
                    "jsonpath={.items[*].metadata.name}")
    return proc.stdout.split()


def matar_pod_al_azar(worker_en_vuelo):
    app_label = random.choice(PODS_OBJETIVO)
    pods = _pods(app_label)
    if not pods:
        print(f"[chaos] no encontre pods de app={app_label}, salteo.")
        return None

    if app_label == "worker-cpu" and worker_en_vuelo:
        # se espera a que haya una tarea en vuelo y se matan TODOS los workers: asi el que
        # la tiene seguro muere y se ejercita la reasignacion (con uno solo al azar podria errar).
        est = esperar_tarea_en_vuelo()
        objetivo = pods
        en_vuelo = est[1] if est else 0
    else:
        objetivo = [random.choice(pods)]
        est = estado_cola()
        en_vuelo = est[1] if est else None

    print(f"[chaos] matando pod(s) {objetivo} (app={app_label}), tareas en vuelo: {en_vuelo}")
    for pod in objetivo:
        _kubectl("delete", "pod", pod, "--wait=false")
    _evento("kill_pod", app=app_label, pods=objetivo, tareas_en_vuelo=en_vuelo,
            cola=est)
    return objetivo


def matar_nodo(rol):
    nodos = _kubectl("get", "nodes", "-l", f"role={rol}", "-o",
                     "jsonpath={.items[*].metadata.name}").stdout.split()
    if not nodos:
        print(f"[chaos] no encontre nodos con role={rol}, salteo.")
        return None
    nodo = random.choice(nodos)
    zona = _kubectl("get", "node", nodo, "-o",
                    r"jsonpath={.metadata.labels.topology\.kubernetes\.io/zone}").stdout.strip()
    afectados = _kubectl("get", "pods", "-A", "--field-selector", f"spec.nodeName={nodo}",
                         "-o", "jsonpath={.items[*].metadata.name}").stdout.split()
    est = estado_cola()
    print(f"[chaos] MATANDO NODO {nodo} (role={rol}, zona={zona}); pods afectados: {afectados}")
    proc = _run("gcloud", "compute", "instances", "delete", nodo, "--zone", zona, "--quiet",
                timeout=300)
    _evento("kill_nodo", nodo=nodo, rol=rol, zona=zona, pods_afectados=afectados, cola=est,
            ok=proc.returncode == 0, stderr=proc.stderr[-300:])
    if proc.returncode != 0:
        print(f"[chaos] no se pudo borrar el nodo: {proc.stderr.strip()[-200:]}")
        return None
    return nodo


# ---------------------------------------------------------------- monitoreo y verificacion

def _monitor(url, detener, muestras):
    """Toma una muestra de /health cada 4s (el endpoint permite 20/min) durante todo el caos."""
    while not detener.is_set():
        status, body = _get(url, "/health", timeout=5)
        ok = status == 200 and bool(body) and all(v == "ok" for v in body.values())
        _, st = _get(url, "/status", timeout=5)
        muestras.append({"t_s": round(time.time() - T0, 2), "http": status, "ok": ok,
                         "health": body, "altura": st.get("height"),
                         "pendientes": st.get("pending")})
        detener.wait(4)


def _ventanas_degradadas(muestras):
    """Intervalos contiguos en que /health no estuvo 'ok': [(inicio_s, fin_s)]."""
    ventanas, inicio = [], None
    for m in muestras:
        if not m["ok"] and inicio is None:
            inicio = m["t_s"]
        elif m["ok"] and inicio is not None:
            ventanas.append((inicio, m["t_s"]))
            inicio = None
    if inicio is not None:
        ventanas.append((inicio, muestras[-1]["t_s"]))
    return ventanas


def esperar_health_ok(url, timeout):
    print("[chaos] esperando a que /health vuelva a 'ok' en todo...")
    inicio = time.time()
    while time.time() - inicio < timeout:
        status, body = _get(url, "/health")
        if status == 200 and body and all(v == "ok" for v in body.values()):
            print(f"[chaos] health OK despues de {time.time() - inicio:.1f}s")
            return True, round(time.time() - inicio, 1)
        time.sleep(4)
    print("[chaos] TIMEOUT esperando /health OK")
    return False, round(time.time() - inicio, 1)


def verificar_altura_y_encadenado(url):
    status, body = _get(url, "/chain")
    if status != 200:
        return False, ["no pude leer /chain"]

    problemas = []
    bloques = body.get("blocks", [])
    altura = body.get("height", 0)

    if len(bloques) != altura:
        problemas.append(f"altura reportada={altura} pero llegaron {len(bloques)} bloques")

    indices = [int(b["index"]) for b in bloques]
    esperado = list(range(1, len(bloques) + 1))
    if indices != esperado:
        problemas.append(f"indices no son secuenciales/sin huecos: {indices}")

    # cada bloque N debe encadenar con el hash del N-1 (integridad de la cadena)
    for i in range(1, len(bloques)):
        anterior, actual = bloques[i - 1], bloques[i]
        if actual.get("previous_hash") != anterior.get("block_hash"):
            problemas.append(
                f"bloque {actual.get('index')}: previous_hash no coincide con "
                f"block_hash del bloque {anterior.get('index')}"
            )

    return len(problemas) == 0, problemas


def verificar_tx_no_perdidas(url, tx_ids_aceptadas):
    if not tx_ids_aceptadas:
        return True, []

    status, chain = _get(url, "/chain")
    status_pool, pool = _get(url, "/pool")
    if status != 200 or status_pool != 200:
        return False, ["no pude leer /chain o /pool para verificar transacciones"]

    presentes = set()
    for bloque in chain.get("blocks", []):
        for tx in bloque.get("transactions", []):
            presentes.add(_tx_id(tx))
    for tx in pool.get("pending", []):
        presentes.add(_tx_id(tx))

    perdidas = [tx for tx in tx_ids_aceptadas if tx["tx_id"] not in presentes]
    return len(perdidas) == 0, [
        f"tx {tx['tx_id']} ({tx['from']}->{tx['to']}, enviada en t={tx['t_s']}s) "
        f"aceptada pero no esta ni sellada ni en el pool" for tx in perdidas
    ]


def verificar_trabajo_reasignado(url, timeout):
    """El pool se vacia (cada 30s auto_block forma bloque con lo pendiente) y la cola de
    minado queda en 0 listos / 0 sin ack: nada quedo huerfano en un worker muerto."""
    fin = time.time() + timeout
    ultimo = None
    while time.time() < fin:
        _, st = _get(url, "/status")
        pendientes = st.get("pending")
        cola = estado_cola()
        ultimo = {"pendientes_pool": pendientes, "cola_minado": cola}
        if pendientes == 0 and cola is not None and cola == (0, 0):
            return True, ultimo
        time.sleep(5)
    return False, ultimo


# ---------------------------------------------------------------- carga de fondo

def _generar_carga_de_fondo(url, detener, tx_ids_aceptadas, lock):
    """Corre en un thread aparte durante todo el caos, mandando transferencias sueltas y
    registrando el tx_id de cada una que se acepta, para poder verificar despues que
    ninguna se perdio."""
    emisor_wallet, emisor_priv = _obtener_emisor(url)
    if not emisor_wallet:
        print("[chaos] no se pudo conseguir un emisor, corre sin carga de fondo.")
        return
    emisor_token = _login(url, emisor_wallet, emisor_priv)

    sufijo = int(time.time())
    wallets = []
    # reintenta el fondeo inicial: si el caos justo mata redis/rabbitmq en este momento
    # puntual, un solo intento fallido no debe dejar la corrida entera sin carga de fondo.
    for intento in range(5):
        wallets = []
        for i in range(3):
            wallet = f"chaos_{sufijo}_{i}"
            priv, pub_pem = _generar_wallet()
            _registrar(url, wallet, pub_pem)
            token = _login(url, wallet, priv)
            if token:
                wallets.append((wallet, token))
                _post(url, "/tx", {
                    "type": "emision", "from": emisor_wallet, "to": wallet, "tokens": 50,
                    "motivo": "chaos_test", "pelicula": "N/A",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }, token=emisor_token)
        if len(wallets) >= 2:
            break
        print(f"[chaos] fondeo de wallets de prueba fallo (intento {intento + 1}/5), reintentando...")
        time.sleep(5)

    if len(wallets) < 2:
        print("[chaos] no se pudieron fondear wallets de prueba tras varios intentos, "
              "corre sin carga de fondo.")
        return

    while not detener.is_set():
        origen, token = random.choice(wallets)
        destino = random.choice([w for w, _ in wallets if w != origen])
        tx = {"type": "transferencia", "from": origen, "to": destino, "tokens": 1,
              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
        t_envio = round(time.time() - T0, 2)
        try:
            status, _ = _post(url, "/tx", tx, token=token)
        except Exception:  # la API puede caer durante el caos: no cuenta como aceptada
            status = None
        if status == 200:
            with lock:
                tx_ids_aceptadas.append({"t_s": t_envio, "tx_id": _tx_id(tx),
                                         "from": origen, "to": destino})
        time.sleep(1)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="https://poptoken.34.122.53.67.nip.io")
    ap.add_argument("--duracion", type=int, default=120, help="segundos que dura el caos")
    ap.add_argument("--intervalo-min", type=int, default=15)
    ap.add_argument("--intervalo-max", type=int, default=30)
    ap.add_argument("--nodos", type=int, default=0,
                    help="cantidad de NODOS a matar, repartidos dentro de la duracion")
    ap.add_argument("--rol-nodo", default="apps", choices=["apps", "infra"],
                    help="pool del que se elige el nodo (infra = Redis/RabbitMQ, mas severo)")
    ap.add_argument("--worker-en-vuelo", action="store_true",
                    help="al matar workers, esperar una tarea en vuelo y matarlos a todos")
    ap.add_argument("--timeout-recuperacion", type=int, default=None,
                    help="segundos maximos para que todo se recupere (default 120, 420 con --nodos)")
    ap.add_argument("--out", default=str(pathlib.Path(__file__).parent / "resultados"),
                    help="directorio del JSON crudo de la corrida")
    args = ap.parse_args()
    timeout_rec = args.timeout_recuperacion or (420 if args.nodos else 120)

    print("[chaos] baseline...")
    _, baseline = _get(args.url, "/chain")
    altura_inicial = baseline.get("height")
    print(f"[chaos] altura inicial: {altura_inicial}")
    _evento("baseline", altura=altura_inicial, cola=estado_cola())

    tx_ids_aceptadas = []
    muestras = []
    lock = threading.Lock()
    detener = threading.Event()
    hilo_carga = threading.Thread(
        target=_generar_carga_de_fondo, args=(args.url, detener, tx_ids_aceptadas, lock),
        daemon=True,
    )
    hilo_monitor = threading.Thread(target=_monitor, args=(args.url, detener, muestras),
                                    daemon=True)
    hilo_carga.start()
    hilo_monitor.start()

    # los nodos se matan en instantes fijos repartidos en la ventana; los pods, a intervalos
    # aleatorios entre kills. Todo va al timeline.
    print(f"[chaos] iniciando caos por {args.duracion}s (pods de {PODS_OBJETIVO}, "
          f"{args.nodos} nodo(s) role={args.rol_nodo})...")
    inicio = time.time()
    fin = inicio + args.duracion
    instantes_nodo = [inicio + args.duracion * (i + 1) / (args.nodos + 1)
                      for i in range(args.nodos)]
    muertos, nodos_muertos = [], []
    workers_con_tarea_en_vuelo = 0
    proximo_pod = inicio  # arranca ya
    while time.time() < fin:
        ahora = time.time()
        if instantes_nodo and ahora >= instantes_nodo[0]:
            instantes_nodo.pop(0)
            nodo = matar_nodo(args.rol_nodo)
            if nodo:
                nodos_muertos.append(nodo)
        elif ahora >= proximo_pod:
            objetivo = matar_pod_al_azar(args.worker_en_vuelo)
            if objetivo:
                muertos.extend(objetivo)
                ev = EVENTOS[-1]
                if ev["app"] == "worker-cpu" and (ev["tareas_en_vuelo"] or 0) > 0:
                    workers_con_tarea_en_vuelo += 1
            proximo_pod = time.time() + random.randint(args.intervalo_min, args.intervalo_max)
        time.sleep(1)

    detener.set()
    hilo_carga.join(timeout=10)
    hilo_monitor.join(timeout=10)
    print(f"[chaos] caos terminado. Pods matados: {muertos}. Nodos matados: {nodos_muertos}")
    print(f"[chaos] transacciones aceptadas durante la corrida: {len(tx_ids_aceptadas)}")

    criterios = []
    recuperado, t_rec = esperar_health_ok(args.url, timeout_rec)
    criterios.append(("recuperacion: /health vuelve a ok", recuperado,
                      f"{t_rec}s (limite {timeout_rec}s)"))

    if recuperado:
        ok_altura, problemas_altura = verificar_altura_y_encadenado(args.url)
        criterios.append(("cadena consistente (secuencial + previous_hash)", ok_altura,
                          "; ".join(problemas_altura) or "sin problemas"))

        ok_tx, problemas_tx = verificar_tx_no_perdidas(args.url, tx_ids_aceptadas)
        criterios.append((f"ninguna de las {len(tx_ids_aceptadas)} tx aceptadas se perdio", ok_tx,
                          "; ".join(problemas_tx) or "todas en cadena o pool"))

        ok_drenado, ultimo = verificar_trabajo_reasignado(args.url, timeout_rec)
        criterios.append(("trabajo reasignado: pool vacio y cola de minado en 0/0", ok_drenado,
                          f"estado final {ultimo}"))

        _, final = _get(args.url, "/chain")
        altura_final = final.get("height")
        avanzo = altura_inicial is not None and altura_final is not None \
            and altura_final > altura_inicial
        criterios.append(("el sistema siguio avanzando (altura crecio)", avanzo,
                          f"{altura_inicial} -> {altura_final}"))

    ejercitado = workers_con_tarea_en_vuelo > 0
    print("\n[chaos] ===== CRITERIOS =====")
    for nombre, ok, detalle in criterios:
        print(f"  [{'OK ' if ok else 'FALLO'}] {nombre} - {detalle}")
    if not ejercitado:
        print("  [AVISO] NO EJERCITADO: no se mato ningun worker con una tarea en vuelo; "
              "la reasignacion no quedo demostrada en esta corrida (usar --worker-en-vuelo).")
    ok_total = all(ok for _, ok, _ in criterios)
    print(f"[chaos] RESULTADO: {'OK' if ok_total else 'FALLO'}"
          f"{'' if ejercitado or not ok_total else ' (reasignacion sin ejercitar)'}")

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    archivo = out / f"chaos_{time.strftime('%Y%m%d_%H%M%S')}.json"
    archivo.write_text(json.dumps({
        "parametros": vars(args), "altura_inicial": altura_inicial,
        "pods_matados": muertos, "nodos_matados": nodos_muertos,
        "tx_aceptadas": len(tx_ids_aceptadas), "tx_detalle": tx_ids_aceptadas,
        "workers_matados_con_tarea_en_vuelo": workers_con_tarea_en_vuelo,
        "reasignacion_ejercitada": ejercitado,
        "ventanas_degradadas_s": _ventanas_degradadas(muestras) if muestras else [],
        "criterios": [{"criterio": n, "ok": ok, "detalle": d} for n, ok, d in criterios],
        "resultado": "OK" if ok_total else "FALLO",
        "eventos": EVENTOS, "muestras_health": muestras,
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"[chaos] registro crudo guardado en {archivo}")
    sys.exit(0 if ok_total else 1)


if __name__ == "__main__":
    main()
