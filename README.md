# Financial Crime Analytics Data Platform

> **SMBC-Style AML Financial Crime Analytics Platform** — Python · Java · SQL · Azure · Databricks · PostgreSQL · Docker · Vercel

A production-grade Anti-Money Laundering (AML) analytics platform implementing entity resolution, network modeling, risk scoring, and investigative workflows aligned to FATF financial crime detection standards.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER (Vercel)                       │
│        Next.js 14 Dashboard  ·  5-tab AML UI  ·  Network Graph      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  REST API (/api/*)
┌──────────────────────────▼──────────────────────────────────────────┐
│                    APPLICATION LAYER                                  │
│   AML Pipeline  ·  Risk Scoring Engine  ·  Entity Resolution         │
│   Data Quality Engine  ·  Network Model                              │
│   (Python 3.11 — python/aml/)                                        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                  DATA PIPELINE LAYER (Java / Maven)                  │
│   TransactionTransformer  ·  DataIngestionPipeline                   │
│   Structuring Detection  ·  Data Quality Rules                       │
│   (Java 11 — java/src/)                                              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│               ANALYTICS LAYER (Azure Databricks + Delta Lake)        │
│   Bronze → Silver → Gold  ·  Spark UDFs  ·  ADLS Gen2               │
│   (databricks/notebooks/)                                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│               DATA STORE (PostgreSQL 15)                             │
│   entities · accounts · transactions · alerts                        │
│   investigation_cases · risk_scores_history                          │
│   (sql/schema/, sql/queries/)                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
.
├── pages/                    # Next.js pages (Vercel frontend)
│   ├── index.js              # AML dashboard (5 tabs)
│   ├── _app.js
│   └── api/                  # Serverless API routes
│       ├── alerts.js
│       ├── transactions.js
│       ├── risk-scores.js
│       ├── network.js
│       └── stats.js
├── styles/
│   └── globals.css
├── python/
│   ├── aml/                  # Core AML analytics library
│   │   ├── entity_resolution.py   # Entity matching & deduplication
│   │   ├── network_model.py       # Graph-based network analysis
│   │   ├── risk_scoring.py        # FATF-aligned 8-factor scoring
│   │   ├── data_quality.py        # Data quality validation engine
│   │   └── pipeline.py            # 6-stage ETL orchestration
│   ├── tests/
│   │   ├── test_entity_resolution.py
│   │   ├── test_risk_scoring.py
│   │   ├── test_data_quality.py
│   │   └── test_pipeline.py
│   └── requirements.txt
├── java/
│   ├── pom.xml
│   └── src/
│       ├── main/java/com/fcap/
│       │   ├── model/             # Transaction, Alert models
│       │   ├── transformation/    # TransactionTransformer
│       │   └── pipeline/          # DataIngestionPipeline
│       └── test/java/com/fcap/
│           └── transformation/    # JUnit 5 tests
├── sql/
│   ├── schema/
│   │   ├── 01_create_tables.sql   # Full relational schema
│   │   └── 02_create_views.sql    # Analytical views
│   └── queries/
│       ├── risk_detection.sql     # Structuring, layering, velocity queries
│       └── investigative_workflow.sql
├── databricks/
│   ├── notebooks/
│   │   ├── 01_data_ingestion.py   # Bronze layer (ADLS Gen2)
│   │   ├── 02_transformation.py   # Silver layer (DQ + transforms)
│   │   └── 03_risk_scoring.py     # Gold layer (Spark UDFs)
│   └── config/
│       └── azure_config.py        # Azure connection configuration
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── package.json
├── next.config.js
└── vercel.json
```

---

## 🚀 Quick Start

### Option A — Vercel (Production)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

### Option B — Local Development (Next.js Dashboard)

```bash
npm install
npm run dev
# Open http://localhost:3000
```

### Option C — Docker (Full Stack)

```bash
# Create .env file first (see Environment Variables below)
cp .env.example .env

docker-compose -f docker/docker-compose.yml up -d

# Dashboard:   http://localhost:3000
# PgAdmin:     http://localhost:5050
# PostgreSQL:  localhost:5432
```

### Option D — Python Analytics Only

```bash
cd python
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Use the library
python -c "
from aml.risk_scoring import AMLRiskScoringEngine
engine = AMLRiskScoringEngine()
score = engine.score_entity('ENT-001', {
    'transaction_amount': 500000,
    'velocity_30d': 45,
    'high_risk_country': True,
    'is_pep': True,
    'adverse_media_hits': 3,
    'centrality_score': 0.8,
    'layering_flag': True,
})
print(f'Risk: {score.risk_level} ({score.weighted_score:.1f})')
"
```

### Option E — Java Data Pipeline (Maven)

```bash
cd java
mvn clean test        # Run JUnit 5 tests
mvn clean package     # Build JAR
```

---

## 🧪 Testing

### Python (74 tests, all passing)

```bash
cd python
pytest tests/ -v --tb=short
pytest tests/ --cov=aml --cov-report=html
```

| Test Module | Tests | Coverage |
|---|---|---|
| `test_entity_resolution.py` | 22 | Entity normalization, similarity, clustering, merge |
| `test_data_quality.py` | 22 | Null checks, amount validation, currency, timestamp |
| `test_pipeline.py` | 16 | Full pipeline, transformation rules, stats |
| `test_risk_scoring.py` | 14 | Scoring factors, PEP, batch, filtering |

### Java (JUnit 5)

```bash
cd java
mvn test
```

---

## 🔍 Python AML Modules

### Entity Resolution (`python/aml/entity_resolution.py`)

Resolves duplicate entity records using:
- NFKD Unicode normalization
- Token-set Jaccard + bigram string similarity
- Union-Find clustering for transitive deduplication
- Field-level weighted comparison (name, address, DOB, national ID)

```python
from aml.entity_resolution import EntityResolutionEngine, Entity

engine = EntityResolutionEngine(similarity_threshold=0.8)
groups = engine.resolve_entities(entities)
```

### Risk Scoring (`python/aml/risk_scoring.py`)

FATF-aligned 8-factor weighted model:

| Risk Factor | Default Weight | Trigger |
|---|---|---|
| `TRANSACTION_AMOUNT` | 0.20 | Amount > $10K |
| `VELOCITY` | 0.15 | > 20 transactions/30d |
| `GEOGRAPHY` | 0.20 | High-risk country |
| `CUSTOMER_TYPE` | 0.10 | Shell company / offshore |
| `PEP_STATUS` | 0.15 | Politically Exposed Person |
| `ADVERSE_MEDIA` | 0.10 | Media mentions |
| `NETWORK_CENTRALITY` | 0.05 | High graph centrality |
| `LAYERING_DETECTED` | 0.05 | Network layering flag |

Risk levels: **LOW** (< 30) · **MEDIUM** (30–60) · **HIGH** (60–80) · **CRITICAL** (≥ 80)

### Network Model (`python/aml/network_model.py`)

Graph analysis features:
- DFS-based cycle detection (round-trip transactions)
- BFS suspicious path enumeration (max configurable hops)
- Layering pattern detection (chains of 3+ nodes with rapid sequential flows)
- Degree centrality calculation per node

### Data Quality (`python/aml/data_quality.py`)

10 built-in validation rules:
- Not-null checks for required AML fields
- Positive amount enforcement
- ISO 4217 currency code validation
- Future-timestamp guard
- Amount ceiling (≤ $10M per transaction)
- Account format validation (regex)

### AML Pipeline (`python/aml/pipeline.py`)

6-stage ETL orchestration:

```
INGESTION → VALIDATION → TRANSFORMATION → ENRICHMENT → SCORING → OUTPUT
```

Records failing VALIDATION are quarantined; all stages produce pipeline statistics.

---

## 🏦 SQL Data Model

### Core Tables

| Table | Purpose |
|---|---|
| `entities` | KYC entity records with PEP flag and risk score |
| `accounts` | Bank accounts linked to entities |
| `transactions` | All monitored transactions with risk scoring |
| `alerts` | Generated AML alerts |
| `investigation_cases` | Case management workflow |
| `risk_scores_history` | Audit trail of all score changes (JSONB factors) |

### Key Risk Detection Queries (`sql/queries/risk_detection.sql`)

1. **Structuring** — Multiple transactions just below $10,000 within 7 days
2. **Round-trip** — Money leaving and returning to same entity within 30 days
3. **High velocity** — > 50 transactions from one account in 24 hours
4. **High-risk geography** — Transactions to/from FATF grey/black-listed jurisdictions
5. **Network chains** — Recursive CTE traversal finding chains of depth ≥ 3

---

## ☁️ Azure / Databricks Architecture

### Delta Lake — Medallion Architecture

| Layer | Notebook | Purpose |
|---|---|---|
| **Bronze** | `01_data_ingestion.py` | Raw ingest from ADLS Gen2; schema enforcement |
| **Silver** | `02_transformation.py` | DQ scoring, normalization, Z-ordering |
| **Gold** | `03_risk_scoring.py` | Spark UDF risk scoring; JDBC write to PostgreSQL |

### Azure Services Used

- **Azure Data Lake Storage Gen2** — Raw and processed data storage
- **Azure Databricks** — Spark-based transformation and scoring
- **Azure Key Vault** — Secret management (no credentials in code)
- **PostgreSQL (Azure Database)** — Operational data store

---

## 🐳 Docker

```yaml
# docker/docker-compose.yml
services:
  aml-api:       # Python AML service (port 8000)
  postgres:      # PostgreSQL 15 with schema init (port 5432)
  pgadmin:       # PgAdmin4 web UI (port 5050)
```

---

## 🌐 Dashboard Features (Vercel)

| Tab | Contents |
|---|---|
| **📊 Overview** | KPI cards, 7-day alert trend, alert type distribution, recent high-risk alerts |
| **🚨 Alerts** | Full alert list with risk scores, types, statuses, and descriptions |
| **⚠️ Risk Scores** | Entity risk scores with visual bars, PEP flags, country codes |
| **🕸️ Network** | Interactive SVG transaction network graph showing layering patterns |
| **💸 Transactions** | Transaction monitoring table with flagging status |

---

## 🗓️ Agile Delivery — Sprint Plan

| Sprint | Goal | Deliverables |
|---|---|---|
| Sprint 1 | Foundation | Python OOP AML library, data models, SQL schema |
| Sprint 2 | Pipeline | Java ETL pipeline, data quality rules, transformation logic |
| Sprint 3 | Analytics | Risk scoring engine, entity resolution, network model |
| Sprint 4 | Platform | Azure/Databricks integration, Docker, CI/CD |
| Sprint 5 | UI/UX | Vercel dashboard, API routes, network visualization |

---

## 🔐 Security

- No credentials committed to source code — all secrets via environment variables / Azure Key Vault
- `docker-compose.yml` uses mandatory env var syntax (`:?`) to prevent accidental weak-credential deployments
- SQL schema uses UUID primary keys and CHECK constraints
- Data quality engine validates all inputs before processing

---

## 📦 Environment Variables

```bash
# PostgreSQL (required for Docker)
POSTGRES_PASSWORD=<strong-password>
PGADMIN_DEFAULT_PASSWORD=<strong-password>

# Azure (for Databricks notebooks)
AZURE_STORAGE_ACCOUNT_NAME=<account>
AZURE_STORAGE_CONTAINER=<container>
AZURE_KEY_VAULT_NAME=<vault>
DATABRICKS_WORKSPACE_URL=<url>
```

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Frontend / Deployment | Next.js 14, React 18, Vercel |
| AML Analytics Library | Python 3.11, OOP, dataclasses |
| Data Pipeline | Java 11, Maven, CompletableFuture |
| Database | PostgreSQL 15, UUID, JSONB, CTEs |
| Big Data / Cloud | Azure Databricks, Delta Lake, ADLS Gen2 |
| Containerisation | Docker, docker-compose |
| Testing | pytest 7.4 (74 tests), JUnit 5 |
| Version Control | Git, GitHub |
