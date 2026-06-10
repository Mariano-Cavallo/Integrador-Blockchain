# Pilar 2 — Arquitectura Distribuida (NCT)

Nodo Coordinador de Tareas (NCT) del proyecto **PopToken**. Implementado en Python con
FastAPI + Redis. Ver el caso de uso en [../Propuesta/Propuesta.md](../Propuesta/Propuesta.md).

## Estado

| Paso | Descripción | Estado |
|---|---|---|
| 1 | Validación de transacciones + Redis | Hecho |
| 2 | `pool:pending` + formación de bloque | Hecho |
| 3 | RabbitMQ — publicar tarea PoW | Pendiente |
| 4 | Conectar minero del Pilar 1 como worker | Pendiente |
| 5 | Recibir nonce ganador + MULTI/EXEC | Pendiente |
| 6 | Pool de transacciones (P5) — fragmentación + HPA | Pendiente |
| 7 | REST API completa + Web UI | Pendiente |

## Pasos 1 y 2 — Validación de txs y formación de bloque (resumen)

El NCT recibe transacciones por HTTP, valida su **estructura** y el **saldo** del emisor,
y si son válidas las encola en `pool:pending` (Redis). Cuando se forma un bloque, toma todas
las txs pendientes, las encadena al bloque anterior mediante hashes y vacía el pool.

### Archivos y qué hace cada uno

| Archivo | Para qué sirve |
|---|---|
| `nct/app/models.py` | Define qué es una transacción válida (esquemas pydantic de los 4 tipos: emisión, transferencia, canje, autorizar_emisor). Discrimina por el campo `type`. |
| `nct/app/keys.py` | Único lugar con los nombres de las claves de Redis (`genesis`, `chain:height`, `pool:pending`, `block:<i>`). Evita typos. |
| `nct/app/config.py` | Lee `REDIS_URL` del entorno (con default local). |
| `nct/app/redis_client.py` | Crea el cliente de conexión a Redis. |
| `nct/app/balances.py` | Calcula el saldo de una wallet recorriendo la cadena (modelo UTXO: recibido − enviado). Incluye `pool:pending` para evitar doble gasto. |
| `nct/app/validation.py` | Junta todo: valida estructura (models) + saldo (balances) y, si pasa, encola la tx en `pool:pending`. |
| `nct/app/chain.py` | Lógica de la cadena: calcula el hash de un bloque (MD5, determinístico con `sort_keys`), lee el hash del último bloque y forma un bloque nuevo con todo el pool, encadenándolo al anterior. |
| `nct/app/main.py` | API HTTP (FastAPI): `POST /tx`, `POST /block`, `GET /balance/{wallet}`, `GET /health`. |
| `nct/scripts/seed_genesis.py` | Siembra el bloque génesis en Redis (emisores autorizados, quórum, tokens por entrada). |
| `nct/tests/` | Tests con pytest (usan `fakeredis`, no tocan el Redis real): validación de estructura, de saldo, anti-doble-gasto y formación de bloque (sube height, vacía pool, encadena al génesis). |
| `docker-compose.yml` | Levanta Redis con persistencia AOF (contenedor `PopToken-redis`). |

### Decisiones de diseño

- **Saldo estilo UTXO**: no se almacena, se calcula recorriendo la historia.
- **`emision` acuña tokens** (no descuenta al emisor); `transferencia` y `canje` suman al destino y restan al origen.
- **Anti-doble-gasto**: el saldo cuenta también las txs en `pool:pending`.
- Las funciones reciben el cliente Redis por parámetro → permite testear con `fakeredis`.
- **Bloque**: un bloque agrupa todas las txs pendientes (no una sola) → el costo del PoW se paga una vez por paquete.
- **Encadenamiento**: el `previous_hash` del bloque 1 es el hash MD5 del génesis (no ceros); cada bloque referencia el hash del anterior → inmutabilidad.
- **Hash determinístico**: se serializa con `json.dumps(sort_keys=True)` y se excluye `block_hash`, para que sea reproducible (necesario para el PoW del minero).

## Cómo ejecutar

Requisitos: Docker, Python 3.x. Instalar deps: `pip install -r nct/requirements.txt`.

```bash
# 1. Levantar Redis (desde Pilar2/)
docker compose up -d

# 2. Sembrar el génesis (desde Pilar2/nct/)
python -m scripts.seed_genesis

# 3. Levantar la API (desde Pilar2/nct/)
python -m uvicorn app.main:app --reload --port 8888
#    Docs interactivas: http://localhost:8888/docs

# 4. Correr los tests (desde Pilar2/nct/)
python -m pytest tests/ -v
```

> Nota: todos los comandos de Python se corren parados en `Pilar2/nct/` (ahí vive el paquete `app`).
