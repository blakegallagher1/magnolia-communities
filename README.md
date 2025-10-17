# GallagherMHP Command Platform

**AI-Assisted CRM + Deal Flow + Financial Screening + DD Suite**  
Built for acquiring and operating 20+ unit mobile home parks in East Baton Rouge (and Louisiana).

---

## 🎯 Mission

Ship a production-ready, internal platform that combines:
- **Live East Baton Rouge data** (Socrata + ArcGIS REST)
- **Always-fresh mode** (auto-ingest with schema drift detection)
- **CRM & Deal Flow** (pipeline stages, tasks, campaigns)
- **Financial Screening** (DSCR, IRR, scenarios, buy-box)
- **DD Command Center** (Louisiana-specific checklists, risk scoring)
- **Direct Mail + Heir Sourcing** (campaign management)
- **Parcel Overlay** (spatial joins: zoning, 311, adjudication, city limits)

---

## 🚀 Features

### 1. Live Data Integrations
- **Socrata SODA v2** - EBR Property Information (`re5c-hrw9`)
- **ArcGIS REST** - EBRGIS Map Services
  - Tax Parcels
  - Adjudicated Parcels (tax-foreclosed)
  - Lot Boundaries
  - Zoning Districts
  - City Limits (Baker, Baton Rouge, Central, Zachary)
  - 311 Service Requests (blight, code, drainage)

### 2. Core Modules
| Module | Description |
|--------|-------------|
| **CRM** | Owners, parks, leads, deals, pipeline tracking |
| **Deal Flow** | Kanban pipeline with SLA timers, LOI/PSA tracking |
| **Financial Screening** | Cap Rate, DSCR, Debt Yield, IRR, scenario modeling, buy-box |
| **DD Center** | Louisiana/EBR checklists, risk scoring, document vault |
| **Direct Mail** | Campaign studio, heir sourcing, response capture |
| **Parcel Overlay** | Spatial joins for enrichment (zoning, 311 density, adjudication) |

### 3. Financial Modeling
- **Calculations**: NOI, DSCR, Debt Yield, Cap Rate, CoC, IRR
- **Stress Testing**: Rent ±$10–$50, Occupancy 70–95%, Expense +10–30%, Rate +200bps
- **Buy-Box Criteria**: Configurable (default: DSCR ≥1.25, DY ≥10%, Cap ≥8%, Price/Pad ≤$15K)
- **Pro Forma**: Multi-year projections with exit scenarios

### 4. Data Quality & Observability
- **Freshness Tracking**: Auto-check remote `updated_at`; trigger re-ingest if stale
- **Schema Drift**: Detect column changes; generate migrations; emit alerts
- **Health Dashboard**: Per-source status (healthy/degraded/failed)
- **Metrics**: Prometheus endpoint at `/metrics`
- **Logging**: Structured JSON logs

---

## 📋 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Node.js 20+
- PostgreSQL 16+ with PostGIS
- Redis 7+

### 1. Clone and Configure
```bash
git clone <repo>
cd magnolia-communities-1

# Backend
cd backend
cp .env.example .env
# Edit .env with your configuration

# Frontend
cd ../frontend
cp .env.example .env.local
```

### 2. Start with Docker Compose
```bash
docker-compose up -d
```

This starts:
- PostgreSQL with PostGIS (port 5432)
- Redis (port 6379)
- Backend API (port 8000)
- Frontend (port 3000)

### 3. Run Migrations
```bash
docker-compose exec backend alembic upgrade head
```

### 4. Access the Platform
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/api/docs
- **Metrics**: http://localhost:8000/metrics
- **Health**: http://localhost:8000/health

---

## 🏗️ Architecture

```
magnolia-communities-1/
├── backend/              # FastAPI + Python 3.12
│   ├── app/
│   │   ├── api/         # REST endpoints
│   │   ├── connectors/  # Socrata & ArcGIS clients
│   │   ├── models/      # SQLAlchemy ORM
│   │   ├── services/    # Business logic
│   │   └── jobs/        # Background jobs
│   ├── tests/           # Pytest suite
│   └── alembic/         # Database migrations
├── frontend/            # Next.js 14 + React + Tailwind
│   ├── src/app/        # App router pages
│   ├── src/components/ # React components
│   └── src/lib/        # API client
├── docker-compose.yml  # Local dev stack
└── README.md           # This file
```

### Tech Stack
- **Backend**: Python, FastAPI, SQLAlchemy, PostGIS, Redis
- **Frontend**: Next.js, React, TypeScript, Tailwind CSS
- **Data**: Postgres 16 + PostGIS, Redis
- **Pipelines**: Alembic (migrations), Pytest (testing)
- **Connectors**: Socrata SODA v2, ArcGIS REST
- **Observability**: Prometheus, structured JSON logs

---

## 📊 API Highlights

### Parcel Overlay Example
```bash
GET /api/v1/parcels/{parcel_uid}/overlay
```
Returns:
```json
{
  "parcel_uid": "abc123...",
  "site_address": "123 Main St",
  "owner_name": "John Doe",
  "zoning": {
    "zone_code": "R-1",
    "zone_name": "Residential Single-Family"
  },
  "city": {"city_name": "Baton Rouge"},
  "adjudicated": false,
  "sr_311_stats": {
    "total": 3,
    "open": 1,
    "by_type": {"Blight": 2, "Drainage": 1}
  }
}
```

### Financial Quick Screen
```bash
POST /api/v1/financial/quick-screen
```
Body:
```json
{
  "purchase_price": 800000,
  "pad_count": 40,
  "current_rent": 250,
  "occupancy_rate": 0.90,
  "operating_expenses": 35000,
  "property_tax": 8000,
  "insurance": 4000
}
```
Returns:
- Base scenario metrics
- Top 5 stress scenarios
- Buy-box pass/fail
- 5-year pro forma with IRR
- Recommendation: PASS or FAIL

---

## 🔧 Development

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Testing
```bash
cd backend
pytest --cov=app
```

### Migrations
```bash
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

---

## 📦 Data Ingestion

### Manual Trigger
```python
from app.jobs.data_ingestion import DataIngestionJob

await job.run_all()
```

### Scheduled (Nightly)
Configure via Celery/Airflow for nightly freshness checks and re-ingestion.

---

## 🎨 Modules in Detail

### 1. CRM & Lead Intelligence
- **Entities**: Owner, Park, Lead, Deal, Campaign, Touchpoint
- **Pipeline Stages**: Sourced → Contacted → LOI → DD → Closing → Stabilization → Exit
- **Smart Tags**: Parish, zoning, flood proximity, blight index, adjudicated flag, cap band

### 2. Financial Screening
- **Inputs**: Rent roll, OpEx, property tax, insurance, lender terms
- **Outputs**: Cap Rate, DSCR, Debt Yield, CoC, IRR, Value/Pad
- **Scenarios**: Rent ±$10–$50, Occupancy 70–95%, Expense +10–30%, Rate +200bps
- **Buy-Box**: Pass/fail with deltas

### 3. DD Command Center
- **Louisiana/EBR Checklist**: Title, utilities, zoning (EBRGIS), permits (MHP license), environmental (Phase I), flood/drainage, financials, physical, legal
- **Risk Scoring**: Weighted by item priority and risk level
- **File Vault**: S3 storage with metadata tracking
- **Status Flags**: Pending / Verified / Escrowed / Deferred

### 4. Direct Mail + Heir Sourcing
- **Campaign Studio**: 3–5 touch sequences/year
- **Merge Fields**: `[Owner_Name]`, `[Parcel_ID]`, `[Offer_Price]`
- **Heir Engine**: Pluggable skip-trace/probate feeds
- **Response Capture**: Auto-creates CRM leads with source attribution

### 5. Post-Close Ops (MVP)
- Rent roll manager (CSV import)
- Collections monitor
- Vendor log
- Insurance schedule
- RTO/Gift contract tracker

---

## 🔐 Security & Compliance
- **Secrets**: KMS-encrypted; never commit `.env`
- **PII Minimization**: Redact owner emails/phones outside CRM
- **Signed URLs**: Document access with expiration
- **Rate Limiting**: External API connectors with backoff
- **Least Privilege**: Service accounts with minimal permissions

---

## 📈 Metrics & Observability
- **Prometheus**: `/metrics` endpoint
- **Logs**: Structured JSON to stdout
- **Health Checks**: `/health` (basic), `/api/v1/data-catalog/health` (detailed)
- **Data Quality**: Great Expectations on ingestion
- **Alerts**: Slack/Email for schema drift, 311 surge, insurance renewal

---

## 🧪 Testing & Quality
- **Unit Tests**: Pytest with async support
- **Coverage**: > 80% target
- **Integration Tests**: Test database with fixtures
- **Financial Tests**: Verified DSCR, IRR, Cap Rate formulas
- **Data Quality**: Great Expectations checks

---

## 📚 External Data Sources

### Socrata (Open Data BR)
- **Portal**: https://data.brla.gov/
- **Property Info**: `https://data.brla.gov/resource/re5c-hrw9.json`
- **Docs**: https://dev.socrata.com/docs/queries/

### ArcGIS REST (EBRGIS)
- **Catalog**: https://maps.brla.gov/gis/rest/services/Cadastral
- **Services**:
  - Tax Parcels: `.../Cadastral/Tax_Parcel/MapServer/0`
  - Adjudicated: `.../Cadastral/Adjudicated_Parcel/MapServer/0`
  - Lot Lookup: `.../Cadastral/Lot_Lookup/MapServer/0`
  - Zoning: `.../Cadastral/Zoning/MapServer/0`
  - City Limits: `.../Governmental_Units/City_Limit/MapServer/0`
  - 311: `https://services.arcgis.com/KYvXadMcgf0K1EzK/...`

---

## 🚢 Production Deployment
- **Infrastructure**: Terraform (see `/infrastructure/terraform/`)
- **Platform**: ECS/GKE with containerized services
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana
- **Logging**: CloudWatch / Stackdriver
- **Backup**: Automated daily snapshots

---

## 📝 Acceptance Tests (MVP)
✅ Live queries return rows from each EBR endpoint  
✅ Schema recorded; `updated_at` tracked  
✅ `parcel_uid` traceable to raw source  
✅ Scenario stress recalculates DSCR/DY/IRR correctly  
✅ Overlay queries produce deterministic results  
✅ Mailer sends preview with correct merge fields (sandbox)  
✅ All secrets encrypted; no PII leakage in logs  

---

## 🤝 Contributing
This is an internal platform for Gallagher Property Company.

---

## 📄 License
Proprietary - Gallagher Property Company © 2025

---

## 🙏 Credits
Built in 2025 with:
- FastAPI, Next.js, PostgreSQL/PostGIS, Redis
- East Baton Rouge Open Data & EBRGIS
- Modern best practices for data pipelines, observability, and security

**Mission**: Acquire and operate 20+ unit mobile home parks efficiently with AI-assisted tooling and always-fresh Louisiana data.
