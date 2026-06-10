# DB Copilot - Product Architecture Principles

## Mission

DB Copilot is a Database Intelligence Platform.

It does not generate prompts from metadata.

It generates reusable intelligence about databases that can power:

* AI Agents
* RAG Systems
* Text-to-SQL
* Analytics Copilots
* Executive Assistants
* Governance Systems
* KPI Intelligence

---

# System Flow

Database
↓
Metadata Discovery
↓
Governance Intelligence
↓
Semantic Intelligence
↓
Relationship Intelligence
↓
KPI Intelligence
↓
Context Package Generation
↓
AI Consumption Layer

---

# Stage 1 - Metadata Discovery

Purpose:

Create an accurate structural representation of the database.

Output:

* Schemas
* Tables
* Columns
* Data Types
* Constraints
* Indexes

Storage:

* database_tables
* database_columns
* database_schemas

No AI should run here.

---

# Stage 2 - Governance Intelligence

Purpose:

Understand risk before AI touches the data.

Responsibilities:

* PII Detection
* Sensitive Data Detection
* Regulatory Classification
* Data Risk Assessment

Storage:

* column_semantics

Architecture:

Rule Engine
↓
Table-Level AI Classification
↓
Column-Level Fallback

Never:

* One Azure call per column
* One Azure call per value

Governance is the system of record.

Everything downstream consumes governance outputs.

---

# Stage 3 - Semantic Intelligence

Purpose:

Understand business meaning.

Examples:

orders
customers
claims
policies
payments

Output:

* Business summaries
* Business entities
* Domain language
* Business glossary

Storage:

* database_semantics
* schema_semantics

AI calls:

Database-level
Table-level

Never column-level.

---

# Stage 4 - Relationship Intelligence

Purpose:

Understand business processes.

Examples:

Customer
→ Policy
→ Claim
→ Payment

Output:

* Entity graph
* Process flows
* Upstream dependencies
* Downstream dependencies

Storage:

* schema_relationship_graph

Important:

Never send the entire schema to one AI prompt.

Use:

Relationship Clusters
↓
Entity Groups
↓
Process Analysis

Then aggregate.

---

# Stage 5 - KPI Intelligence

Purpose:

Discover measurable business outcomes.

Examples:

Revenue
Retention
Claims Ratio
Inventory Turnover

Output:

* KPI Catalog
* KPI Formulas
* KPI Definitions
* KPI Sources

Storage:

kpi_intelligence

AI operates on:

Semantics
Relationships

not raw metadata.

---

# Stage 6 - Context Package Generation

Purpose:

Generate reusable intelligence packages.

Packages:

* Executive Package
* Business Analyst Package
* Text-to-SQL Package
* Agent Package
* RAG Package
* KPI Package
* Governance Package

Storage:

artifact_manifests

artifact_manifests is the system of record.

---

# AI Usage Rules

AI should never receive:

* Entire databases
* Entire schemas
* Raw PII values
* Large metadata dumps

AI should receive:

* Summaries
* Clusters
* Business entities
* Relationship groups

---

# Prompt Design Principles

Prompts are reasoning layers.

Prompts are not policy engines.

Governance Rules
↓
Prompt Template
↓
AI Reasoning

Rules belong in:

app/config/governance

Prompts belong in:

app/prompts

---

# Observability Rules

Every AI call must include:

* database_id
* prompt_id
* prompt_version
* model_name
* job_id
* module

Every AI call must be traceable.

Tracing failures must never fail business workflows.

---

# Job Architecture

Long-running operations must be jobs.

Jobs:

* Sync
* Governance
* Semantics
* Relationships
* KPI Intelligence
* Embeddings
* Artifact Generation

UI must expose:

* Running
* Completed
* Failed
* Progress
* Duration

Jobs Dashboard is mandatory.

---

# UI Architecture

Users should see:

1. Connected Sources
2. Jobs
3. Governance Intelligence
4. Semantic Intelligence
5. Relationship Intelligence
6. KPI Intelligence
7. Database Intelligence Studio
8. AI Readiness
9. Artifacts

Prompt Studio should be renamed:

Database Intelligence Studio

because users consume intelligence, not prompts.

---

# Success Criteria

A newly connected database should automatically generate enough intelligence that an AI system can:

* Understand the business domain
* Understand relationships
* Understand KPIs
* Understand governance restrictions
* Answer business questions accurately

without requiring SME intervention.
