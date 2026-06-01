#  DB Copilot

**AI-powered database copilot** — connect external databases, sync schemas automatically, and (soon) query them in plain English.

> **Current version:** MVP — Connection infrastructure + Schema synchronization + Streamlit UI.
> AI querying is architecturally ready but not yet activated.

---

## 📐 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit UI (:8501)                         │
│   Home │ Connect DB │ Connected Sources │ Schema Explorer │ Chat    │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ HTTP / REST
┌─────────────────────────▼───────────────────────────────────────────┐
│                      FastAPI Backend (:8000)                        │
│                                                                     │
│  /connections  /metadata  /ai (placeholders)                        │
│                                                                     │
│  ┌──────────────────┐    ┌──────────────────────────────────────┐   │
│  │ ConnectionService│    │           SyncService                │   │
│  └──────────────────┘    └──────────────────────────────────────┘   │
│                                       │                             │
│            ┌──────────────────────────▼──────────────────────────┐  │
│            │              Connector Layer                        │  │
│            │  PostgresConnector  MySQLConnector                  │  │
│            │  SQLServerConnector MongoConnector                  │  │
│            └──────────────────────────┬──────────────────────────┘  │
└───────────────────────────────────────│─────────────────────────────┘
                                        │
          ┌──────────────────────────────▼──────────────────────────────┐
          │              External Databases (user-provided)             │
          │   PostgreSQL  │  MySQL  │  SQL Server  │  MongoDB           │
          └─────────────────────────────────────────────────────────────┘
                                        │
          ┌──────────────────────────────▼──────────────────────────────┐
          │           Internal PostgreSQL Metadata Store (:5432)        │
          │  connected_databases │ database_schemas │ database_tables   │
          │  database_columns    │ database_relationships │ sync_logs   │
          └─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Docker ≥ 24.0
- Docker Compose ≥ 2.0
- Python 3.11+ (for local dev only)

### 1 — Clone and configure

```bash
git clone <your-repo>
cd dbcopilot

# Create .env from template (auto-generates encryption key)
./scripts/start.sh
```

Or manually:

```bash
cp .env.example .env

# Generate an encryption key
python scripts/generate_key.py
# → paste the key into .env as ENCRYPTION_KEY=...
```

### 2 — Start the stack

```bash
# Build images and start all services in the background
docker compose up --build -d

# Or use the helper script
./scripts/start.sh --build
```

### 3 — Access the UI

| Service         | URL                          |
|-----------------|------------------------------|
| Streamlit UI    | http://localhost:8501        |
| FastAPI Docs    | http://localhost:8000/docs   |
| Health Check    | http://localhost:8000/health |

### 4 — Connect your first database

1. Open http://localhost:8501
2. Navigate to **Connect Database**
3. Enter your DB credentials
4. Click **Test Connection** → **Connect & Sync**
5. Explore schemas in **Schema Explorer**

---

## 📁 Project Structure

```
dbcopilot/
│
├── app/                        # FastAPI backend
│   ├── api/
│   │   └── routes/
│   │       ├── connections.py      # Connection CRUD + test + sync
│   │       ├── metadata.py         # Schema/table/column browser
│   │       └── ai_placeholders.py  # Future AI endpoints
│   │
│   ├── connectors/             # External DB connector layer
│   │   ├── base.py                 # Abstract BaseConnector
│   │   ├── postgres.py             # PostgreSQL (asyncpg)
│   │   ├── mysql.py                # MySQL (aiomysql)
│   │   ├── sqlserver.py            # SQL Server (aioodbc)
│   │   └── mongo.py                # MongoDB (motor)
│   │
│   ├── services/               # Business logic
│   │   ├── connection_service.py   # Connection lifecycle
│   │   └── sync_service.py         # Schema introspection + persistence
│   │
│   ├── models/
│   │   └── metadata.py         # SQLAlchemy ORM models
│   │
│   ├── schemas/
│   │   └── api_schemas.py      # Pydantic request/response models
│   │
│   ├── db/
│   │   ├── session.py          # Async SQLAlchemy session
│   │   └── init_db.py          # Table creation on startup
│   │
│   ├── core/
│   │   ├── config.py           # Pydantic settings (loads from .env)
│   │   ├── security.py         # Credential encryption/decryption
│   │   └── logging.py          # Logging configuration
│   │
│   ├── utils/
│   │   └── helpers.py          # Shared utilities
│   │
│   ├── workflows/              # Future AI agent workflows
│   │   └── text_to_sql.py      # Stub: LangGraph text-to-SQL
│   │
│   └── main.py                 # FastAPI app factory + lifespan
│
├── ui/                         # Streamlit frontend
│   ├── app.py                      # Home page
│   ├── components/
│   │   └── api_client.py           # HTTP client for FastAPI
│   └── pages/
│       ├── 1_connect_database.py   # Credential form
│       ├── 2_connected_sources.py  # Connection management
│       ├── 3_schema_explorer.py    # Schema hierarchy browser
│       ├── 4_chat.py               # AI chat (placeholder)
│       └── 5_settings.py           # Health + future config
│
├── docker/
│   └── postgres/
│       └── init.sql            # DB bootstrap (extensions + grants)
│
├── tests/
│   ├── conftest.py
│   ├── test_connection_service.py
│   ├── test_connectors.py
│   └── test_api_routes.py
│
├── scripts/
│   ├── start.sh                # Start all services
│   ├── stop.sh                 # Stop all services
│   └── generate_key.py         # Generate Fernet encryption key
│
├── alembic/                    # DB migrations
│   └── env.py
│
├── Dockerfile.api              # FastAPI multi-stage image
├── Dockerfile.streamlit        # Streamlit image
├── docker-compose.yml          # Full stack orchestration
├── requirements.txt            # Backend dependencies
├── requirements.streamlit.txt  # Frontend dependencies
└── .env.example                # Environment template
```

---

##  Supported Databases

| Database       | Driver         | Status |
|----------------|----------------|--------|
| PostgreSQL      | asyncpg        |  Full support |
| MySQL / MariaDB | aiomysql       |  Full support |
| SQL Server      | aioodbc        |  Full support |
| MongoDB         | motor          |  Collections + type inference |

---

## 🗄 Internal Metadata Schema

All discovered schema metadata is stored in the internal PostgreSQL instance:

```sql
connected_databases      -- registered external data sources
  └── database_schemas   -- schemas within each database
      └── database_tables    -- tables and views
          ├── database_columns       -- column details (type, PK, FK, nullable...)
          └── database_relationships -- FK relationships between tables

sync_logs                -- audit trail for every sync run
```

---

## 🔒 Security

- **Passwords encrypted at rest** using Fernet (AES-128-CBC + HMAC-SHA256)
- **Read-only queries only** — connectors never issue INSERT/UPDATE/DELETE/DROP
- **Non-root Docker containers** — app runs as UID 1001
- **No credential logging** — passwords masked in all log output
- **Connection pooling** — controlled pool sizes per external DB

---

## 🧪 Running Tests

```bash
# Install test dependencies locally
pip install -r requirements.txt pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

---

## 🗺 API Reference

### Connections

| Method | Endpoint                         | Description                    |
|--------|----------------------------------|--------------------------------|
| POST   | `/api/v1/connections/test`       | Test credentials (no persist)  |
| POST   | `/api/v1/connections`            | Register new connection        |
| GET    | `/api/v1/connections`            | List all connections           |
| GET    | `/api/v1/connections/{id}`       | Get connection details         |
| POST   | `/api/v1/connections/{id}/sync`  | Sync schema from DB            |
| DELETE | `/api/v1/connections/{id}`       | Delete connection + metadata   |

### Metadata

| Method | Endpoint                                      | Description             |
|--------|-----------------------------------------------|-------------------------|
| GET    | `/api/v1/metadata/databases/{id}/schemas`     | List schemas            |
| GET    | `/api/v1/metadata/schemas/{id}/tables`        | List tables             |
| GET    | `/api/v1/metadata/tables/{id}/columns`        | List columns            |
| GET    | `/api/v1/metadata/tables/{id}/relationships`  | List FK relationships   |
| GET    | `/api/v1/metadata/databases/{id}/sync-logs`   | Sync history            |

### AI (Placeholders)

| Method | Endpoint                    | Description              |
|--------|-----------------------------|--------------------------|
| POST   | `/api/v1/ai/chat`           | Natural language chat    |
| POST   | `/api/v1/ai/generate-sql`   | Text-to-SQL              |

Full interactive docs: **http://localhost:8000/docs**

---

## 🚀 Activating the AI Layer (Future)

When you're ready to add AI capabilities:

1. **Uncomment** Redis and Qdrant in `docker-compose.yml`
2. **Add** OpenAI API key to `.env`
3. **Uncomment** AI packages in `requirements.txt`
4. **Implement** `app/workflows/text_to_sql.py`
5. **Wire** `app/api/routes/ai_placeholders.py` to the real pipeline

The schema metadata is already being collected and stored — the AI layer
just needs to be connected to it.

---

## 🛠 Development

### Hot-reload (default in dev)
The API and UI containers mount source code as volumes, so changes take
effect immediately without rebuilding:

```bash
docker compose up          # starts with --reload enabled
```

### Database migrations (Alembic)
```bash
# Generate a migration after model changes
alembic revision --autogenerate -m "add my new column"

# Apply migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

### Adding a new connector
1. Create `app/connectors/your_db.py` extending `BaseConnector`
2. Implement: `connect`, `disconnect`, `test_connection`, `get_databases`, `get_schemas`, `get_tables`, `get_columns`, `get_relationships`
3. Register in `app/connectors/__init__.py` `_REGISTRY`
4. Add driver to `requirements.txt`

---

