# PopToken — Arquitectura del despliegue (Pilar 3)

Diagrama del estado actual: blockchain distribuida desplegada en **dos clusters Kubernetes**,
con minería distribuida y tolerancia a fallos.

```
                                  INTERNET
                                     │
                  ┌──────────────────┼───────────────────────┐
                  │ HTTPS (:443)     │ AMQP (:5672)          │
                  │ navegador        │ inter-cluster         │
                  ▼                  ▼                       │
   ╔════════════════════════════════════════════════╗        │
   ║   CLUSTER GKE  (proyecto blockchain-tp)        ║        │
   ║   GKE Standard · us-central1-a                 ║        │
   ║                                                ║        │
   ║   ┌────────────────────────────────────────┐   ║        │
   ║   │ Ingress nginx  (LB 34.122.53.67)       │   ║        │
   ║   │  TLS cert autofirmado (Secret nct-tls) │   ║        │
   ║   └───────────────────┬────────────────────┘   ║        │
   ║                       │ /  → nct-api           ║        │
   ║   ┌───────────── nodegroup APPS ───────────┐   ║        │
   ║   │                   ▼                    │   ║        │
   ║   │   ┌─────────────────────────────┐      │   ║        │
   ║   │   │ nct-api  (Deployment ×2)    │      │   ║        │
   ║   │   │  FastAPI + Web UI (/ui)     │      │   ║        │
   ║   │   │  POST /tx /block · GET ...  │      │   ║        │
   ║   │   │  /metrics (:8888)           │      │   ║        │
   ║   │   └──────┬───────────────┬──────┘      │   ║        │
   ║   │          │               │             │   ║        │
   ║   │   ┌───────────────┐  ┌──────────────┐  │   ║        │
   ║   │   │ nct-consumer  │  │ worker-cpu   │  │   ║        │
   ║   │   │ (Deploy ×2)   │  │ (Deploy +HPA)│  │   ║        │
   ║   │   │ sella bloques │  │ minero CPU   │  │   ║        │
   ║   │   │ + auto-bloque │  │ (respaldo)   │  │   ║        │
   ║   │   │ (lock Redis)  │  │ /metrics     │  │   ║        │
   ║   │   │ /metrics(:8889│  │ (:8001)      │  │   ║        │
   ║   │   └──┬─────────┬──┘  └──────┬───────┘  │   ║        │
   ║   │      │         │            │          │   ║        │
   ║   │   ┌──────────────────────────────────┐ │   ║        │
   ║   │   │ grafana  (Deployment ×1)         │ │   ║        │
   ║   │   │  dashboard de métricas           │ │   ║        │
   ║   │   │  LB → IP pública (:3000)         │ │   ║        │
   ║   │   └──────────────────────────────────┘ │   ║        │
   ║   └──────┼─────────┼────────────┼──────────┘   ║        │
   ║          │         │            │              ║        │
   ║   ┌──────┼─────────┼────────────┼───────────┐  ║        │
   ║   │      ▼ nodegroup INFRA      ▼           │  ║        │
   ║   │  ┌──────────┐  ┌──────────┐  ┌───────┐  │  ║        │
   ║   │  │  Redis   │  │RabbitMQ  │  │Promet.│  │  ║        │
   ║   │  │ StatefulS│  │StatefulS │  │Deploy │  │  ║        │
   ║   │  │ 1 + PVC  │  │ 3 réplicas  │1+PVC  │  │  ║        │
   ║   │  │ (cadena, │  │ cluster  │  │10Gi   │  │  ║        │
   ║   │  │  saldos) │  │classic   │  │(:9090)│  │  ║        │
   ║   │  │ AOF      │  │config    │◄─┼───────┘  │  ║        │
   ║   │  └──────────┘  └──────────┘  │  scrape  │  ║        │
   ║   │                    ▲         │  pods    │  ║        │
   ║   │                    └─────────┘          │  ║        │
   ║   │              Service LoadBalancer        │  ║        │
   ║   │              rabbitmq-external           │  ║        │
   ║   │              (35.222.70.5:5672)◄─────────┼──╬────────┘
   ║   └─────────────────────────────────────────┘  ║
   ╚════════════════════════════════════════════════╝
                          ▲
                          │ AMQP por internet
                          │ (consume mining_tasks,
                          │  publica mining_results)
   ╔══════════════════════╪═════════════════════════╗
   ║  CLUSTER DEL PROFE (k3s)  ·  namespace g-la-25 ║
   ║                      │                         ║
   ║   ┌──────────────────┴───────────────────┐     ║
   ║   │  worker-gpu  (Deployment)            │     ║
   ║   │   minero CUDA (limites_gpu, sm_61)   │     ║
   ║   │   resources: nvidia.com/gpu: 1       │     ║
   ║   │   GPU: GeForce GTX 1050              │     ║
   ║   └──────────────────────────────────────┘     ║
   ╚════════════════════════════════════════════════╝
```

## Flujo de una transacción (ciclo completo)

```
1. Usuario (navegador) ─POST /tx──────────► nct-api
                                              │ valida (estructura, saldo,
                                              │ emisor, anti-duplicado)
                                              ▼
                                          Redis: pool:pending

2. nct-consumer (cada 30s, con lock) ─────► forma bloque desde el pool
                                              │ guarda block:pending:N
                                              ▼
                                   RabbitMQ: mining_tasks
                                   (N fragmentos de rango de nonce)

3. workers (gpu del profe / cpu del GKE) ─► minan PoW (MD5 + nonce)
                                              │ el que encuentra publica
                                              ▼
                                   RabbitMQ: mining_results

4. nct-consumer ──────────────────────────► verifica el PoW (recalcula hash)
                                              │ sella atómico (MULTI/EXEC):
                                              │ block:N, sube height,
                                              │ borra pending, vacía pool
                                              ▼
                                          Redis: cadena (block:1..N)
```

## Componentes y rol

| Componente | Dónde | Rol | Réplicas / HA |
|---|---|---|---|
| **Ingress nginx** | GKE | Entrada HTTPS pública | LoadBalancer |
| **nct-api** | GKE / apps | API REST + Web UI + `/metrics` (:8888) | 2 réplicas |
| **nct-consumer** | GKE / apps | Sella bloques + auto-formación (lock distribuido) + `/metrics` (:8889) | 2 réplicas |
| **worker-cpu** | GKE / apps | Minero CPU (respaldo elástico) + `/metrics` (:8001) | HPA 1–6 |
| **Redis** | GKE / infra | Estado: cadena, saldos, pool | 1 + PVC (reschedule) |
| **RabbitMQ** | GKE / infra | Colas de PoW (tasks/results) | 3 réplicas (classic_config peer discovery) |
| **Prometheus** | GKE / infra | Recolección de métricas (scrape por anotaciones) | 1 + PVC 10Gi |
| **Grafana** | GKE / apps | Visualización de métricas | 1 + LoadBalancer |
| **worker-gpu** | Cluster profe | Minero CUDA (primario) | 1 + GPU |

## Tolerancia a fallos

- **nct-api / nct-consumer**: ≥2 réplicas → si cae un pod/nodo, el otro responde.
- **Redis**: StatefulSet + PVC → si cae el nodo, K8s reprograma y re-monta el disco (sin perder la cadena).
- **Minería**: si el worker-gpu (profe) no está disponible, el worker-cpu (GKE) mina igual → la cadena no se frena.
- **Auto-formación de bloques**: lock distribuido en Redis → con 2 réplicas de consumer, solo una forma cada bloque (sin duplicados); si la que tiene el lock cae, otra lo toma.

## Monitoring (Prometheus + Grafana)

- **Prometheus** corre en `infra-pool`, scrapea métricas cada 15s usando auto-discovery por anotaciones (`prometheus.io/scrape: "true"`).
- **Grafana** expone dashboard en IP pública (LoadBalancer `:3000`). Datasource: `http://prometheus:9090`.

| Componente | Puerto métricas | Métricas expuestas |
|---|---|---|
| nct-api | `:8888/metrics` | `nct_transactions_total`, `nct_blocks_formed_total`, `nct_pool_size` |
| nct-consumer | `:8889` | `nct_blocks_sealed_total`, `nct_chain_height`, `nct_pool_size` |
| worker-cpu | `:8001` | `worker_tasks_processed_total`, `worker_tasks_won_total` |

---

## Seguridad

- **HTTPS** (cert autofirmado) en el Ingress — necesario para `crypto.subtle` de las wallets.
- **Credenciales de RabbitMQ** en Secrets de K8s (no hardcodeadas).
- **OIDC / Workload Identity** para el CI/CD (sin claves estáticas en GitHub).
- **RabbitMQ inter-cluster**: usuario/password + (pendiente) restringir IP de origen.

## CI/CD (GitHub Actions)

- `p3-1-cluster` — Terraform: cluster GKE + node pools.
- `p3-2-infra` — Redis + RabbitMQ.
- `p3-3-apps` — build/push imágenes (Artifact Registry) + deploy apps. Auth por OIDC.
- `p3-4-worker-gpu` — (pendiente) deploy del worker GPU al cluster del profe.
