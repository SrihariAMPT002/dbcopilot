# DB Copilot

## Overview

DB Copilot is an AI Context Engineering Platform that transforms enterprise databases into AI-ready business context.

The platform connects to enterprise databases, discovers metadata, builds semantic understanding, generates retrieval-ready knowledge, and produces reusable AI context artifacts for chatbots, AI agents, RAG systems, copilots, and Text-to-SQL applications.

---

# Key Capabilities

* Database Connectivity
* Metadata Discovery
* Schema Exploration
* Relationship Graph Generation
* Semantic Intelligence
* Embeddings & Retrieval
* Prompt Studio
* AI Readiness Assessment
* Artifact Export Framework

---

# High-Level Architecture

External Databases
↓
Metadata Discovery
↓
Schema Explorer
↓
Relationship Graph
↓
Semantic Intelligence
↓
Embeddings & Retrieval
↓
Prompt Studio
↓
AI Context Artifacts

---

# Technology Stack

## Backend

* FastAPI
* Python 3.11
* SQLAlchemy
* Alembic
* Pydantic

## Frontend

* Streamlit

## Databases

* PostgreSQL
* MySQL
* SQL Server
* MongoDB

## AI & Semantic Layer

* Azure OpenAI
* OpenAI SDK
* Qdrant
* Vector Embeddings

## Infrastructure

* Docker
* Docker Compose

---

# Repository Structure

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

---

# Core Modules

## Connect Database

Responsible for secure database connectivity and metadata synchronization.

## Schema Explorer

Provides visibility into schemas, tables, columns, and relationships.

## Relationship Graph

Builds entity relationships and dependency mapping.

## Semantic Intelligence

Generates business summaries, glossary terms, business entities, and use cases from metadata.

## Embeddings & Retrieval

Creates vector-searchable schema intelligence and semantic search capabilities.

## Prompt Studio

Generates AI-ready artifacts:

* Database Context
* System Prompt
* RAG Context
* Agent Context
* Text-to-SQL Context

## AI Readiness

Evaluates how prepared a database is for AI-driven applications.

---

# Prerequisites

Required:

* Docker 24+
* Docker Compose 2+
* Python 3.11+

Optional:

* Azure OpenAI Account
* Qdrant Instance

---

# Environment Setup

Create:

.env

Required variables:

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

---

# Running Locally

Clone repository:

git clone <repo-url>

cd dbcopilot

Create environment file:

cp .env.example .env

Start services:

docker compose up --build

---

# Access URLs

Frontend

http://localhost:8501

Backend API

http://localhost:8000

Swagger Documentation

http://localhost:8000/docs

Health Endpoint

http://localhost:8000/health

---

# Development Workflow

Create Migration

alembic revision --autogenerate -m "message"

Apply Migration

alembic upgrade head

Rollback Migration

alembic downgrade -1

Run Tests

pytest tests/

---

# Security

* Credentials encrypted at rest
* Secrets stored in environment variables
* No secrets committed to Git
* No secrets baked into Docker images
* Read-only metadata extraction

---

# Troubleshooting

Common Issues

Migration Failures

alembic upgrade head

Docker Rebuild

docker compose down -v

docker compose build --no-cache

docker compose up

Container Logs

docker compose logs -f

---

# License

Internal Project
Confidential
