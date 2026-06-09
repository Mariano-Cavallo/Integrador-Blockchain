import hashlib
import sys

def md5_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Uso: python {sys.argv[0]} <string>")
        sys.exit(1)

    entrada = sys.argv[1]
    resultado = md5_hash(entrada)
    print(f"Input : {entrada}")
    print(f"MD5   : {resultado}")
