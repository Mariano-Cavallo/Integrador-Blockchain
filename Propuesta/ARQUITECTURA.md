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
   ║   │   └──────┬───────────────┬──────┘      │   ║        │
   ║   │          │               │             │   ║        │
   ║   │   ┌───────────────┐  ┌──────────────┐  │   ║        │
   ║   │   │ nct-consumer  │  │ worker-cpu   │  │   ║        │
   ║   │   │ (Deploy ×2)   │  │ (Deploy +HPA)│  │   ║        │
   ║   │   │ sella bloques │  │ minero CPU   │  │   ║        │
   ║   │   │ + auto-bloque │  │ (respaldo)   │  │   ║        │
   ║   │   │  (lock Redis) │  │              │  │   ║        │
   ║   │   └──┬─────────┬──┘  └──────┬───────┘  │   ║        │
   ║   └──────┼─────────┼────────────┼──────────┘   ║        │
   ║          │         │            │              ║        │
   ║   ┌──────┼─────────┼────────────┼───────────┐  ║        │
   ║   │      ▼ nodegroup INFRA      ▼           │  ║        │
   ║   │  ┌──────────┐      ┌────────────────┐   │  ║        │
   ║   │  │  Redis   │      │   RabbitMQ     │   │  ║        │
   ║   │  │ StatefulS│      │  StatefulSet   │   │  ║        │
   ║   │  │ 1 + PVC  │      │  1 réplica*    │◄──┼──┼────────┘
   ║   │  │ (cadena, │      │  colas:        │   │  ║   Service LoadBalancer
   ║   │  │  saldos) │      │  mining_tasks  │   │  ║   rabbitmq-external
   ║   │  │ AOF      │      │  mining_results│   │  ║   (35.222.70.5:5672)
   ║   │  └──────────┘      │  (quorum qs)   │   │  ║
   ║   │                    └────────────────┘   │  ║
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

   (*) RabbitMQ en 1 réplica standalone por incompatibilidad
       RabbitMQ 3.13 + GKE 1.35 en el clustering. Pendiente:
       3 réplicas con RabbitMQ Cluster Operator (consultado al profe).
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
| **nct-api** | GKE / apps | API REST + Web UI | 2 réplicas |
| **nct-consumer** | GKE / apps | Sella bloques + auto-formación (lock distribuido) | 2 réplicas |
| **worker-cpu** | GKE / apps | Minero CPU (respaldo elástico) | HPA 1–6 |
| **Redis** | GKE / infra | Estado: cadena, saldos, pool | 1 + PVC (reschedule) |
| **RabbitMQ** | GKE / infra | Colas de PoW (tasks/results) | 1 standalone* |
| **worker-gpu** | Cluster profe | Minero CUDA (primario) | 1 + GPU |

## Tolerancia a fallos

- **nct-api / nct-consumer**: ≥2 réplicas → si cae un pod/nodo, el otro responde.
- **Redis**: StatefulSet + PVC → si cae el nodo, K8s reprograma y re-monta el disco (sin perder la cadena).
- **Minería**: si el worker-gpu (profe) no está disponible, el worker-cpu (GKE) mina igual → la cadena no se frena.
- **Auto-formación de bloques**: lock distribuido en Redis → con 2 réplicas de consumer, solo una forma cada bloque (sin duplicados); si la que tiene el lock cae, otra lo toma.

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
