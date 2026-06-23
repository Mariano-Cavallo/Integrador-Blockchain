# Pilar 3 — Estado actual (contexto para continuar)

> Documento de traspaso. Última actualización: 2026-06-23.
> Resume dónde quedó el Pilar 3 para poder continuar desde cualquier máquina.

## Qué es el Pilar 3

Desplegar PopToken (Pilar 2, ya completo y dockerizado) en **GKE** con **tolerancia a fallos**
(requisito central: si cae cualquier nodo, la app sigue). IaC con Terraform, CI/CD con GitHub Actions.

## Arquitectura: DOS clusters

- **Cluster GKE** (`blockchain-cluster`, proyecto compartido `blockchain-tp`): corre TODO menos los mineros GPU.
  - nodegroup `infra`: Redis + RabbitMQ (2 nodos).
  - nodegroup `apps`: nct-api, nct-consumer, worker-cpu (≥2 réplicas).
  - LoadBalancer público para la UI/API y para RabbitMQ.
- **Cluster del PROFE** (tiene GPUs): correrá los workers GPU (minero CUDA del Pilar 1),
  conectándose al RabbitMQ del GKE vía su IP pública.

## Estado de las fases

| Fase | Estado |
|---|---|
| 0 — Prep GCP (proyecto, billing, APIs, Artifact Registry, OIDC) | ✅ (lo hizo mayormente el compañero) |
| 1 — Cluster GKE (Terraform `Pilar3/tofu/cluster/`) | ✅ creado y corriendo |
| 2 — Redis + RabbitMQ (`Pilar3/k8s/infra/`) | 🟡 Redis OK, **RabbitMQ bloqueado** (ver abajo) |
| 3 — Apps (`Pilar3/k8s/apps/`) | ✅ manifiestos escritos, sin desplegar aún |
| 4 — Worker GPU en cluster del profe | ⬜ pendiente |
| 5 — Pruebas de carga + informe | ⬜ pendiente |

## 🚨 BLOQUEANTE ACTUAL: RabbitMQ no forma cluster en GKE

**Síntoma:** los pods de RabbitMQ crashean al boot (`BOOT FAILED — error:{badkey,<<"hostname">>}`),
o arrancan pero cada uno forma un cluster de 1 nodo en vez de unirse.

**Causa raíz:** incompatibilidad entre **RabbitMQ 3.13** (imagen `rabbitmq:3-management`) y
**Kubernetes 1.35** (la versión de GKE). El peer discovery `rabbit_peer_discovery_k8s` espera el
campo `hostname` en los endpoints, que K8s 1.35 ya no popula igual (usa EndpointSlice).
Con `address_type=hostname` da `badkey`; con `address_type=ip` bootea pero el nodename (por hostname)
no coincide con lo que descubre (por ip) y no se unen.

**Ya probado sin éxito:** `publishNotReadyAddresses: true`, `subdomain: rabbitmq-headless`,
ambos `address_type`, recreación limpia de PVCs.

**SOLUCIÓN PENDIENTE — esperando respuesta del profe:**
Consultar si se puede usar el **RabbitMQ Cluster Operator** (oficial de Broadcom/VMware). Resuelve el
problema de raíz porque usa un mecanismo de clustering compatible con K8s moderno. Se instala con un
`kubectl apply` del manifiesto oficial y el cluster se define con un recurso `RabbitmqCluster` (replicas: 3).
- Si el profe dice **SÍ** → instalar operador + recurso RabbitmqCluster de 3 réplicas (HA real).
- Si dice **NO** → Plan B: RabbitMQ a **1 réplica + PVC** (como Redis); la tolerancia la da el reschedule.

## Datos clave del entorno

- **Proyecto GCP:** `blockchain-tp` (compartido, billing activo). Usuario tiene rol Owner.
- **Cluster:** `blockchain-cluster`, zona `us-central1-a`.
- **Artifact Registry:** `us-central1-docker.pkg.dev/blockchain-tp/blockchain-registry`
- **OIDC (Workload Identity):** provider `projects/674993689697/locations/global/workloadIdentityPools/github-pool/providers/github-provider`, SA `github-actions@blockchain-tp.iam.gserviceaccount.com`. Atado al repo `Mariano-Cavallo/Integrador-Blockchain`.
- **Repo:** `Mariano-Cavallo/Integrador-Blockchain`.
- Requiere `gke-gcloud-auth-plugin` instalado para que kubectl conecte (instalar con `gcloud components install gke-gcloud-auth-plugin` como admin).

## Conectarse al cluster (desde cualquier PC)

```powershell
gcloud auth login
gcloud config set project blockchain-tp
gcloud container clusters get-credentials blockchain-cluster --zone us-central1-a
kubectl get pods
```

## Estado de los nodos (ahorro de crédito)

Hoy se desactivó el autoscaling del `apps-pool` para apagar nodos. Quedaron ~2 nodos corriendo
(gasto mínimo). Para **reactivar como define el Terraform**:

```powershell
gcloud container clusters update blockchain-cluster --enable-autoscaling --node-pool apps-pool --min-nodes 2 --max-nodes 4 --zone us-central1-a
gcloud container clusters resize blockchain-cluster --node-pool infra-pool --num-nodes 2 --zone us-central1-a --quiet
```

## Secuencia de despliegue (cuando se resuelva RabbitMQ)

```powershell
# 1. cluster ya existe (NO recrear). Conectar kubectl (ver arriba).

# 2. Secret de credenciales de RabbitMQ (valores SIN tildes ni @ : / ):
kubectl create secret generic rabbitmq-credentials `
  --from-literal=RABBITMQ_DEFAULT_USER=poptoken `
  --from-literal=RABBITMQ_DEFAULT_PASS=<password-fuerte> `
  --from-literal=RABBITMQ_ERLANG_COOKIE=<cookie-larga>

# 3. infra (Redis + RabbitMQ)
kubectl apply -f Pilar3\k8s\infra\

# 4. Secret con la URL de RabbitMQ para las apps (mismo password del paso 2)
kubectl create secret generic nct-rabbitmq-url `
  --from-literal=RABBITMQ_URL="amqp://poptoken:<password>@rabbitmq:5672/"

# 5. apps (reemplazando el placeholder de imagen, o vía el workflow p3-3-apps)
#    El workflow p3-3-apps hace build+push+deploy automaticamente (necesita GitHub Secret RABBITMQ_PASS).
```

## Pendientes varios

- Crear el **GitHub Secret `RABBITMQ_PASS`** (Settings → Secrets → Actions) para el workflow p3-3-apps.
- `loadBalancerSourceRanges` del Service `rabbitmq-external`: hoy en `0.0.0.0/0` (placeholder).
  Reemplazar por la IP de salida del cluster del profe cuando se tenga.
- Worker GPU (Fase 4): Dockerfile con CUDA + binario del Pilar 1 + manifiesto para el cluster del profe.
- Workflows: existen `p3-1-cluster`, `p3-2-infra`, `p3-3-apps`. Falta `p3-4-worker-gpu`.

## Coordinación de equipo

- El compañero maneja el Terraform del cluster. **No correr `terraform apply` sin coordinar** (no duplicar cluster).
- Trabajar en ramas separadas + PRs para no pisarse.
- En paralelo, los compañeros pueden ir con: informe + scripts de carga + gráficas + video + diagramas + worker GPU.
