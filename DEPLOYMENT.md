# Deployment Guide

## Production Deployment

### Prerequisites
- AWS Account (or GCP for GKE)
- Terraform >= 1.6
- Docker
- kubectl (for Kubernetes deployments)

### Environment Variables

Create production `.env` files:

**Backend `.env`:**
```bash
DATABASE_URL=postgresql://user:pass@prod-db:5432/gallagher_mhp
REDIS_URL=redis://prod-redis:6379
SECRET_KEY=<generate-with-openssl-rand-hex-32>
ENVIRONMENT=production
SENTRY_DSN=<your-sentry-dsn>
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
S3_BUCKET_NAME=gallagher-mhp-docs-prod
SLACK_WEBHOOK_URL=<your-webhook>
```

**Frontend `.env.production`:**
```bash
NEXT_PUBLIC_API_URL=https://api.gallagher-mhp.com
```

### Deployment Steps

#### 1. Build Docker Images
```bash
# Backend
cd backend
docker build -t gallagher-mhp-backend:latest .

# Frontend
cd ../frontend
docker build -t gallagher-mhp-frontend:latest .
```

#### 2. Push to Registry
```bash
# Tag images
docker tag gallagher-mhp-backend:latest <registry>/gallagher-mhp-backend:latest
docker tag gallagher-mhp-frontend:latest <registry>/gallagher-mhp-frontend:latest

# Push
docker push <registry>/gallagher-mhp-backend:latest
docker push <registry>/gallagher-mhp-frontend:latest
```

#### 3. Deploy Infrastructure with Terraform
```bash
cd infrastructure/terraform

# Initialize
terraform init

# Plan
terraform plan -out=tfplan

# Apply
terraform apply tfplan
```

#### 4. Run Migrations
```bash
# SSH into backend container
kubectl exec -it <backend-pod> -- alembic upgrade head
```

#### 5. Verify Deployment
```bash
# Check health
curl https://api.gallagher-mhp.com/health

# Check data catalog
curl https://api.gallagher-mhp.com/api/v1/data-catalog/health
```

### Scheduled Jobs

Configure cron jobs or use a scheduler (Celery Beat, Airflow):

**Nightly Freshness Check (2 AM CT):**
```bash
0 2 * * * python -m app.tasks.freshness_job
```

**Weekly Data Quality Audit (Sunday 3 AM):**
```bash
0 3 * * 0 python -m app.tasks.data_quality_audit
```

### Monitoring

#### Prometheus Metrics
- Endpoint: `https://api.gallagher-mhp.com/metrics`
- Configure scraping in Prometheus config

#### Logs
- Backend: CloudWatch Logs / Stackdriver
- Frontend: CloudWatch Logs / Stackdriver
- Format: Structured JSON

#### Alerts
Configure alerts for:
- Data source failures (3+ consecutive)
- High 311 surge near target parcels
- Schema drift detection
- Insurance renewal reminders (30 days out)
- API error rate > 5%
- Response time > 2s (p95)

### Backup & Recovery

#### Database Backups
```bash
# Automated daily snapshots
pg_dump -h prod-db -U gallagher gallagher_mhp | gzip > backup-$(date +%Y%m%d).sql.gz

# Upload to S3
aws s3 cp backup-$(date +%Y%m%d).sql.gz s3://gallagher-mhp-backups/
```

#### Restore
```bash
# Download backup
aws s3 cp s3://gallagher-mhp-backups/backup-20250101.sql.gz .

# Restore
gunzip < backup-20250101.sql.gz | psql -h prod-db -U gallagher gallagher_mhp
```

### Scaling

#### Horizontal Scaling
- Backend API: 3-10 replicas (auto-scale on CPU > 70%)
- Frontend: 2-5 replicas (auto-scale on requests)

#### Vertical Scaling
- Backend: 2-4 vCPU, 4-8 GB RAM
- Database: 4-8 vCPU, 16-32 GB RAM
- Redis: 2 vCPU, 4 GB RAM

### Security Checklist

- [ ] All secrets in KMS/Secrets Manager
- [ ] TLS/SSL certificates installed
- [ ] CORS configured for production domains
- [ ] Rate limiting enabled (100 req/min per IP)
- [ ] Database backups automated
- [ ] Monitoring & alerting configured
- [ ] Log retention policy set (90 days)
- [ ] IAM roles follow least privilege
- [ ] Security groups restrict access
- [ ] VPC peering configured

### Rollback Procedure

If deployment fails:

1. **Revert to previous image:**
```bash
kubectl set image deployment/backend backend=<registry>/gallagher-mhp-backend:<previous-tag>
kubectl set image deployment/frontend frontend=<registry>/gallagher-mhp-frontend:<previous-tag>
```

2. **Rollback database migrations:**
```bash
kubectl exec -it <backend-pod> -- alembic downgrade -1
```

3. **Verify health:**
```bash
curl https://api.gallagher-mhp.com/health
```

### Support Contacts
- DevOps: devops@gallagher-property.com
- On-call: +1-XXX-XXX-XXXX
- Slack: #gallagher-mhp-alerts

