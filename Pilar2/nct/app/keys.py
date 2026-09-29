GENESIS = "genesis"
CHAIN_HEIGHT = "chain:height"
POOL_PENDING = "pool:pending"
SEEN_TX = "seen:tx"
HEALTH_CONSUMER = "health:nct-consumer"
# dificultad movil (Mejora 1): vive ACA, separada del genesis, para que el genesis quede
# 100% inmutable despues de sembrado. Arranca en el mismo valor que genesis.difficulty
# (ver seed_genesis.py) pero de ahi en mas es esta key la que se ajusta, nunca el genesis.
CHAIN_DIFFICULTY = "chain:difficulty"

def block(index):
    return f"block:{index}"

def block_pending(index):
    return f"block:pending:{index}"

def pubkey(wallet):
    return f"pubkey:{wallet}"

def challenge(wallet):
    return f"challenge:{wallet}"

def session(token):
    return f"session:{token}"

def solicitud_emisor(wallet):
    return f"solicitud:emisor:{wallet}"

