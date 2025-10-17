# GallagherMHP Command Platform - Backend

AI-assisted CRM + Deal Flow + Financial Screening + DD Suite for acquiring and operating 20+ unit mobile home parks in East Baton Rouge and Louisiana.

## Features

### Live Data Integrations
- **Socrata SODA v2** - EBR Open Data Property Information
- **ArcGIS REST** - EBRGIS Map Services
  - Tax Parcels
  - Adjudicated Parcels
  - Lot Boundaries
  - Zoning Districts
  - City Limits
  - 311 Service Requests

### Core Modules
1. **CRM & Lead Intelligence** - Owners, parks, leads, deals, pipeline tracking
2. **Deal Flow & Tasking** - Kanban pipeline with SLA timers
3. **Financial Screening** - DSCR, IRR, Cap Rate, scenario modeling, buy-box evaluation
4. **DD Command Center** - Louisiana/EBR-specific checklists, risk scoring
5. **Direct Mail + Heir Sourcing** - Campaign management with source attribution
6. **Parcel Overlay Service** - Spatial joins for zoning, adjudication, 311 density

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 16+ with PostGIS
- Redis 7+
- Docker & Docker Compose (recommended)

### Development Setup

1. **Clone and setup**
```bash
cd backend
cp .env.example .env
# Edit .env with your configuration
```

2. **Start services with Docker Compose**
```bash
docker-compose up -d
```

3. **Run database migrations**
```bash
docker-compose exec backend alembic upgrade head
```

4. **Access the application**
- API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs
- Metrics: http://localhost:8000/metrics

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis locally
# Then run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health & Status
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed health with DB/Redis/PostGIS status
- `GET /api/v1/data-catalog/health` - Data source health summary

### Parcels & Overlay
- `GET /api/v1/parcels/search` - Search parcels by address/owner/parcel_id
- `GET /api/v1/parcels/{parcel_uid}` - Get parcel details
- `GET /api/v1/parcels/{parcel_uid}/overlay` - Get comprehensive overlay (zoning, city, 311, adjudication)
- `GET /api/v1/parcels/adjudicated/list` - List adjudicated parcels
- `GET /api/v1/parcels/high-311/list` - Find parcels with high 311 density (blight indicator)

### CRM
- `POST /api/v1/crm/owners` - Create owner
- `GET /api/v1/crm/owners` - List owners
- `POST /api/v1/crm/parks` - Create park
- `GET /api/v1/crm/parks` - List parks
- `POST /api/v1/crm/leads` - Create lead
- `GET /api/v1/crm/leads` - List leads (filter by stage/source)
- `POST /api/v1/crm/deals` - Create deal
- `GET /api/v1/crm/deals` - List deals (filter by stage)
- `GET /api/v1/crm/pipeline/summary` - Pipeline summary by stage

### Financial Screening
- `POST /api/v1/financial/scenario/base` - Calculate base scenario
- `POST /api/v1/financial/scenario/stress` - Run stress scenarios
- `POST /api/v1/financial/buy-box/evaluate` - Evaluate against buy-box criteria
- `POST /api/v1/financial/pro-forma` - Generate multi-year pro forma with IRR
- `POST /api/v1/financial/quick-screen` - Comprehensive quick screen (all-in-one)

### Due Diligence
- `POST /api/v1/dd/checklists` - Create DD checklist for deal
- `GET /api/v1/dd/checklists/{checklist_id}` - Get checklist
- `GET /api/v1/dd/checklists/{checklist_id}/items` - Get checklist items
- `POST /api/v1/dd/items` - Create DD item
- `PATCH /api/v1/dd/items/{item_id}` - Update DD item

### Campaigns
- `POST /api/v1/campaigns` - Create campaign
- `GET /api/v1/campaigns` - List campaigns
- `GET /api/v1/campaigns/{campaign_id}` - Get campaign
- `PATCH /api/v1/campaigns/{campaign_id}/launch` - Launch campaign
- `GET /api/v1/campaigns/{campaign_id}/performance` - Get performance metrics

## Data Ingestion

### Manual Ingestion
```python
from app.jobs.data_ingestion import DataIngestionJob

# Run all ingestion jobs
await job.run_all()

# Or individual jobs
await job.ingest_property_info()
await job.ingest_zoning()
await job.ingest_311_requests()
```

### Scheduled Ingestion
Configure nightly job via Celery/Airflow (see `/backend/app/tasks/` for implementation).

## Financial Calculations

### Formulas Implemented
- **NOI** = EGI - OpEx (where EGI = Gross Income - Vacancy Loss)
- **DSCR** = NOI / Annual Debt Service
- **Debt Yield** = NOI / Loan Amount
- **Cap Rate** = NOI / Property Value
- **Cash-on-Cash** = Annual Cash Flow / Equity Invested
- **IRR** = IRR(Cash Flows over projection period)

### Buy-Box Defaults
- DSCR ≥ 1.25
- Debt Yield ≥ 10%
- Cap Rate ≥ 8%
- Price/Pad ≤ $15,000

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_financial_screening.py -v
```

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## External Data Sources

### Socrata (Open Data BR)
- **Base URL**: https://data.brla.gov/resource
- **Property Dataset**: re5c-hrw9
- **Docs**: https://dev.socrata.com/docs/queries/

### ArcGIS REST (EBRGIS)
- **Base URL**: https://maps.brla.gov/gis/rest/services/Cadastral
- **311 Base**: https://services.arcgis.com/KYvXadMcgf0K1EzK/arcgis/rest/services
- **Docs**: https://developers.arcgis.com/rest/

## Architecture

```
backend/
├── app/
│   ├── api/v1/endpoints/    # API route handlers
│   ├── connectors/          # External API connectors (Socrata, ArcGIS)
│   ├── core/                # Config, database, logging
│   ├── models/              # SQLAlchemy models
│   ├── services/            # Business logic services
│   └── jobs/                # Background jobs
├── alembic/                 # Database migrations
└── tests/                   # Test suite
```

## Security

- Secrets stored in environment variables (never commit .env)
- KMS-encrypted secrets in production
- Signed URLs for document access
- PII minimization and redaction outside CRM
- Rate limiting on external API connectors

## Observability

- **Metrics**: Prometheus endpoint at `/metrics`
- **Logging**: Structured JSON logging to stdout
- **Health**: `/health` and `/api/v1/data-catalog/health`
- **Data Quality**: Great Expectations checks on ingestion

## Production Deployment

See `/infrastructure/terraform/` for IaC templates (ECS/GKE deployment).

## License

Proprietary - Gallagher Property Company

