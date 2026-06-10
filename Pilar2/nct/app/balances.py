import json
from app import keys

def calcular_saldo(wallet, r):
    saldo = 0
    
    # 1. recorrer bloques confirmados (block:1 .. chain:height)
    altura = int(r.get(keys.CHAIN_HEIGHT) or 0)
    for i in range(1, altura + 1):
        bloque = r.hgetall(keys.block(i))
        txs = json.loads(bloque["transactions"])   
        for tx in txs:
            saldo += _efecto(tx, wallet)
    
    # 2. recorrer pool:pending
    for tx_raw in r.lrange(keys.POOL_PENDING, 0, -1):
        tx = json.loads(tx_raw)
        saldo += _efecto(tx, wallet)
    
    return saldo

def _efecto(tx, wallet):    
    if(tx["type"] in ("transferencia", "canje")):
        if tx["to"] == wallet:
            return int(tx["tokens"])
        elif tx["from"] == wallet:
            return -int(tx["tokens"])
    elif(tx["type"] == "emision"):
        if tx["to"] == wallet:
            return int(tx["tokens"])    
    return 0
    
