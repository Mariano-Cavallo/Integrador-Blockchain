from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature


def verificar_firma(public_key_pem: str, mensaje: str, signature_hex: str) -> bool:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        sig_bytes = bytes.fromhex(signature_hex)
        msg_bytes = mensaje.encode()
        public_key.verify(sig_bytes, msg_bytes, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, Exception):
        return False
