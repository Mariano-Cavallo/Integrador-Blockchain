"""
Genera transacciones reales contra un NCT en funcionamiento (local o nube), para tener
actividad de minado sostenida durante una corrida de benchmark (Mejora 3) o de caos (Mejora 7).

Uso:
    python -m scripts.load_test --url http://localhost:8888 --n-wallets 5 --n-tx 30
    python -m scripts.load_test --url https://poptoken.34.122.53.67.nip.io --n-tx 10

Para poder emitir tokens hace falta un emisor autorizado (el resto de las tx, transferencia/
canje, salen de wallets ya fondeadas por esas emisiones). Dos caminos, segun el estado de la
cadena contra la que se corre:

  - Cadena RECIEN sembrada (fresh, ej. local tras `seed_genesis`): el script intenta
    registrarse como uno de los emisores del genesis (Hoyts_123 / cinepolis_456 / cinemark_789)
    con un par de claves nuevo. Como nadie lo reclamo todavia, el registro funciona solo.
  - Cadena YA en uso (produccion): esos nombres ya estan reclamados (409 en /register). Hace
    falta pasar la clave privada de un emisor real por variables de entorno:
        EMISOR_WALLET=Hoyts_123
        EMISOR_PRIVATE_KEY_PEM=/ruta/a/la/clave_privada.pem_o_.json
    Acepta tanto PEM como JWK (el formato que exporta crypto.subtle del navegador, ej.
    "clave-privada-Hoyts_123.json") - se detecta solo segun el contenido del archivo.

OJO: corrido contra la URL publica de produccion, esto agrega transacciones y bloques reales
a la cadena. Usar con criterio (tandas acotadas), no es trafico descartable.
"""
import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

GENESIS_EMISORES = ("Hoyts_123", "cinepolis_456", "cinemark_789")

_JWK_CURVAS = {
    "P-256": ec.SECP256R1(),
    "P-384": ec.SECP384R1(),
    "P-521": ec.SECP521R1(),
}


def _b64url_a_entero(valor: str) -> int:
    import base64
    relleno = "=" * (-len(valor) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(valor + relleno), "big")


def _cargar_clave_privada(path: str):
    """Carga una clave privada EC desde PEM o desde JWK (el formato que exporta
    crypto.subtle del navegador - ver app/static/index.html). Se detecta sola: si el
    archivo parsea como JSON con un campo "d", es JWK; si no, se asume PEM."""
    with open(path, "rb") as f:
        contenido = f.read()
    try:
        jwk = json.loads(contenido)
    except json.JSONDecodeError:
        jwk = None

    if jwk and "d" in jwk:
        curva = _JWK_CURVAS.get(jwk.get("crv"))
        if curva is None:
            raise ValueError(f"curva JWK no soportada: {jwk.get('crv')}")
        valor_privado = _b64url_a_entero(jwk["d"])
        return ec.derive_private_key(valor_privado, curva)

    return serialization.load_pem_private_key(contenido, password=None)


def _post(url, path, body, token=None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url + path, data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except json.JSONDecodeError:
            return e.code, {}


def _get(url, path):
    try:
        with urllib.request.urlopen(url + path) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def _generar_wallet():
    priv = ec.generate_private_key(ec.SECP256R1())
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return priv, pub_pem


def _firmar(priv, mensaje: str) -> str:
    return priv.sign(mensaje.encode(), ec.ECDSA(hashes.SHA256())).hex()


def _registrar(url, wallet, pub_pem):
    return _post(url, "/register", {"wallet": wallet, "public_key": pub_pem})


def _login(url, wallet, priv):
    status, body = _get(url, f"/challenge/{wallet}")
    if status != 200:
        return None
    firma = _firmar(priv, body["challenge"])
    status, body = _post(url, "/auth", {"wallet": wallet, "signature": firma})
    return body.get("token") if status == 200 else None


def _obtener_emisor(url):
    """Devuelve (wallet, priv_key) de un emisor autenticable, o (None, None) si no se pudo."""
    wallet = os.getenv("EMISOR_WALLET")
    key_path = os.getenv("EMISOR_PRIVATE_KEY_PEM")
    if wallet and key_path:
        return wallet, _cargar_clave_privada(key_path)

    for candidato in GENESIS_EMISORES:
        priv, pub_pem = _generar_wallet()
        status, _ = _registrar(url, candidato, pub_pem)
        if status == 200:
            print(f"[load_test] Emisor '{candidato}' libre, reclamado con clave nueva.")
            return candidato, priv

    print("[load_test] Los emisores del genesis ya estan reclamados (cadena en uso real).")
    print("[load_test] Pasa EMISOR_WALLET y EMISOR_PRIVATE_KEY_PEM para usar un emisor existente.")
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://localhost:8888")
    ap.add_argument("--n-wallets", type=int, default=5)
    ap.add_argument("--n-tx", type=int, default=30)
    ap.add_argument("--sleep", type=float, default=0.3, help="segundos entre tx")
    args = ap.parse_args()

    emisor_wallet, emisor_priv = _obtener_emisor(args.url)
    if not emisor_wallet:
        return
    emisor_token = _login(args.url, emisor_wallet, emisor_priv)
    if not emisor_token:
        print("[load_test] No se pudo autenticar el emisor, abortando.")
        return

    sufijo = int(time.time())
    usuarios = []
    for i in range(args.n_wallets):
        wallet = f"loadtest_{sufijo}_{i}"
        priv, pub_pem = _generar_wallet()
        _registrar(args.url, wallet, pub_pem)
        token = _login(args.url, wallet, priv)
        if token:
            usuarios.append((wallet, token))
    print(f"[load_test] {len(usuarios)} wallets de usuario registradas.")
    if not usuarios:
        return

    for wallet, _ in usuarios:
        _post(args.url, "/tx", {
            "type": "emision", "from": emisor_wallet, "to": wallet, "tokens": 20,
            "motivo": "carga_de_prueba", "pelicula": "N/A",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, token=emisor_token)
    print(f"[load_test] {len(usuarios)} emisiones iniciales enviadas.")

    for i in range(args.n_tx):
        origen, token = random.choice(usuarios)
        candidatos = [u for u in usuarios if u[0] != origen]
        if not candidatos:
            continue
        destino, _ = random.choice(candidatos)
        status, body = _post(args.url, "/tx", {
            "type": "transferencia", "from": origen, "to": destino, "tokens": 1,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, token=token)
        detalle = body.get("status") or body.get("detail")
        print(f"[load_test] tx {i + 1}/{args.n_tx}: {status} {detalle}")
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
