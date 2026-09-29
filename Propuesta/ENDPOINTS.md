# PopToken — Endpoints del sistema

Listado completo de endpoints expuestos por los distintos componentes, con la URL pública
completa. Base de código: [Pilar2/nct/app/main.py](../Pilar2/nct/app/main.py).

URL pública base: `https://poptoken.34.122.53.67.nip.io`

---

## A. API REST — `nct-api`

| Método | URL completa | Auth | Qué representa |
|---|---|---|---|
| `POST` | `https://poptoken.34.122.53.67.nip.io/register` | No | Registra una wallet nueva: `{wallet, public_key}`. 409 si el nombre ya existe. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/challenge/{wallet}` | No | Genera un desafío aleatorio (válido 60s) para iniciar el login de esa wallet. 404 si no está registrada. |
| `POST` | `https://poptoken.34.122.53.67.nip.io/auth` | No | Login: `{wallet, signature}` — firma ECDSA del challenge. Devuelve `{token, wallet}`, sesión con TTL 1h en Redis. |
| `POST` | `https://poptoken.34.122.53.67.nip.io/tx` | **Sí** (Bearer) | Envía una transacción (`emision`/`transferencia`/`canje`). Valida estructura, emisor autorizado, saldo y anti-duplicado; la encola en `pool:pending`. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/balance/{wallet}` | **Sí** (Bearer) | Saldo de una wallet, calculado recorriendo la cadena confirmada + el pool pendiente (estilo UTXO). |
| `GET` | `https://poptoken.34.122.53.67.nip.io/tipo_wallet/{wallet}` | No | Indica si la wallet es `cine`, `usuario` o `desconocida`. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/chain` | No | Altura actual de la cadena + todos los bloques confirmados. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/block/{index}` | No | Un bloque puntual por índice. No valida `index` contra la altura actual — puede devolver bloques huérfanos tras un re-seed del genesis. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/pool` | No | Lista las transacciones pendientes (todavía sin minar). |
| `GET` | `https://poptoken.34.122.53.67.nip.io/status` | No | Resumen rápido: `{height, pending, redis}`. |
| `POST` | `https://poptoken.34.122.53.67.nip.io/block` | **Sin auth** | Fuerza la formación manual de un bloque desde el pool actual. Bypassea el lock distribuido de `auto_block.py` — usarlo mientras un bloque ya está en curso puede duplicar la formación. |
| `POST` | `https://poptoken.34.122.53.67.nip.io/solicitar_emisor` | **Sí** | La wallet autenticada pide ser emisor (cine) autorizado. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/solicitudes_emisor` | **Sí** | Lista todas las solicitudes de emisor pendientes de voto. |
| `POST` | `https://poptoken.34.122.53.67.nip.io/votar_emisor` | **Sí** | Un emisor ya autorizado vota `{wallet, voto}` sobre una solicitud. Al alcanzar quórum, encola la tx `autorizar_emisor`. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/estado_emisor/{wallet}` | **Sí** | Estado de una solicitud de emisor: `aprobado` / `pendiente` / `no_solicitado`. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/health` | No | `{redis: "ok"/"down", rabbitmq: "ok"/"down"}` — chequeo de dependencias. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/` | No | Redirect a `/ui`. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/ui` | No | Web UI estática de PopToken. |
| `GET` | `https://poptoken.34.122.53.67.nip.io/metrics` | No | Métricas Prometheus de `nct-api` en formato texto. |

---

## B. Endpoints de métricas por componente (internos, no públicos)

Cada proceso expone su propio `/metrics`, scrapeado por Prometheus vía auto-discovery
(anotaciones `prometheus.io/scrape`). Ninguno tiene URL de Internet — solo resuelven dentro
del cluster.

| Método | URL interna | Qué representa |
|---|---|---|
| `GET` | `http://nct-api:8888/metrics` | `nct_transactions_total{tipo,resultado}`, `nct_blocks_formed_total`, `nct_pool_size` |
| `GET` | `http://nct-consumer:8889/metrics` | `nct_blocks_sealed_total`, `nct_chain_height`, `nct_pool_size` |
| `GET` | `http://worker-cpu:8001/metrics` | `worker_tasks_processed_total`, `worker_tasks_won_total` |
| `GET` | `http://worker-gpu:8001/metrics` | Igual que `worker-cpu` (mismo código `common/consumer.py`). No scrapeado hoy: corre en otro cluster, sin anotaciones ni Prometheus federado. |

---

## C. UIs/APIs de infraestructura (no son código propio del proyecto)

| Método | URL completa | Auth | Qué representa |
|---|---|---|---|
| `GET` | `https://grafana.34.122.53.67.nip.io` | Login (Secret `grafana-admin`) | Dashboards de métricas; acceso anónimo deshabilitado. |
| `GET` | `http://prometheus:9090` (interno, requiere `kubectl port-forward` para verlo desde afuera) | Sin auth | TSDB + UI de consultas PromQL; no expuesto a Internet. |
| `GET` | `http://localhost:15672` (solo en Docker Compose local) | `guest`/`guest` | Management UI de RabbitMQ; en la nube no tiene Ingress ni Service público hacia el 15672. |

---

## Notas de seguridad relevantes

- `POST /block` y `GET /health` son los únicos endpoints de escritura/estado **sin ningún tipo
  de autenticación ni rate limiting** — `/block` en particular puede disparar efectos
  secundarios reales (formación de bloques duplicados) sin login.
- `GET /challenge/{wallet}` permite enumerar qué wallets existen (200 vs 404) sin límite de
  intentos.
- Ninguno de los endpoints de escritura (`/tx`, `/register`, `/auth`) tiene rate limiting.
