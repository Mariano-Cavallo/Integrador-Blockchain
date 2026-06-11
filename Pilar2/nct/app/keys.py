GENESIS = "genesis"
CHAIN_HEIGHT = "chain:height"
POOL_PENDING = "pool:pending"
SEEN_TX = "seen:tx"     

def block(index):
    return f"block:{index}"

def block_pending(index):
    return f"block:pending:{index}"

