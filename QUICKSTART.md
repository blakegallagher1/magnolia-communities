# Quick Start Guide

Get the **GallagherMHP Command Platform** running locally in 5 minutes.

## Prerequisites

- Docker Desktop installed
- 8GB RAM available
- Ports 3000, 5432, 6379, 8000 free

## Step 1: Clone & Configure

```bash
cd /Users/gallagherpropertycompany/Desktop/magnolia-communities-1

# Backend config (optional - defaults work for local dev)
cd backend
cp .env.example .env

# Frontend config
cd ../frontend  
cp .env.example .env.local
```

## Step 2: Start Services

```bash
# From project root
docker-compose up -d
```

This starts:
- ✅ PostgreSQL 16 + PostGIS (port 5432)
- ✅ Redis 7 (port 6379)
- ✅ Backend API (port 8000)
- ✅ Frontend (port 3000)

## Step 3: Initialize Database

```bash
# Run migrations
docker-compose exec backend alembic upgrade head
```

## Step 4: Access the Platform

Open in your browser:

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/api/docs
- **API Health**: http://localhost:8000/health
- **Data Health**: http://localhost:8000/api/v1/data-catalog/health

## Step 5: Try It Out

### Search Parcels
```bash
curl "http://localhost:8000/api/v1/parcels/search?address=Capitol&limit=5"
```

### Run Financial Screen
```bash
curl -X POST "http://localhost:8000/api/v1/financial/quick-screen" \
  -H "Content-Type: application/json" \
  -d '{
    "purchase_price": 800000,
    "pad_count": 40,
    "current_rent": 250,
    "occupancy_rate": 0.90,
    "operating_expenses": 35000,
    "property_tax": 8000,
    "insurance": 4000,
    "loan_ltv": 0.75,
    "interest_rate": 0.07,
    "term_years": 30
  }'
```

### Create a Park
```bash
curl -X POST "http://localhost:8000/api/v1/crm/parks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test MHP",
    "address": "123 Main St",
    "city": "Baton Rouge",
    "state": "LA",
    "pad_count": 40,
    "lot_rent": 250
  }'
```

## Useful Commands

```bash
# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart a service
docker-compose restart backend

# Run backend shell
docker-compose exec backend /bin/sh

# Run tests
docker-compose exec backend pytest

# Generate migration
docker-compose exec backend alembic revision --autogenerate -m "description"
```

## Using the Makefile

```bash
make up       # Start all services
make down     # Stop services
make logs     # View logs
make test     # Run tests
make help     # Show all commands
```

## Troubleshooting

### Port Already in Use
```bash
# Check what's using ports
lsof -i :8000
lsof -i :3000
lsof -i :5432

# Kill process or change port in docker-compose.yml
```

### Database Connection Error
```bash
# Check Postgres is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Restart Postgres
docker-compose restart postgres
```

### Frontend Can't Connect to API
```bash
# Check NEXT_PUBLIC_API_URL in frontend/.env.local
# Should be: http://localhost:8000

# Restart frontend
docker-compose restart frontend
```

## Next Steps

1. **Explore API**: http://localhost:8000/api/docs
2. **Read Backend README**: `backend/README.md`
3. **Check Data Sources**: Configure Socrata/ArcGIS tokens (optional)
4. **Run Data Ingestion**: See `backend/app/jobs/data_ingestion.py`
5. **Customize Buy-Box**: Adjust criteria in financial endpoints

## Live Data Integration

### Optional: Configure API Tokens

For higher rate limits, add to `backend/.env`:

```bash
# Socrata (optional - public data works without token)
SOCRATA_APP_TOKEN=your-token-here

# ArcGIS (optional for authenticated services)
ARCGIS_CLIENT_ID=your-client-id
ARCGIS_CLIENT_SECRET=your-secret
```

### Test Live Data Queries

```bash
# Property information from Socrata
curl "http://localhost:8000/api/v1/parcels/search?address=Capitol"

# Adjudicated parcels
curl "http://localhost:8000/api/v1/parcels/adjudicated/list?limit=10"

# High 311 density (blight indicator)
curl "http://localhost:8000/api/v1/parcels/high-311/list?threshold=5"
```

## Production Deployment

See `DEPLOYMENT.md` for production setup with:
- AWS/GCP infrastructure
- CI/CD pipelines
- Monitoring & alerting
- Backup & recovery
- Scaling configuration

---

**Need Help?** Check the full README.md or backend/README.md for detailed documentation.

