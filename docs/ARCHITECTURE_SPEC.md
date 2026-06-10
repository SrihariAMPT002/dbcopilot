# DB Copilot - Product & Engineering Architecture Specification

## 1. Product Mission

DB Copilot is a Database Intelligence Platform.

Its purpose is not to generate prompts.

Its purpose is to transform a raw database into a reusable intelligence layer that can power:

* AI Agents
* RAG Systems
* Text-to-SQL
* Analytics Assistants
* KPI Discovery
* Data Governance
* Executive Insights
* Knowledge Graphs

A user should be able to connect a database and automatically receive enough intelligence for an AI system to understand:

* What the business does
* What entities exist
* How entities interact
* What data is sensitive
* Which KPIs matter
* How questions should be answered

without requiring a human SME.

---

# 2. Core Principles

## Intelligence First

DB Copilot generates intelligence.

Prompts are implementation details.

The product should never be designed around prompts.

The product should be designed around intelligence outputs.

---

## Governance Before AI

AI should never be the first consumer of data.

Every database must pass through governance.

Order:

Metadata
→ Governance
→ Semantics
→ Relationships
→ KPI Intelligence
→ AI Consumption

---

## Intelligence Is Reusable

Every intelligence artifact must be reusable by:

* Agents
* RAG
* Search
* Analytics
* KPI Engines
* Prompt Studio
* Readiness

No intelligence should be generated for only one feature.

---

# 3. Platform Architecture

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
Knowledge Layer
↓
Context Package Generation
↓
AI Consumption Layer

---

# 4. Metadata Discovery Layer

Purpose:

Create an accurate technical representation.

Responsibilities:

* Schemas
* Tables
* Columns
* Views
* Indexes
* Constraints
* Foreign Keys
* Data Types

No AI allowed.

Output Tables:

database_schemas
database_tables
database_columns

Success Metric:

100% structural fidelity.

---

# 5. Governance Intelligence Layer

Purpose:

Protect the enterprise before AI touches data.

Responsibilities:

PII Detection
Sensitive Data Detection
Regulatory Classification
Risk Classification
Policy Enforcement

Output Table:

column_semantics

---

## Governance Architecture

Stage 1

Rule Engine

Input:

Column Name
Table Name
Description
Data Type

Examples:

email
eml
cust_email
phone
ph_no
aadhaar
ssn
passport

No AI.

---

Stage 2

Table Intelligence

Input:

Table Metadata
Semantic Context
Governance Rulebook

Output:

PII Classification
Risk Classification

One AI call per table.

Never one AI call per column.

---

Stage 3

Fallback Intelligence

Only unresolved columns.

Targeted AI call.

---

# 6. Semantic Intelligence Layer

Purpose:

Understand business meaning.

Examples:

customers
policies
claims
orders
suppliers

Output:

Business Glossary
Business Entities
Business Context
Business Vocabulary

Storage:

database_semantics
schema_semantics

---

## Semantic AI Strategy

Database Summary

One AI call per database.

Table Understanding

One AI call per table.

Never:

One AI call per column.

---

# 7. Relationship Intelligence Layer

Purpose:

Understand business processes.

Not technical relationships.

Business relationships.

Example:

Customer
→ Policy
→ Claim
→ Payment

Output:

Entity Graph
Process Graph
Lifecycle Graph
Dependency Graph

Storage:

schema_relationship_graph

---

## Relationship Architecture

Forbidden:

Entire database
↓
Single AI prompt

Allowed:

Database
↓
Entity Clustering
↓
Relationship Groups
↓
Process Analysis
↓
Aggregation

---

Relationship AI Input Limit

Maximum:

3-5 related tables per call

Never:

Entire schema

---

# 8. KPI Intelligence Layer

Purpose:

Discover measurable business outcomes.

Examples:

Revenue
Retention
Claims Ratio
Inventory Turnover
Customer Growth

Output:

KPI Catalog
Formula
Business Definition
Source Tables

Storage:

kpi_intelligence

---

## KPI Discovery Flow

Semantics
+
Relationships
↓
Candidate Metrics
↓
AI Reasoning
↓
KPI Catalog

Never operate directly on raw schema.

---

# 9. Knowledge Layer

Purpose:

Create a reusable database knowledge model.

Output:

Business Entities
Relationships
Glossary
Governance
KPIs

This becomes the foundation for all AI experiences.

---

# 10. Context Package Layer

Purpose:

Package intelligence for consumption.

Artifacts:

Executive Package
Governance Package
RAG Package
Agent Package
Text-to-SQL Package
KPI Package

Storage:

artifact_manifests

---

# 11. Prompt Architecture

Prompts are reasoning layers.

Prompts are not policy engines.

Rulebooks:

app/config/governance

Prompts:

app/prompts

Architecture:

Rulebook
↓
Prompt
↓
AI

Never:

Policy embedded in prompt.

Never:

Policy embedded in Python.

---

# 12. AI Architecture

Every Azure OpenAI call must:

Have prompt_id
Have prompt_version
Have model_name
Have database_id
Have job_id

All AI execution must be observable.

---

## AI Call Size Rules

Maximum Context:

Use summarized metadata.

Never send:

Entire schema
Entire database
Raw records
PII values

---

# 13. Observability Architecture

Provider:

LangSmith

Every run must contain:

database_id
job_id
module
prompt_id
prompt_version
model_name

Tracing failures must never fail business workflows.

---

# 14. Job Architecture

Long-running operations are jobs.

Examples:

Sync
Governance
Semantics
Relationships
KPIs
Embeddings
Artifacts

Storage:

pipeline_jobs

---

## Job Lifecycle

Queued
↓
Running
↓
Completed
↓
Failed

Every job must expose:

Progress
Duration
Status
Error

---

# 15. UI Architecture

Connected Sources

Jobs

Governance Intelligence

Semantic Intelligence

Relationship Intelligence

KPI Intelligence

Database Intelligence Studio

AI Readiness

Artifacts

---

Prompt Studio must not exist.

Replace with:

Database Intelligence Studio

because users consume intelligence, not prompts.

---

# 16. Database Design Rules

Never store prompts as business intelligence.

Store:

Intelligence

Not:

Prompt output only.

---

Every intelligence table must contain:

prompt_id
prompt_version
model_name
generated_at
quality_score

---

# 17. Engineering Rules

All relationships:

lazy="raise"

No runtime lazy loading.

Every relationship access must use:

selectinload()
joinedload()

before use.

---

No service may depend on UI.

No AI call may depend on Streamlit.

No prompt may contain governance policy.

No business logic may live inside prompts.

---

# 18. Definition of Done

A database is considered AI-ready when:

Governance Complete
✓

Semantic Intelligence Complete
✓

Relationship Intelligence Complete
✓

KPI Intelligence Complete
✓

Context Packages Generated
✓

AI Readiness Above Threshold
✓

At that point any external AI system should be able to answer business questions accurately using only DB Copilot intelligence artifacts.
