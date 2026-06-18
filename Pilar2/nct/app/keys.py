GENESIS = "genesis"
CHAIN_HEIGHT = "chain:height"
POOL_PENDING = "pool:pending"
SEEN_TX = "seen:tx"     

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

