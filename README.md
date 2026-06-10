# DB Copilot

## Overview

DB Copilot is an AI context engineering platform that transforms enterprise databases into AI-ready business context.

It connects to enterprise databases, discovers metadata, builds semantic understanding, generates retrieval-ready knowledge, and produces reusable AI context artifacts for chatbots, AI agents, RAG systems, copilots, and Text-to-SQL applications.

---

## Key Capabilities

- Database Connectivity
- Metadata Discovery
- Schema Exploration
- Relationship Graph Generation
- Jobs Dashboard and Pipeline Monitoring
- Semantic Intelligence
- PII Classification and Governance Scoring
- Embeddings & Retrieval
- Prompt Studio
- AI Readiness Assessment
- Artifact Export Framework
- AI Observability and Token Logging

---

## High-Level Architecture

```text
External Databases
  ↓
Metadata Discovery
  ↓
Schema Explorer
  ↓
Relationship Graph
  ↓
Relationship Clustering and Targeted AI Calls
  ↓
Semantic Intelligence
  ↓
PII Governance Classification
  ↓
Embeddings & Retrieval
  ↓
Prompt Studio
  ↓
Jobs Dashboard
  ↓
AI Context Artifacts
```

---

## Technology Stack

### Backend

- FastAPI
- Python 3.11
- SQLAlchemy
- Alembic
- Pydantic

### Frontend

- Streamlit

### Databases

- PostgreSQL
- MySQL
- SQL Server
- MongoDB

### AI & Semantic Layer

- Azure OpenAI
- OpenAI SDK
- Qdrant
- Vector Embeddings
- LangSmith-compatible observability

### Infrastructure

- Docker
- Docker Compose

---

## Repository Structure

```text
dbcopilot/
app/
├── api/
├── config/
├── connectors/
├── core/
├── db/
├── models/
├── schema_engine/
├── services/
├── prompts/
├── workflows/
└── main.py

ui/
├── components/
├── pages/
└── app.py

alembic/
docker/
scripts/
tests/
```

---

## Core Modules

### Connect Database

Responsible for secure database connectivity and metadata synchronization.

### Jobs Dashboard

Provides pipeline visibility for queued, running, failed, and completed jobs.

Supports retries, cancellation, and monitoring for the core AI stages.

### Schema Explorer

Provides visibility into schemas, tables, columns, and relationships.

### Relationship Graph

Builds entity relationships and dependency mapping.

Relationship intelligence now uses clustered, targeted AI calls instead of sending the entire schema to one prompt.

### Semantic Intelligence

Generates business summaries, glossary terms, business entities, and use cases from metadata.

Also powers governance-aware PII classification with rule-first and table-level fallback processing.

### Embeddings & Retrieval

Creates vector-searchable schema intelligence and semantic search capabilities.

### Prompt Studio

Generates AI-ready artifacts:

- Database Context
- System Prompt
- RAG Context
- Agent Context
- Text-to-SQL Context
- Database Intelligence Package

### AI Readiness

Evaluates how prepared a database is for AI-driven applications.

### Observability

AI calls now log estimated input tokens, prompt tokens, completion tokens, output size, and latency.

This improves visibility for semantic generation, PII classification, relationship intelligence, and embeddings.

### Governance

Prompt templates now use defensive defaults for `tojson` fields so missing values do not break rendering.

Readiness, relationship, system, and semantic prompts are safer to render with partial context.

---

## Prerequisites

### Required

- Docker 24+
- Docker Compose 2+
- Python 3.11+

### Optional

- Azure OpenAI Account
- Qdrant Instance

---

## Environment Setup

Create `.env` from `.env.example` and configure:

```env
DATABASE_URL=
POSTGRES_USER=
POSTGRES_PASSWORD=

AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=

QDRANT_HOST=
QDRANT_PORT=

ENCRYPTION_KEY=
```

---

## Running Locally

```bash
git clone <repo-url>
cd dbcopilot
cp .env.example .env
docker compose up --build
```

---

## Access URLs

- Frontend: `http://localhost:8501`
- Backend API: `http://localhost:8000`
- Swagger Documentation: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/health`

---

## Development Workflow

### Create Migration

```bash
alembic revision --autogenerate -m "message"
```

### Apply Migration

```bash
alembic upgrade head
```

### Rollback Migration

```bash
alembic downgrade -1
```

### Run Tests

```bash
pytest tests/
```

---

## Security

- Credentials encrypted at rest
- Secrets stored in environment variables
- No secrets committed to Git
- No secrets baked into Docker images
- Read-only metadata extraction

---

## Troubleshooting

Common issue:

### Migration failures

```bash
alembic upgrade head
```
