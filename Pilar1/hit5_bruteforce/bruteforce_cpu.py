import hashlib
import sys
import time

def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

def bruteforce(cadena: str, prefijo: str) -> tuple[int, str]:
    nonce = 0
    while True:
        candidate = cadena + str(nonce)
        h = md5(candidate)
        if h.startswith(prefijo):
            return nonce, h
        nonce += 1

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Uso: python {sys.argv[0]} <cadena> <prefijo>")
        print(f"Ejemplo: python {sys.argv[0]} hola 0000")
        sys.exit(1)

    cadena  = sys.argv[1]
    prefijo = sys.argv[2]

    print(f"Buscando nonce para MD5({cadena} + nonce) que empiece con '{prefijo}'...")
    t0 = time.time()
    nonce, h = bruteforce(cadena, prefijo)
    elapsed = time.time() - t0

    print(f"Nonce  : {nonce}")
    print(f"Input  : {cadena + str(nonce)}")
    print(f"MD5    : {h}")
    print(f"Tiempo : {elapsed:.3f}s")
