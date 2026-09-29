import json
from app.redis_client import get_redis
from app import keys
from datetime import datetime

def main():
    r = get_redis()
    genesis = {
        "type": "genesis",
        "previous_hash": "0" * 16,
        "difficulty": "00",
        "emisores_autorizados": json.dumps(["Hoyts_123", "cinepolis_456", "cinemark_789"]),
        "quorum_requerido": 3,
        "tokens_por_entrada": 10,
        "timestamp": datetime.now().isoformat(),
    }
    r.hset(keys.GENESIS, mapping=genesis)
    r.set(keys.CHAIN_HEIGHT, 0)
    # dificultad movil (Mejora 1): arranca igual que genesis.difficulty, pero en su propia
    # key mutable - el genesis nunca se vuelve a tocar despues de esta siembra.
    r.set(keys.CHAIN_DIFFICULTY, genesis["difficulty"])
    print("Genesis sembrado")

if __name__ == "__main__":
    main()
