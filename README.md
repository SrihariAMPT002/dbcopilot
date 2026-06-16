# DB Copilot

DB Copilot is an AI-native Metadata Intelligence, Governance, and Retrieval Platform.

It connects to enterprise databases, discovers metadata, builds governance and semantic intelligence, reasons over relationships, generates KPI and prompt artifacts, creates embeddings and retrieval assets, and evaluates AI readiness with full observability.

## Overview

Current capabilities in this repository:

- Metadata Discovery
- Governance and PII Detection
- Semantic Intelligence
- Relationship Intelligence
- KPI Intelligence
- Prompt Studio
- Embeddings and Retrieval
- AI Readiness
- AI Observability

The backend is the source of truth. The React frontend consumes package-driven APIs and renders the current intelligence state.

## Architecture

Package-first execution flow:

```text
Metadata
 -> Governance
 -> Semantics
 -> Relationships
 -> KPI
 -> Prompt Studio
 -> Embeddings & Retrieval
 -> AI Readiness
```

Pipeline execution is tracked through persisted execution records and stage status APIs. Downstream stages consume persisted packages rather than rebuilding intelligence from raw metadata when package data already exists.

## Tech Stack

### Backend

- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Azure OpenAI GPT-5 Nano
- Qdrant
- LangSmith / Langfuse observability integrations
- Python 3.11

### Frontend

- React 19
- TypeScript
- Vite
- TanStack Query
- TanStack Router
- Tailwind CSS v4
- shadcn/ui

## Repository Structure

```text
dbcopilot/
├── app/
│   ├── api/
│   ├── config/
│   ├── connectors/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── prompts/
│   ├── schemas/
│   ├── schema_engine/
│   ├── services/
│   ├── templates/
│   ├── utils/
│   └── workflows/
├── alembic/
├── docs/
├── frontend/
│   └── src/
│       ├── api/
│       ├── components/
│       ├── context/
│       ├── hooks/
│       ├── lib/
│       ├── pages/
│       ├── routes/
│       ├── services/
│       └── types/
├── scripts/
├── tests/
├── docker-compose.yml
├── Dockerfile.api
└── Dockerfile.frontend
```

### Backend folders

- `app/services/` - orchestration and domain services
- `app/models/` - ORM models
- `app/schemas/` - API and domain schemas
- `app/prompts/` - prompt contracts and stage templates
- `app/config/` - settings, feature flags, and prompt configuration
- `app/api/` - FastAPI routes
- `app/workflows/` - workflow helpers and execution logic

### Frontend folders

- `frontend/src/routes/` - route registration
- `frontend/src/pages/` - page composition
- `frontend/src/components/` - reusable UI
- `frontend/src/hooks/` - data fetching hooks
- `frontend/src/services/` - UI transformation and domain services
- `frontend/src/api/` - HTTP transport modules
- `frontend/src/context/` - global application state
- `frontend/src/types/` - backend-aligned TypeScript contracts

## Supported Databases

Implemented connectors and test paths currently support:

- PostgreSQL
- MySQL
- MariaDB
- SQL Server
- MongoDB

## AI Modules

The repository includes these intelligence surfaces:

- Governance intelligence and PII classification
- Semantic intelligence
- Relationship intelligence
- KPI intelligence
- Prompt Studio artifact generation
- Embeddings and retrieval
- Retrieval metrics and evaluation
- AI readiness scoring
- Business events
- Business insights
- Agent memory
- Prompt budget auditing

## Observability

AI executions and pipeline stages record:

- `trace_id`
- `prompt_id`
- `prompt_version`
- `model_name`
- token usage
- `finish_reason`
- latency
- execution status
- failure reason

Azure OpenAI calls go through the observability wrapper so raw responses and token metadata can be inspected during troubleshooting.

## API Documentation

Major API groups currently in the backend:

- Connections and database management
- Metadata and schema exploration
- Governance and column semantics
- Semantics
- Relationships
- KPI intelligence
- Prompt Studio
- Embeddings and retrieval
- Retrieval metrics and evaluation
- AI readiness
- Business events and business insights
- Agent memory
- Pipeline execution and job tracking
- Prompt budgets
- Dashboard and status summaries

API docs are available through the FastAPI OpenAPI UI when the backend is running.

## Environment Variables

Copy [`.env.example`](.env.example) to `.env` and configure the values for your environment.

Backend environment variables used by the repository include:

```env
APP_NAME=DB Copilot
APP_ENV=development
APP_VERSION=1.0.0
DEBUG=true
LOG_LEVEL=INFO
INTELLIGENCE_PACKAGES_ENABLED=true

API_HOST=0.0.0.0
API_PORT=8000
API_PREFIX=/api/v1
WORKERS=1
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=dbcopilot_meta
POSTGRES_USER=dbcopilot
POSTGRES_PASSWORD=***
DATABASE_URL=postgresql+asyncpg://...
DATABASE_URL_SYNC=postgresql://...

ENCRYPTION_KEY=***
SECRET_KEY=***

QDRANT_URL=http://qdrant:6333
QDRANT_HOST=qdrant
QDRANT_PORT=6333

AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=***
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-5-nano

AZURE_OPENAI_EMBEDDING_URL=
AZURE_OPENAI_EMBEDDING_API_KEY=
AZURE_OPENAI_EMBEDDING_DIMENSIONS=

LANGSMITH_TRACING=false
LANGSMITH_PROJECT=dbcopilot
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Frontend environment variables:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=DBCopilot
VITE_APP_ENV=development
```

## Local Development

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Build:

```bash
cd frontend
npm run build
```

### Docker

```bash
docker compose up --build
```

The Docker stack currently includes:

- PostgreSQL metadata store
- FastAPI backend
- React frontend
- Qdrant vector store

## Development Workflow

- Create migrations with Alembic
- Run the backend sync pipeline from the API or job orchestration layer
- Use the Jobs page and dashboard to inspect execution status
- Use prompt budget and execution tracking pages to verify AI behavior
- Keep docs and tests aligned with the package-first architecture

## Screenshots

### Dashboard

_Placeholder_

### Governance

_Placeholder_

### Semantics

_Placeholder_

### Relationships

_Placeholder_

### Embeddings

_Placeholder_

### AI Readiness

_Placeholder_

## Roadmap

Future work belongs here only if it is not already implemented in the repository.

- Further prompt quality and retrieval improvements
- Additional model/provider integrations
- Expanded analytics and agent workflows

## Testing

Run the test suite with:

```bash
pytest
```

If you want targeted coverage, run the existing module-specific tests under `tests/`.

