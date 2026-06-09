import hashlib
import sys
import time

def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(f"Uso: python {sys.argv[0]} <cadena> <prefijo> <nonce_min> <nonce_max>")
        print(f"Ejemplo: python {sys.argv[0]} hola 0000 0 100000")
        sys.exit(1)

    cadena   = sys.argv[1]
    prefijo  = sys.argv[2]
    nonce_min = int(sys.argv[3])
    nonce_max = int(sys.argv[4])

    if nonce_min > nonce_max:
        print("Error: nonce_min debe ser <= nonce_max")
        sys.exit(1)

    print(f"Buscando nonce en [{nonce_min}, {nonce_max}] para MD5({cadena} + nonce) que empiece con '{prefijo}'...")
    t0 = time.time()

    encontrado = False
    for nonce in range(nonce_min, nonce_max + 1):
        h = md5(cadena + str(nonce))
        if h.startswith(prefijo):
            elapsed = time.time() - t0
            print(f"Nonce  : {nonce}")
            print(f"Input  : {cadena + str(nonce)}")
            print(f"MD5    : {h}")
            print(f"Tiempo : {elapsed:.3f}s")
            encontrado = True
            break

    if not encontrado:
        elapsed = time.time() - t0
        print(f"No se encontro solucion en el rango [{nonce_min}, {nonce_max}]")
        print(f"Tiempo : {elapsed:.3f}s")
