# Staging Environment Deployment

## Prerequisites

- Kubernetes cluster (GKE, EKS, or AKS)
- kubectl configured and authenticated
- Docker images pushed to registry
- PostgreSQL database provisioned (Cloud SQL, RDS, or Azure Database)
- Redis instance provisioned

## Setup

### 1. Create Namespace

```bash
kubectl apply -f namespace.yaml
```

### 2. Create Secrets

```bash
# Copy template
cp secrets.yaml.template secrets.yaml

# Edit secrets.yaml with base64-encoded values
# Generate SECRET_KEY:
openssl rand -hex 32 | base64

# Encode other values:
echo -n 'postgresql://user:pass@host:5432/db' | base64

# Apply secrets
kubectl apply -f secrets.yaml

# IMPORTANT: Do not commit secrets.yaml to git!
echo "secrets.yaml" >> .gitignore
```

### 3. Apply Configuration

```bash
kubectl apply -f configmap.yaml
```

### 4. Deploy Backend

```bash
kubectl apply -f backend-deployment.yaml
```

### 5. Deploy Ingress

```bash
# Ensure cert-manager is installed for TLS
kubectl apply -f ingress.yaml
```

### 6. Run Database Migrations

```bash
# Get backend pod name
kubectl get pods -n gallagher-mhp-staging

# Run migrations
kubectl exec -it <backend-pod> -n gallagher-mhp-staging -- alembic upgrade head
```

### 7. Create Admin User

```bash
# Copy create_admin_user.py to pod
kubectl cp ../../backend/scripts/create_admin_user.py <backend-pod>:/tmp/ -n gallagher-mhp-staging

# Run script
kubectl exec -it <backend-pod> -n gallagher-mhp-staging -- python /tmp/create_admin_user.py
```

## Verification

### Check Deployment Status

```bash
kubectl get all -n gallagher-mhp-staging
```

### Check Logs

```bash
kubectl logs -f deployment/gallagher-mhp-backend -n gallagher-mhp-staging
```

### Test Health Endpoints

```bash
curl https://api-staging.gallagher-mhp.com/health
curl https://api-staging.gallagher-mhp.com/api/v1/health/readiness
```

### Test Authentication

```bash
# Login
curl -X POST https://api-staging.gallagher-mhp.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your_password>"}'

# Use token
curl https://api-staging.gallagher-mhp.com/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

## Monitoring

### View Metrics

```bash
# Port forward Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n monitoring

# Access at http://localhost:9090
```

### View Logs

```bash
# Stream logs
kubectl logs -f deployment/gallagher-mhp-backend -n gallagher-mhp-staging --tail=100

# Search logs
kubectl logs deployment/gallagher-mhp-backend -n gallagher-mhp-staging | grep ERROR
```

## Scaling

```bash
# Scale replicas
kubectl scale deployment/gallagher-mhp-backend --replicas=3 -n gallagher-mhp-staging

# Enable autoscaling
kubectl autoscale deployment/gallagher-mhp-backend \
  --min=2 --max=10 --cpu-percent=70 \
  -n gallagher-mhp-staging
```

## Troubleshooting

### Pods Not Starting

```bash
kubectl describe pod <pod-name> -n gallagher-mhp-staging
kubectl logs <pod-name> -n gallagher-mhp-staging
```

### Database Connection Issues

```bash
# Test database connectivity from pod
kubectl exec -it <backend-pod> -n gallagher-mhp-staging -- \
  psql $DATABASE_URL -c "SELECT 1"
```

### Redis Connection Issues

```bash
# Test Redis connectivity
kubectl exec -it <backend-pod> -n gallagher-mhp-staging -- \
  python -c "from redis import from_url; r=from_url('$REDIS_URL'); print(r.ping())"
```

## Cleanup

```bash
# Delete all resources
kubectl delete namespace gallagher-mhp-staging
```

