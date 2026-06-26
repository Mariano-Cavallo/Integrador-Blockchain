from prometheus_client import Counter, Gauge

tx_total = Counter(
    "nct_transactions_total",
    "Total de transacciones procesadas",
    ["tipo", "resultado"],
)
blocks_formed = Counter("nct_blocks_formed_total", "Bloques formados por el NCT")
blocks_sealed = Counter("nct_blocks_sealed_total", "Bloques sellados exitosamente")
chain_height  = Gauge("nct_chain_height", "Altura actual de la cadena")
pool_size     = Gauge("nct_pool_size", "Transacciones pendientes en el pool")
