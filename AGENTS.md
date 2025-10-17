# GallagherMHP AI Agents Strategy

## Overview

This document defines the AI agent architecture for the GallagherMHP Command Platform. Each agent is designed to automate specific tasks in the mobile home park acquisition workflow, from initial sourcing to final due diligence.

**Core Philosophy**: Human-in-the-loop automation that amplifies analyst capabilities while maintaining control over critical decisions.

---

## Table of Contents

1. [Agent Architecture](#agent-architecture)
2. [Deal Sourcing Agents](#deal-sourcing-agents)
3. [Financial Analysis Agents](#financial-analysis-agents)
4. [Due Diligence Agents](#due-diligence-agents)
5. [CRM & Outreach Agents](#crm--outreach-agents)
6. [Data Quality Agents](#data-quality-agents)
7. [Reporting & Intelligence Agents](#reporting--intelligence-agents)
8. [Implementation Roadmap](#implementation-roadmap)

---

## Agent Architecture

### Design Principles

1. **Composability**: Agents are modular and can be chained together
2. **Observability**: All agent actions are logged with structured metadata
3. **Reversibility**: Critical actions require human approval
4. **Context-Aware**: Agents leverage full deal context from Postgres/Redis
5. **Self-Improving**: Agents log performance metrics for continuous refinement

### Technology Stack

- **Orchestration**: LangChain / LangGraph for agent workflows
- **LLM Provider**: OpenAI GPT-4 / Anthropic Claude (configurable)
- **Vector Store**: Pinecone / Weaviate for semantic search over documents
- **Memory**: Redis for short-term agent state, Postgres for long-term
- **Tool Integration**: FastAPI endpoints exposed as tools to agents
- **Observability**: LangSmith / Weights & Biases for tracing

### Base Agent Template

```python
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import StructuredTool
from langchain_openai import ChatOpenAI
from app.core.logging import get_logger

logger = get_logger(__name__)

class BaseGallagherAgent:
    """Base class for all GallagherMHP agents."""
    
    def __init__(self, agent_name: str, temperature: float = 0.0):
        self.agent_name = agent_name
        self.llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=temperature)
        self.tools = self._register_tools()
        self.agent = self._create_agent()
        
    def _register_tools(self) -> list[StructuredTool]:
        """Override in subclass to register agent-specific tools."""
        raise NotImplementedError
        
    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent with registered tools."""
        # Implementation here
        pass
        
    async def execute(self, task: str, context: dict) -> dict:
        """Execute agent task with context."""
        logger.info(f"Agent {self.agent_name} executing task", extra={
            "agent": self.agent_name,
            "task": task,
            "context_keys": list(context.keys())
        })
        result = await self.agent.ainvoke({"input": task, "context": context})
        logger.info(f"Agent {self.agent_name} completed task", extra={
            "agent": self.agent_name,
            "result_keys": list(result.keys())
        })
        return result
```

---

## Deal Sourcing Agents

### 1. **Parcel Hunter Agent**

**Purpose**: Continuously scan parcel data to identify mobile home park candidates in target markets.

**Tools**:
- `search_parcels_by_criteria`: Query PostGIS for parcels matching size/zoning
- `get_property_characteristics`: Fetch detailed parcel metadata
- `check_311_service_requests`: Analyze complaint density as proxy for condition
- `calculate_walkability_score`: Assess location quality
- `save_lead`: Create CRM lead record

**Workflow**:
```
1. Query parcels in East Baton Rouge with land_use = "Mobile Home Park"
2. Filter for 20+ unit parks (estimate from acreage × density heuristic)
3. For each candidate:
   a. Fetch 311 service request history (5-year window)
   b. Calculate proximity to amenities (grocery, schools, highways)
   c. Assess flood zone risk from FEMA data
   d. Score lead (0-100) based on weighted criteria
4. Save top 20% as leads with detailed reasoning
5. Notify analyst via Slack/email with ranked list
```

**Prompt Template**:
```
You are a real estate analyst specializing in mobile home park acquisitions.

Task: Evaluate whether parcel {parcel_id} at {address} is a viable acquisition target.

Criteria:
- Minimum 20 units (estimate from {acreage} acres × 8 units/acre)
- Low 311 complaint density (< 2 per unit per year)
- Not in 100-year floodplain
- Within 2 miles of grocery store
- Zoning permits manufactured housing

Available Tools: {tool_names}

Return:
- score (0-100)
- reasoning (2-3 sentences)
- recommendation (PURSUE, MONITOR, PASS)
```

**Scheduling**: Runs daily at 6 AM, processes new parcels added in last 24h.

---

### 2. **Market Intelligence Agent**

**Purpose**: Aggregate macro trends in the Louisiana mobile home park market.

**Data Sources**:
- Recent sales comps from CoStar/Crexi APIs
- Louisiana Manufactured Housing Association updates
- Census demographic shifts
- State housing policy changes

**Tools**:
- `fetch_recent_sales_comps`: Pull sales data from external APIs
- `analyze_demographic_trends`: Query Census API for population/income shifts
- `scrape_industry_news`: Monitor LMHA, MHInsider for policy updates
- `generate_market_report`: Compile findings into structured report

**Workflow**:
```
1. Fetch all mobile home park sales in Louisiana (last 90 days)
2. Calculate median cap rate, price per unit, NOI trends
3. Query Census API for East Baton Rouge:
   a. Population growth rate
   b. Median household income changes
   c. Renter vs. owner-occupied trends
4. Scan industry news for regulatory changes (rent control, zoning)
5. Generate executive summary with key insights and implications
6. Store in data catalog for analyst access
```

**Scheduling**: Runs weekly on Monday morning.

---

## Financial Analysis Agents

### 3. **Underwriting Autopilot Agent**

**Purpose**: Automatically generate T12 pro forma and sensitivity analyses for new deals.

**Tools**:
- `fetch_property_financials`: Retrieve income/expense data from CRM
- `calculate_noi`: Compute net operating income
- `calculate_dscr`: Debt service coverage ratio
- `calculate_debt_yield`: Debt yield for lender approval
- `calculate_irr`: Internal rate of return with exit scenario
- `stress_test_assumptions`: Run downside scenarios (vacancy +10%, opex +15%)
- `compare_to_portfolio`: Benchmark against existing deals

**Workflow**:
```
1. Extract T12 income statement from uploaded PDF (OCR + GPT-4V)
2. Normalize line items to standardized chart of accounts
3. Calculate baseline metrics:
   - EGI = Gross Rent - Vacancy
   - NOI = EGI - OpEx
   - Cap Rate = NOI / Purchase Price
   - DSCR = NOI / Annual Debt Service
   - Cash-on-Cash = Net Cash Flow / Equity
4. Run 5 stress scenarios:
   - Base Case
   - Downside (vacancy +10%, opex +15%, rent +0%)
   - Upside (fill to 95%, rent +3%/yr)
   - Interest Rate Shock (+2% on refinance)
   - Major Capex (roof/roads = $150k)
5. Generate 10-year IRR waterfall with Year 5 exit assumption
6. Flag deal as GREEN/YELLOW/RED based on thresholds:
   - GREEN: DSCR > 1.25, Cash-on-Cash > 8%, IRR > 15%
   - YELLOW: DSCR 1.15-1.25, Cash-on-Cash 6-8%, IRR 12-15%
   - RED: Below YELLOW thresholds
7. Generate PDF report with charts and email to analyst
```

**Prompt Template**:
```
You are a real estate financial analyst. Underwrite this mobile home park deal:

Property: {property_name}
Address: {address}
Units: {num_units}
Purchase Price: ${purchase_price:,.0f}
Loan Terms: {loan_amount:,.0f} at {interest_rate}% for {term_years} years

T12 Financials:
{financials_json}

Tasks:
1. Validate financials for completeness and reasonableness
2. Calculate NOI, Cap Rate, DSCR, Debt Yield, Cash-on-Cash, IRR
3. Identify any red flags (e.g., abnormally low maintenance, inflated occupancy)
4. Recommend BID or PASS with detailed justification

Use financial_screening tools to compute metrics. Be conservative in assumptions.
```

**Human Review Gates**:
- Analyst must approve final bid amount
- Flagged deals (RED) require mandatory review before proceeding
- All assumptions (exit cap, rent growth, capex reserves) editable by analyst

---

### 4. **Rent Roll Analyzer Agent**

**Purpose**: Parse rent rolls, identify unit mix issues, and recommend revenue optimization.

**Tools**:
- `parse_rent_roll_pdf`: Extract unit-level data (unit #, tenant, rent, lease date)
- `calculate_unit_metrics`: Compute $ per sq ft, occupancy by unit type
- `benchmark_market_rents`: Compare to Zillow/Apartments.com for MSA
- `identify_below_market_units`: Flag units > 15% below market
- `estimate_revenue_upside`: Model rent increases to market

**Workflow**:
```
1. Parse rent roll PDF (handle various formats with GPT-4V fallback)
2. Standardize to schema: unit_id, size_sqft, current_rent, lease_end, tenant_name
3. Calculate:
   - Economic occupancy (rent collected / potential rent)
   - Physical occupancy (occupied units / total units)
   - Average rent by unit size (1BR, 2BR, 3BR)
4. Scrape market comps within 5-mile radius (Zillow API)
5. Identify below-market units and estimate annual revenue upside:
   - Upside = Σ (market_rent - current_rent) × 12 for units > 15% below market
6. Recommend lease renewal strategy (gradual increases to minimize churn)
7. Generate unit-level pricing recommendations with prioritization
```

**Output Example**:
```json
{
  "property_id": "MHP-2024-015",
  "total_units": 47,
  "economic_occupancy": 0.89,
  "physical_occupancy": 0.92,
  "average_rent": 785,
  "market_average_rent": 850,
  "below_market_units": 21,
  "annual_revenue_upside": 163800,
  "top_priorities": [
    {
      "unit_id": "A12",
      "current_rent": 650,
      "market_rent": 825,
      "monthly_upside": 175,
      "lease_end": "2024-11-30",
      "recommendation": "Offer renewal at $750 (+15%), then $825 in Year 2"
    }
  ]
}
```

---

## Due Diligence Agents

### 5. **Document Extraction Agent**

**Purpose**: Auto-extract key facts from due diligence documents (leases, permits, surveys).

**Tools**:
- `upload_document`: Store PDF in S3 with signed URL
- `ocr_document`: Extract text via Textract or DocAI
- `classify_document`: Determine type (lease, permit, survey, utility bill, etc.)
- `extract_entities`: Pull dates, dollar amounts, parties, addresses
- `validate_extracted_data`: Cross-check against property profile
- `flag_discrepancies`: Alert analyst to inconsistencies

**Workflow**:
```
1. Seller uploads DD docs to secure portal (S3 presigned URLs)
2. For each document:
   a. Run OCR to extract text
   b. Classify document type with LLM (few-shot classification)
   c. Extract structured data based on type:
      - Lease: tenant name, unit, rent, lease start/end, deposit
      - Permit: permit #, issue date, expiration, scope, status
      - Utility Bill: provider, meter #, monthly cost, usage
   d. Validate against known property data (flag if unit # doesn't exist)
3. Store extracted data in DD model tables
4. Generate DD checklist status (% complete per category)
5. Notify analyst of newly processed docs and any red flags
```

**Prompt Template (Lease Extraction)**:
```
Extract key information from this residential lease agreement:

{document_text}

Return JSON with:
- tenant_name (string)
- unit_number (string)
- monthly_rent (float)
- security_deposit (float)
- lease_start_date (YYYY-MM-DD)
- lease_end_date (YYYY-MM-DD)
- lease_type (month-to-month | fixed-term)
- utilities_included (list)
- pets_allowed (boolean)
- special_provisions (list of strings)

If any field is not found, set to null. Be precise with dates and amounts.
```

**Error Handling**:
- Low-confidence extractions (< 85%) flagged for human review
- Duplicate documents detected via hash and skipped
- Version control: track document updates during DD period

---

### 6. **Risk Assessment Agent**

**Purpose**: Aggregate risk signals from multiple sources and quantify deal risk score.

**Data Sources**:
- 311 complaint density (nuisance, crime, blight)
- FEMA flood maps
- Environmental site assessments (Phase I/II)
- Title/lien searches
- Permit violation history
- Utility arrears

**Tools**:
- `analyze_311_trends`: Aggregate service requests by category and severity
- `assess_flood_risk`: Check FEMA zones, historical flooding events
- `check_title_liens`: Query county records for encumbrances
- `evaluate_deferred_maintenance`: Estimate capex backlog from inspection notes
- `calculate_risk_score`: Weighted composite risk (0-100)

**Risk Categories & Weights**:
| Category | Weight | Metrics |
|----------|--------|---------|
| Environmental | 25% | Flood zone, soil contamination, wetlands |
| Operational | 20% | 311 complaints, code violations, utility shutoffs |
| Financial | 20% | Occupancy trend, rent collection %, delinquency |
| Legal | 15% | Title defects, outstanding liens, pending litigation |
| Physical | 20% | Deferred maintenance, useful life of systems |

**Workflow**:
```
1. For each risk category, compute sub-scores:
   Environmental:
   - If in FEMA Zone AE: -30 points
   - If Phase I ESA flags concerns: -40 points
   
   Operational:
   - If 311 complaints > 2 per unit per year: -25 points
   - If code violations in last 3 years: -35 points
   
   Financial:
   - If occupancy < 85%: -20 points
   - If delinquency > 10%: -30 points
   
   Legal:
   - If outstanding liens: -50 points
   - If pending litigation: -40 points
   
   Physical:
   - If roof age > 20 years: -25 points
   - If roads need repaving: -20 points
   - If sewer/water systems failing: -40 points

2. Calculate weighted risk score (100 = zero risk)
3. Classify deal:
   - LOW RISK: Score > 75
   - MEDIUM RISK: Score 50-75
   - HIGH RISK: Score < 50
4. Generate risk mitigation checklist for high-risk items
5. Recommend: PROCEED / PROCEED WITH CAUTION / WALK AWAY
```

**Output Example**:
```
Property: Magnolia Gardens MHP
Overall Risk Score: 68 (MEDIUM RISK)

Risk Breakdown:
✓ Environmental (85/100): Not in flood zone, clean Phase I
⚠ Operational (60/100): High 311 complaint rate (3.2 per unit/yr)
⚠ Financial (55/100): Occupancy 82%, delinquency 12%
✓ Legal (90/100): Clean title, no liens
⚠ Physical (50/100): Roof 22 years old, roads need repaving

Top Risks:
1. Deferred maintenance capex: est. $285k (roads + roofs)
2. Below-market occupancy: need marketing push + rehab units
3. High 311 complaints: investigate and address immediately

Recommendation: PROCEED WITH CAUTION
- Negotiate $150k price reduction for capex
- Require 6-month seller financing for stabilization
- Include clawback provision if occupancy < 88% at closing
```

---

## CRM & Outreach Agents

### 7. **Broker Relationship Agent**

**Purpose**: Manage broker relationships, track deal flow, automate follow-ups.

**Tools**:
- `fetch_broker_contacts`: Query CRM for broker database
- `analyze_broker_performance`: Track deals sourced, close rate, avg time-to-close
- `generate_email_draft`: Create personalized outreach emails
- `schedule_follow_up`: Set reminder tasks in CRM
- `send_market_update`: Distribute quarterly market reports to brokers

**Workflow (Quarterly Broker Campaign)**:
```
1. Segment brokers by performance tier:
   - Tier 1: Sent 3+ deals in last 12 months, 1+ closed
   - Tier 2: Sent 1-2 deals, none closed yet
   - Tier 3: No deals sent yet, but covers target markets
   
2. For each tier, generate personalized email:
   
   Tier 1:
   - Thank for recent deals ({deal_names})
   - Share portfolio update and current acquisition criteria
   - Invite to site visit of recently acquired park
   
   Tier 2:
   - Acknowledge deals sent, provide feedback on why passed
   - Reiterate buying criteria
   - Offer to preview off-market deals before formal listing
   
   Tier 3:
   - Introduce Gallagher as active buyer in Louisiana
   - Share recent acquisition (social proof)
   - Mention specific markets of interest (East Baton Rouge, Lafayette)

3. Human reviews and edits emails before sending
4. Track open/reply rates in CRM
5. Auto-schedule 30-day follow-up if no response
```

**Prompt Template (Tier 1 Broker Email)**:
```
You are drafting an email to a top-performing broker. Be professional, warm, and appreciative.

Broker: {broker_name} at {brokerage}
Relationship History: {relationship_summary}
Recent Deals Sent: {deal_list}

Email Goals:
1. Thank them for quality deal flow
2. Update them on your recent acquisition of {recent_property}
3. Reiterate current acquisition criteria (20+ units, East Baton Rouge, on/off-market)
4. Invite them to tour {recent_property} next month

Tone: Professional but friendly. Keep under 150 words.
```

---

### 8. **Owner Direct Outreach Agent**

**Purpose**: Identify property owners and automate personalized direct mail / email campaigns.

**Tools**:
- `fetch_parcel_ownership`: Query assessor data for owner name and mailing address
- `enrich_owner_data`: Append phone, email via Skip tracing APIs (BeenVerified, Whitepages)
- `score_owner_motivation`: Predict likelihood of selling (age, out-of-state, estate)
- `generate_letter_template`: Create personalized direct mail copy
- `send_mailer`: Integrate with Lob API for printing and mailing
- `track_campaign_performance`: Monitor response rate, cost per lead

**Workflow (Monthly Direct Mail Campaign)**:
```
1. Identify target universe:
   - All mobile home parks in East Baton Rouge (20+ units)
   - Owner has owned > 10 years (potential burnout)
   - OR owner is out-of-state (harder to manage remotely)
   - OR owner age > 70 (succession planning)
   
2. Enrich owner data:
   - Match owner name to phone/email via skip tracing
   - Check if property is in LLC (if yes, find registered agent)
   
3. Segment by motivation score:
   - HIGH: Out-of-state + age 70+ + owned 15+ years
   - MEDIUM: 2 of 3 above factors
   - LOW: In-state, younger owner, owned < 5 years
   
4. Generate personalized letter for each owner:
   - Mention specific property address
   - Acknowledge challenges of managing mobile home parks
   - Offer fair, cash purchase with flexible timeline
   - Include recent testimonial from past seller
   
5. Print and mail via Lob API (first-class postage)
6. Wait 10 days, send follow-up postcard
7. Wait 20 days, send email (if email address available)
8. Track responses in CRM and assign to analyst for outreach
```

**Letter Template (High Motivation)**:
```
Dear {owner_name},

I hope this letter finds you well. My name is [Analyst Name], and I work with Gallagher Property Company, a Louisiana-based real estate firm specializing in mobile home park acquisitions.

I'm writing because we're actively acquiring parks in East Baton Rouge Parish, and {property_address} caught our attention. We admire how you've maintained the property over the years, and we understand that managing a mobile home park—especially from {owner_state}—comes with unique challenges.

If you've ever considered selling, we'd love to have a no-obligation conversation. We offer:
✓ Fair market value, based on current income
✓ All-cash purchase with flexible closing timeline
✓ We handle all tenant communications and transition logistics

We recently acquired [Recent Property Name] under similar terms, and the previous owner shared: "[Testimonial quote about smooth process]"

Would you be open to a brief call to discuss? You can reach me directly at [Phone] or reply to [Email].

Thank you for your time, and best wishes regardless.

Sincerely,
[Analyst Name]
Gallagher Property Company
```

**Compliance**:
- Include opt-out mechanism in all mailings (CAN-SPAM Act)
- Respect Do Not Call Registry for phone outreach
- Maintain suppression list for owners who decline contact

---

## Data Quality Agents

### 9. **Schema Drift Monitor Agent**

**Purpose**: Detect when upstream data sources (Socrata, ArcGIS) change schemas and trigger alerts.

**Tools**:
- `fetch_remote_schema`: Query API metadata endpoints for column definitions
- `compare_schemas`: Diff current schema vs. stored baseline
- `generate_migration`: Create Alembic migration for new/changed columns
- `send_alert`: Notify eng team via Slack webhook

**Workflow**:
```
1. Every 6 hours, query remote schemas for monitored datasets:
   - EBR Parcels (ArcGIS REST)
   - 311 Service Requests (Socrata SODA)
   - Building Permits (Socrata SODA)
   
2. For each dataset, compare current schema to last known version:
   - New columns added?
   - Columns removed or renamed?
   - Data types changed?
   
3. If drift detected:
   a. Log detailed change report
   b. Generate Alembic migration (AUTO mode, review required)
   c. Send Slack alert to #data-eng channel:
      "🚨 Schema drift detected in [Dataset Name]
       Added columns: [list]
       Removed columns: [list]
       Review migration: [link to generated file]"
   d. Pause ingestion job until migration approved
   
4. If no drift, log success and continue
```

**Prompt Template**:
```
Compare these two schemas and identify all changes:

Baseline Schema:
{baseline_schema_json}

Current Schema:
{current_schema_json}

Return JSON with:
- added_columns: [list of new column names]
- removed_columns: [list of deleted column names]
- renamed_columns: [{old: "X", new: "Y"}]
- type_changes: [{column: "Z", old_type: "string", new_type: "integer"}]

Be precise. Only flag actual changes, not reordering.
```

---

### 10. **Data Freshness Watchdog Agent**

**Purpose**: Ensure external data sources are updating as expected; alert if stale.

**Tools**:
- `check_last_modified`: Query API for last update timestamp
- `compare_to_expected_frequency`: Validate against SLA (daily, weekly, etc.)
- `trigger_manual_refresh`: Force re-ingestion if data is stale
- `log_freshness_metrics`: Store uptime metrics in Prometheus

**Workflow**:
```
1. For each external dataset, check last_modified timestamp:
   - Expected frequency defined in data catalog (daily, weekly, monthly)
   
2. Calculate staleness:
   - staleness_hours = (now - last_modified) in hours
   - threshold = expected_frequency × 1.5
   
3. If staleness_hours > threshold:
   a. Log WARNING
   b. Attempt manual refresh via ingestion job
   c. If refresh fails, send PagerDuty alert (P2 severity)
   d. Update data catalog status to "STALE"
   
4. If fresh:
   a. Log success
   b. Update catalog status to "CURRENT"
   c. Record freshness metric for dashboard

5. Weekly report to stakeholders:
   - Uptime % per data source
   - Avg refresh latency
   - # of staleness incidents
```

---

## Reporting & Intelligence Agents

### 11. **Executive Briefing Agent**

**Purpose**: Generate daily executive summary of pipeline, key metrics, and action items.

**Tools**:
- `fetch_pipeline_summary`: Query CRM for deal stages and counts
- `calculate_portfolio_metrics`: Aggregate NOI, occupancy, cash flow across all properties
- `identify_action_items`: Surface overdue tasks and upcoming deadlines
- `generate_briefing_document`: Compile into readable PDF or Slack message

**Workflow (Daily at 7 AM)**:
```
1. Pull key metrics:
   - Pipeline: # of deals by stage (Sourcing, Underwriting, DD, Closing)
   - Total pipeline value: Σ purchase prices
   - Avg days in each stage
   - Deals closed this month vs. target
   - Portfolio: total units, avg occupancy, consolidated NOI
   
2. Identify top priorities:
   - Deals with upcoming deadlines (e.g., DD expiration in 7 days)
   - Tasks overdue > 3 days
   - Properties with occupancy < 85% (need action)
   
3. Highlight insights:
   - "Pipeline velocity increased 15% WoW"
   - "Magnolia Gardens occupancy dropped to 83% (investigate)"
   - "New parcel lead matching criteria: 123 Oak St (review today)"
   
4. Generate executive summary (1-page PDF or Slack message):
   - Metrics dashboard
   - Top 3 priorities for the day
   - Key insights / alerts
   
5. Deliver via Slack DM to CEO and email to leadership team
```

**Output Example (Slack Format)**:
```
📊 **Daily Briefing - Oct 17, 2025**

**Pipeline**
🔵 Sourcing: 12 leads (+2 new yesterday)
🟡 Underwriting: 5 deals (avg 8 days in stage)
🟠 Due Diligence: 2 deals
🟢 Closing: 1 deal (Magnolia Terrace - closes Oct 25)

💰 Total Pipeline Value: $8.4M

**Portfolio**
🏘️ Total Units: 427
📈 Avg Occupancy: 91.2% (target: 93%)
💵 Monthly NOI: $142,500

**🚨 Action Items**
1. Cypress Park - DD expires in 5 days (missing: Phase I ESA)
2. Oak Manor - occupancy 83%, down from 89% last month (investigate)
3. New lead: Southside MHP, 28 units, $1.2M asking (review underwriting)

**💡 Insights**
- Pipeline velocity up 15% WoW (good momentum)
- Oak Manor seeing elevated turnover; schedule site visit
- Interest rates held steady; financing environment stable

Have a great day! 🚀
```

---

### 12. **Market Comp Intelligence Agent**

**Purpose**: Continuously monitor sold comps and update valuation models.

**Tools**:
- `fetch_recent_sales`: Query CoStar/Crexi/LoopNet APIs for recent transactions
- `extract_sale_details`: Parse listing data (price, cap rate, units, location)
- `normalize_metrics`: Adjust for market, condition, unit mix differences
- `update_valuation_model`: Retrain cap rate prediction model with new data
- `generate_comp_report`: Create detailed comp analysis for specific property

**Workflow (Weekly)**:
```
1. Query external APIs for mobile home park sales in Louisiana (last 7 days)
2. For each sale:
   a. Extract: property name, address, # units, sale price, cap rate, date
   b. Geocode address to lat/lon
   c. Enrich with demographic data (median income, population density)
   d. Store in comps database
   
3. Update valuation model:
   - Features: units, location, age, occupancy, market MSA
   - Target: cap rate
   - Model: Gradient boosted regression (scikit-learn)
   - Retrain monthly with rolling 24-month dataset
   
4. For active deals in pipeline:
   - Generate updated comp report with 5 most similar sales
   - Flag if current offer is > 10% above predicted value
   
5. Notify analysts of significant outliers or market shifts
```

**Comp Report Template**:
```
Property: Cypress Park MHP
Offer: $2.1M (5.8% cap rate)
Units: 38

Top 5 Comps (within 50 miles, last 12 months):

1. Oakwood Village - Baton Rouge, LA
   32 units | $1.65M | 6.2% cap | Sold Aug 2024
   Distance: 8 mi | Similarity: 92%
   
2. Pine Ridge Estates - Denham Springs, LA
   45 units | $2.4M | 5.9% cap | Sold Jun 2024
   Distance: 18 mi | Similarity: 88%
   
[3 more comps...]

Predicted Cap Rate: 6.0% (model confidence: 85%)
Implied Value at 6.0% cap: $2.0M

⚠️ Offer is 5% above predicted value. Consider negotiating to $2.0M.
```

---

## Implementation Roadmap

### Phase 1: Foundation (Months 1-2)

**Goal**: Establish agent infrastructure and deploy 2 high-value agents.

**Deliverables**:
- [ ] Agent orchestration framework (LangChain + FastAPI integration)
- [ ] Observability pipeline (LangSmith + structured logging)
- [ ] Tool registry (all API endpoints wrapped as LangChain tools)
- [ ] Deploy **Parcel Hunter Agent** (automate lead sourcing)
- [ ] Deploy **Underwriting Autopilot Agent** (financial screening)

**Success Metrics**:
- 10+ qualified leads generated per week by Parcel Hunter
- Underwriting time reduced from 4 hours → 1 hour per deal
- Zero agent failures requiring manual intervention

---

### Phase 2: Due Diligence Automation (Months 3-4)

**Goal**: Streamline DD process with document automation.

**Deliverables**:
- [ ] Deploy **Document Extraction Agent** (auto-parse leases, permits)
- [ ] Deploy **Risk Assessment Agent** (aggregate risk signals)
- [ ] Vector store integration for semantic search over DD documents
- [ ] Human-in-the-loop approval workflow for extracted data

**Success Metrics**:
- 80% of DD documents processed automatically (no human OCR)
- Risk score generated within 24 hours of entering DD phase
- 50% reduction in time spent on document review

---

### Phase 3: CRM & Outreach (Months 5-6)

**Goal**: Scale deal flow through automated broker and owner outreach.

**Deliverables**:
- [ ] Deploy **Broker Relationship Agent** (quarterly campaigns)
- [ ] Deploy **Owner Direct Outreach Agent** (monthly direct mail)
- [ ] Integration with Lob API for printing/mailing
- [ ] Skip tracing integration (BeenVerified or similar)

**Success Metrics**:
- 2x increase in deals entering pipeline (from broker and owner channels)
- 5%+ response rate on direct mail campaigns
- 100% of brokers contacted quarterly

---

### Phase 4: Data Quality & Intelligence (Months 7-8)

**Goal**: Ensure data reliability and proactive market intelligence.

**Deliverables**:
- [ ] Deploy **Schema Drift Monitor Agent**
- [ ] Deploy **Data Freshness Watchdog Agent**
- [ ] Deploy **Executive Briefing Agent** (daily reports)
- [ ] Deploy **Market Comp Intelligence Agent** (valuation updates)

**Success Metrics**:
- 99.5% data uptime (no stale data incidents)
- Zero schema drift incidents causing pipeline failures
- Daily briefing delivered 100% reliably by 7 AM

---

### Phase 5: Advanced Analytics (Months 9-12)

**Goal**: Predictive models and optimization agents.

**Deliverables**:
- [ ] **Tenant Churn Prediction Agent**: Identify at-risk tenants 60 days before move-out
- [ ] **Capex Optimization Agent**: Recommend optimal timing/sequencing for major projects
- [ ] **Acquisition Target Scoring Agent**: Machine learning model to rank all leads
- [ ] **Portfolio Rebalancing Agent**: Recommend buy/sell/hold for each property

**Success Metrics**:
- 20% reduction in tenant turnover via proactive retention
- Capex deployed 15% more efficiently (ROI per dollar spent)
- Top 10% of leads (by agent score) convert at 3x rate vs. bottom 50%

---

## Agent Performance Dashboard

Track KPIs for each agent to ensure continuous improvement:

| Agent | Executions/Week | Success Rate | Avg Runtime | Human Intervention Rate | Business Impact |
|-------|----------------|--------------|-------------|-------------------------|-----------------|
| Parcel Hunter | 7 | 98% | 12 min | 5% (approval) | 10 leads/week |
| Underwriting Autopilot | 15 | 95% | 8 min | 20% (review) | 75% time savings |
| Document Extraction | 50 | 92% | 3 min | 15% (low confidence) | 80% auto-processed |
| Risk Assessment | 10 | 100% | 5 min | 0% (informational) | Earlier risk ID |
| Broker Relationship | 1/quarter | 100% | 20 min | 100% (human approval) | 2x deal flow |
| Owner Direct Outreach | 4 | 98% | 45 min | 10% (letter review) | 5% response rate |
| Schema Drift Monitor | 28 | 100% | 2 min | 0% (alerts only) | Zero drift incidents |
| Data Freshness Watchdog | 28 | 99% | 1 min | 1% (manual refresh) | 99.5% uptime |
| Executive Briefing | 7 | 100% | 5 min | 0% (auto-delivered) | Daily leadership insights |
| Market Comp Intelligence | 1 | 100% | 15 min | 0% (auto-update) | Valuation accuracy +10% |

---

## Security & Compliance

### Data Access Controls
- Agents operate with scoped service accounts (least privilege)
- Read-only access to CRM/financial data (writes require human approval)
- All agent actions logged with user attribution for audit trail

### PII Minimization
- Tenant names/contact info redacted in logs
- Owner contact data encrypted at rest (KMS)
- Skip tracing results stored separately with limited access

### Rate Limiting
- External API calls throttled (max 100/hour per source)
- Exponential backoff on failures
- Cost monitoring with daily budget alerts

### Model Monitoring
- Track LLM input/output tokens for cost control
- Flag unexpected outputs (hallucinations, errors)
- Human review for any agent action with $ impact > $1,000

---

## Cost Estimation

**Monthly Agent Operating Costs**:

| Component | Cost/Month |
|-----------|-----------|
| LLM API (GPT-4 Turbo, 2M tokens/day) | $1,200 |
| Vector Store (Pinecone, 1M vectors) | $70 |
| Observability (LangSmith) | $200 |
| External APIs (CoStar, Skip Tracing, Lob) | $500 |
| Compute (FastAPI agents, background workers) | $150 |
| **Total** | **$2,120/month** |

**ROI Analysis**:
- Analyst time saved: ~60 hours/month × $75/hr = $4,500
- Additional deals sourced: 40 leads/month × 2% close rate × $30k profit = $24,000
- **Net monthly value: $26,380 - $2,120 = $24,260/month**
- **Payback period: < 1 week**

---

## Appendix: Agent Prompt Library

### Prompt Engineering Best Practices

1. **Be Specific**: Define exact output format (JSON schema, bullet points, etc.)
2. **Provide Examples**: Few-shot learning dramatically improves accuracy
3. **Set Constraints**: Word limits, required fields, validation rules
4. **Assign Role**: "You are a real estate analyst specializing in..."
5. **Chain of Thought**: For complex tasks, ask agent to "think step-by-step"
6. **Error Handling**: Instruct what to do if data is missing or ambiguous

### Sample Prompts

**Property Evaluation (Classification)**:
```
You are a real estate analyst evaluating mobile home park acquisition targets.

Property Details:
- Address: {address}
- Acreage: {acreage}
- Zoning: {zoning}
- 311 Complaints (5yr): {complaint_count}
- Flood Zone: {flood_zone}

Evaluate this property for acquisition. Return JSON:
{
  "score": <0-100>,
  "recommendation": "PURSUE" | "MONITOR" | "PASS",
  "reasoning": "<2-3 sentences>",
  "red_flags": ["<list any issues>"]
}

Criteria:
- PASS if in 100-year floodplain OR > 3 complaints/unit/year
- MONITOR if 1-3 complaints/unit/year OR marginal zoning
- PURSUE if < 1 complaint/unit/year AND good zoning AND no flood risk
```

**Financial Underwriting (Calculation + Reasoning)**:
```
You are underwriting a mobile home park acquisition. Think step-by-step.

Given:
- Purchase Price: ${price}
- Gross Rents (annual): ${gross_rents}
- Vacancy Rate: {vacancy}%
- Operating Expenses (annual): ${opex}
- Loan Amount: ${loan_amount} at {rate}% for {years} years

Step 1: Calculate EGI = Gross Rents × (1 - Vacancy Rate)
Step 2: Calculate NOI = EGI - Operating Expenses
Step 3: Calculate Annual Debt Service = Loan Payment × 12
Step 4: Calculate DSCR = NOI / Annual Debt Service
Step 5: Evaluate:
  - If DSCR ≥ 1.25: STRONG
  - If DSCR 1.15-1.25: ACCEPTABLE
  - If DSCR < 1.15: WEAK

Show all calculations. Final recommendation: BID or PASS?
```

**Document Extraction (Structured Output)**:
```
Extract tenant information from this lease agreement:

{lease_text}

Return valid JSON only (no additional text):
{
  "tenant_name": "string",
  "unit_number": "string",
  "monthly_rent": number,
  "lease_start": "YYYY-MM-DD",
  "lease_end": "YYYY-MM-DD",
  "deposit": number
}

Rules:
- If a field is not found, set to null
- Dates must be ISO 8601 format
- Numbers must be numeric (no $ symbols)
- Be precise; do not guess
```

---

## Conclusion

This AI agent strategy transforms GallagherMHP from a manual CRM into an intelligent acquisition engine. By automating 70% of repetitive tasks (lead sourcing, document processing, financial analysis), the team can focus on high-value activities: relationship building, creative deal structuring, and strategic portfolio management.

**Key Success Factors**:
1. Start small (2 agents), prove value, then scale
2. Maintain human-in-the-loop for critical decisions
3. Obsess over observability and error handling
4. Continuously refine prompts based on real-world performance
5. Treat agents as team members: measure, coach, improve

**Next Steps**:
1. Review this document with engineering and acquisitions teams
2. Prioritize Phase 1 agents based on highest-impact use cases
3. Set up development environment (LangChain, FastAPI tools, observability)
4. Build MVP of Parcel Hunter Agent (2-week sprint)
5. Deploy to production with monitoring and iterate

---

**Document Version**: 1.0  
**Last Updated**: October 17, 2025  
**Owner**: Gallagher Property Company  
**Questions?**: Contact engineering team or see `/backend/README.md` for technical setup

