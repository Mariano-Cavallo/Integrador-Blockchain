# Pilar 2 — PopToken Blockchain

Sistema de tokens para cines implementado como una blockchain con Proof of Work distribuido.

---

## Arquitectura general

```
Browser (index.html)
        │  HTTP REST
        ▼
  nct-api (FastAPI)  ──── Redis ────  nct-consumer
        │                                    │
        │  RabbitMQ: mining_tasks            │ RabbitMQ: mining_results
        ▼                                    │
  worker-cpu × N  ──────────────────────────┘
```

| Servicio | Rol |
|---|---|
| `nct-api` | API REST + UI web. Recibe transacciones, forma bloques, expone endpoints. |
| `nct-consumer` | Escucha resultados de minado y sella bloques en Redis. |
| `worker-cpu` | Minero. Busca nonces en un rango dado. Escalable con `--scale`. |
| `redis` | Estado persistente: cadena, pool, autenticación. |
| `rabbitmq` | Cola de tareas de minado y resultados. |

---

## Flujo completo de una transacción

```
1. Usuario firma tx con su clave privada (browser)
2. POST /tx  →  validar_tx()  →  pool:pending (Redis)
3. Cada 30s (o POST /block manual)  →  formar_bloque()
4. Se publican N fragmentos en mining_tasks (RabbitMQ)
5. Workers consumen fragmentos y buscan nonce MD5 con prefijo "00"
6. Worker ganador publica en mining_results
7. nct-consumer llama sellar_bloque() → block:{i} confirmado en Redis
```

---

## Tipos de transacciones

| Tipo | `from` | `to` | Regla de destino |
|---|---|---|---|
| `emision` | cine emisor | usuario | solo a usuarios (no cines) |
| `transferencia` | usuario | usuario | solo a usuarios registrados |
| `canje` | usuario | cine | solo a cines emisores |
| `autorizar_emisor` | sistema interno | — | generada automáticamente al alcanzar quórum |

---

## Autenticación (ECDSA P-384)

El login NO es usuario/contraseña. Es un protocolo de desafío-respuesta:

```
1. Browser genera par de claves ECDSA P-384 (WebCrypto)
2. Clave pública se envía al servidor  →  POST /register
3. Login: GET /challenge/{wallet}  →  servidor devuelve texto aleatorio
4. Browser firma el challenge con su clave privada  →  POST /auth
5. Servidor verifica la firma con la clave pública guardada
6. Si es válida, devuelve un token de sesión (Bearer token, 1h)
7. Todas las requests posteriores llevan Authorization: Bearer <token>
```

La clave privada nunca sale del browser (se guarda en `localStorage` como JWK).

---

## Registro de cines emisores

Un cine no puede emitir tokens sin ser autorizado. El proceso es blockchain-correcto:

```
1. Cine solicita  →  POST /solicitar_emisor  →  solicitud en Redis
2. Cines ya autorizados votan  →  POST /votar_emisor
3. Al alcanzar quórum (3 votos)  →  se genera tx autorizar_emisor en el pool
4. Esa tx se mina en un bloque como cualquier otra
5. Desde ese bloque, el cine aparece como emisor al escanear la cadena
```

La lista de emisores no se persiste por separado: `_get_emisores()` lee el génesis y escanea bloque a bloque buscando txs `autorizar_emisor`.

---

## Archivos — descripción y partes clave

### `app/main.py` — API REST (FastAPI)

Punto de entrada de la aplicación. Define todos los endpoints HTTP y el hilo de auto-bloque.

**Partes clave:**

- `_loop_auto_bloque()` (línea 30): hilo daemon que cada 30 segundos forma un bloque si hay txs pendientes.
- `startup()`: lanza el hilo al arrancar. No inicia el consumidor (eso lo hace `nct-consumer`).
- `_get_emisores(r)` (línea 168): escanea genesis + todos los bloques confirmados para obtener la lista actualizada de cines emisores. Es la única fuente de verdad — no hay lista separada.
- `_require_auth()` (línea 116): valida el Bearer token contra Redis. Toda ruta protegida lo llama primero.
- `POST /tx` (línea 126): verifica que `from` coincide con el wallet autenticado antes de validar.
- `POST /votar_emisor` (línea 208): al alcanzar quórum empuja una tx `autorizar_emisor` al pool (no muta el génesis).

**Endpoints principales:**

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/register` | Registra clave pública de una wallet |
| GET | `/challenge/{wallet}` | Emite challenge para login |
| POST | `/auth` | Verifica firma y devuelve token de sesión |
| POST | `/tx` | Envía transacción (requiere auth) |
| GET | `/balance/{wallet}` | Saldo actual (requiere auth) |
| POST | `/block` | Forma bloque manualmente |
| POST | `/solicitar_emisor` | Cine pide ser autorizado |
| GET | `/solicitudes_emisor` | Lista solicitudes pendientes |
| POST | `/votar_emisor` | Cine vota una solicitud |
| GET | `/estado_emisor/{wallet}` | Estado de solicitud de un cine |
| GET | `/tipo_wallet/{wallet}` | Devuelve "cine", "usuario" o "desconocida" |

---

### `app/validation.py` — Validación de transacciones

Valida una tx antes de agregarla al pool. Retorna `(bool, mensaje)`.

**Orden de validaciones:**
1. Bloquea `autorizar_emisor` enviados externamente (tipo reservado al sistema).
2. Valida estructura con Pydantic (`models.py`).
3. Verifica que el emisor está autorizado (solo para `emision`).
4. Anti-duplicado por hash MD5 de la tx (`seen:tx` en Redis).
5. Saldo suficiente (para `transferencia` y `canje`).
6. Destino registrado y del tipo correcto según el tipo de tx (líneas 41–50).

Si todo pasa, empuja la tx al `pool:pending` y registra su ID en `seen:tx`.

---

### `app/auth.py` — Verificación ECDSA

Función única `verificar_firma(public_key_pem, mensaje, signature_hex)`.

Usa la librería `cryptography` de Python para verificar firmas ECDSA con SHA-256. La firma llega en formato DER hex (convertido en el browser desde el formato raw de WebCrypto).

---

### `app/chain.py` — Formación de bloques

- `formar_bloque(r)`: toma todas las txs del pool, crea el bloque pendiente en Redis y publica N fragmentos de nonces en RabbitMQ.
- Cada fragmento cubre un rango `[nonce_min, nonce_max]` sobre 10.000.000 de nonces posibles divididos en `N_FRAGMENTOS`.
- `hash_bloque(bloque)`: hash MD5 del bloque serializado (sin el campo `block_hash`). Es la base sobre la que los workers minan.
- `ultimo_hash(r)`: devuelve el hash del último bloque confirmado para encadenar el siguiente.

---

### `app/sealer.py` — Sellado de bloques

Llamado por `nct-consumer` cuando llega un resultado de minado.

1. Recupera el bloque pendiente de Redis.
2. Recomputa el hash para verificar que el nonce es válido.
3. Si es válido: escribe `block:{i}`, actualiza `chain:height`, borra el pendiente y limpia el pool (transacción atómica Redis `MULTI/EXEC`).
4. Si ya fue sellado por otro worker (carrera): devuelve `False` y descarta.
5. Post-sellado: elimina las `solicitud:emisor` cuyas txs `autorizar_emisor` quedaron confirmadas en el bloque.

---

### `app/balances.py` — Cálculo de saldo

Recorre bloques confirmados + pool pendiente y suma/resta tokens según el tipo de tx y el rol de la wallet (`from` o `to`). No hay tabla de saldos — se recalcula en cada consulta.

---

### `app/models.py` — Modelos Pydantic

Define las 4 estructuras de transacción válidas con discriminación por `type`:
`Emision`, `Transferencia`, `Canje`, `AutorizarEmisor`.

---

### `app/keys.py` — Claves Redis

Centraliza todos los nombres de clave usados en Redis:

| Función/Constante | Clave Redis |
|---|---|
| `GENESIS` | `"genesis"` |
| `CHAIN_HEIGHT` | `"chain:height"` |
| `POOL_PENDING` | `"pool:pending"` |
| `SEEN_TX` | `"seen:tx"` |
| `block(i)` | `"block:{i}"` |
| `block_pending(i)` | `"block:pending:{i}"` |
| `pubkey(wallet)` | `"pubkey:{wallet}"` |
| `challenge(wallet)` | `"challenge:{wallet}"` |
| `session(token)` | `"session:{token}"` |
| `solicitud_emisor(w)` | `"solicitud:emisor:{wallet}"` |

---

### `app/queue.py` — Publicación de tareas

`publicar_tarea(tarea)`: publica un mensaje JSON en la cola `mining_tasks` de RabbitMQ. Lo llama `chain.py` una vez por fragmento al formar un bloque.

---

### `app/results_consumer.py` — Consumidor de resultados

`iniciar_consumidor()`: escucha `mining_results` en RabbitMQ y llama a `sellar_bloque()` por cada resultado recibido. **No se llama desde `nct-api`** — lo ejecuta el servicio `nct-consumer` (`scripts/run_consumer.py`) para evitar duplicar consumidores.

---

### `worker/cpu/miner.py` — Worker de minado CPU

Función `minar(cadena, prefijo, nonce_min, nonce_max)`: itera nonces en el rango dado, computa `MD5(cadena + nonce)` y devuelve el primero que empiece con `prefijo`. Si no encuentra ninguno, devuelve `None`.

El marco de consumo/publicación en RabbitMQ está en `worker/common/consumer.py`.

---

### `static/index.html` — Frontend

Una sola página HTML con tres pantallas:

- **Login**: genera o recupera el par de claves ECDSA, registra la clave pública y hace el challenge-response.
- **Pendiente**: pantalla de espera mientras la solicitud de cine es votada. Polling cada 3s a `/estado_emisor`.
- **App**: interfaz principal diferenciada por rol.
  - **Cine**: solo puede emitir tokens a usuarios.
  - **Usuario**: puede hacer transferencias (a usuarios) y canjes (a cines, con dropdown de productos fijos).

**Partes clave:**
- `generarOCargarClaves()`: genera claves P-384 con WebCrypto o las recupera de `localStorage`.
- `conectarWallet()`: siempre re-registra la clave pública antes del challenge (maneja reinicios del servidor).
- `firmarChallenge()`: convierte la firma raw de WebCrypto a DER hex antes de enviarla.
- `refreshSaldoHeader()`: consulta `/balance` con el token de sesión y muestra el saldo en el header.
- `verificarDestino()`: llama `/tipo_wallet` al salir del campo destinatario para validar el tipo antes de enviar.

---

### `scripts/seed_genesis.py` — Inicialización

Siembra el bloque génesis en Redis con los emisores iniciales (`Hoyts_123`, `cinepolis_456`, `cinemark_789`), dificultad `"00"` y quórum 3.

Ejecutar tras cada `docker compose down -v`:
```bash
docker exec PopToken-nct-api python -m scripts.seed_genesis
```

---

## Levantar el sistema

```bash
cd Pilar2
docker compose up --build -d
docker exec PopToken-nct-api python -m scripts.seed_genesis
```

UI disponible en: `http://localhost:8888/ui`

Escalar workers:
```bash
docker compose up --scale worker-cpu=4 -d
```

Resetear todo:
```bash
docker compose down -v
docker compose up --build -d
docker exec PopToken-nct-api python -m scripts.seed_genesis
```
