# AI Intelligence Architecture

## Executive Summary

This repository already contains the major building blocks of an AI-native metadata intelligence platform: connection ingestion, schema discovery, semantic enrichment, governance classification, relationship intelligence, KPI intelligence, embeddings, prompt studio, readiness scoring, and observability.

The current problem is not missing surface area. The problem is architectural coupling and contract drift:

- AI stages mix orchestration, prompt shaping, extraction, validation, and persistence.
- Downstream stages do not consistently consume upstream intelligence.
- Prompt payloads are too large and too loosely shaped for GPT-5 Nano.
- Some stages treat partial or empty AI responses as success-like outputs.
- Legacy compatibility aliases are still leaking into contracts and validators.
- The same “intelligence” concept is represented in multiple places with different shapes.

The target architecture should keep the system metadata-first, but make it AI-native:

- services orchestrate
- AI reasons
- persistence stores normalized intelligence packages
- downstream stages consume prior intelligence packages
- prompts stay small, explicit, and stage-specific
- observability is a first-class control surface, not an afterthought

## Current Architecture

### Major subsystems in the repo

- `app/connectors/`: database-specific metadata ingestion
- `app/services/sync_service.py`: connection sync and metadata persistence
- `app/schema_engine/relationship_graph.py`: relationship graph building and cluster intelligence
- `app/services/database_semantic_service.py`: database-level semantic intelligence
- `app/services/column_semantic_service.py`: table/column governance and PII classification
- `app/services/kpi_intelligence_service.py`: KPI discovery and generation
- `app/services/readiness_service.py`: readiness assessment
- `app/services/prompt_studio_service.py`: generated prompt artifacts
- `app/schema_engine/embeddings.py` and `app/services/qdrant_service.py`: vector assets
- `app/services/ai_observability_service.py`: Azure OpenAI wrapper and LangSmith instrumentation
- `app/services/database_pipeline_orchestrator.py`: higher-level pipeline/job orchestration
- `app/api/routes/*`: API surfaces for all intelligence layers
- `ui/pages/*`: legacy UI contracts for connection, schema, relationships, semantic, governance, KPI, readiness, embeddings, prompt studio, and jobs

### Existing data model shape

The metadata store already contains the core persistence layers:

- `ConnectedDatabase`
- `DatabaseSchema`
- `DatabaseTable`
- `DatabaseColumn`
- `DatabaseRelationship`
- `SyncLog`
- `DatabaseSemantic`
- `SchemaSemantic`
- `ColumnSemantic`
- `SchemaRelationshipGraph`
- `ReadinessSnapshot`
- `ArtifactManifest`
- `PipelineJob`

### Existing AI integration shape

The repo currently uses Azure OpenAI through a centralized observability wrapper:

- `AIObservabilityService.generate(...)`
- GPT-5 models are used through Azure deployment settings
- LangSmith tracing is integrated and should remain enabled
- Prompt templates are stored under `app/prompts/`

## Problems

### 1. Contract drift between prompts and code

Relationship analysis has legacy aliases and evolving output fields. Governance and semantic stages also render prompts with variables that are not always populated.

### 2. Large prompts cause unstable completions

GPT-5 Nano is sensitive to prompt bloat. Some current payloads still include too much governance, too much legacy context, or too much unrelated metadata.

### 3. Empty response handling is too fragile

Some AI calls were treated as successful even when the model returned empty content or stopped at length without a usable payload.

### 4. Mixed responsibilities in services

Several services currently do all of the following in one class:

- build prompt input
- call the model
- parse JSON
- validate required fields
- normalize aliases
- persist rows
- update job metadata
- log observability data

That makes each stage brittle and hard to reason about.

### 5. Upstream intelligence is not consistently consumed downstream

Business domain, semantic summaries, and governance packages should feed later stages. In the current design, some stages still operate as if prior intelligence is optional or absent.

### 6. Legacy compatibility is still baked into the runtime path

Backwards-compatible aliases are useful for migration, but they should not define the target contract.

## Technical Debt

- Prompt contracts are larger than necessary.
- JSON parsing and output validation are scattered across services.
- Some stages infer defaults that should be explicit contract requirements.
- Relationship intelligence currently carries both target fields and legacy field names.
- Governance and semantic stages are partly dependent on each other but the dependency flow is not consistently enforced.
- Observability is good, but it needs more structured response capture and failure persistence.

## Production Risks

- GPT-5 Nano truncation and empty outputs on oversized prompts.
- Silent success states with empty content.
- Downstream artifacts built from incomplete or stale upstream intelligence.
- Validator/prompt mismatch causing runtime exceptions.
- Prompt bloat increasing latency and token spend.
- Duplicate logic across services leading to divergent behaviors in UI, API, and sync flows.

## Target Architecture

The platform should become a staged intelligence pipeline with one responsibility per layer:

- connectors collect metadata
- services orchestrate
- prompts ask focused questions
- Azure OpenAI reasons over compact packages
- persistence stores structured intelligence packages
- downstream stages consume upstream packages

### Pipeline Diagram

```text
Connection
  → Metadata
  → Governance
  → Semantic Intelligence
  → Relationship Intelligence
  → KPI Intelligence
  → Embeddings
  → Prompt Studio
  → Readiness
  → Agent Layer
```

## Intelligence Contracts

Each stage should have four explicit contracts:

- Inputs
- Outputs
- Persistence Models
- API Contracts

### 1. Governance Architecture

#### Inputs

- `ConnectedDatabase`
- `DatabaseSchema`
- `DatabaseTable`
- `DatabaseColumn`
- optional database semantic summary

#### Output Governance Package

Per table:

- `table_summary`
- `business_purpose`
- `resolved_columns[]`
- each resolved column:
  - `column_name`
  - `is_pii`
  - `pii_type`
  - `risk_level`
  - `confidence_score`
  - `business_meaning`
  - `governance_reasoning`

#### Persistence Models

- `ColumnSemantic`
- governance summary fields within `DatabaseSemantic` if needed

#### API Contracts

- table-level governance generation
- database-level governance summary
- manual re-run by table or database

#### How downstream stages consume it

- relationship stage uses PII-aware masking and sensitivity context
- readiness stage uses governance coverage and risk distribution
- embeddings stage masks protected fields
- prompt studio uses governance signals to shape generated context

### 2. Semantic Architecture

#### Inputs

- metadata package
- governance package
- database-level schema inventory

#### Output Semantic Package

- `business_domain`
- `business_capabilities[]`
- `business_entities[]`
- `business_processes[]`
- `semantic_summary`
- `analysis_notes`
- `table_semantics[]`

#### Persistence Models

- `DatabaseSemantic`
- `SchemaSemantic`

#### API Contracts

- generate database semantic intelligence
- retrieve stored semantic package
- expose semantic summary for dependent stages

#### Downstream consumption

- governance should receive semantic context when available
- relationship intelligence uses semantic domain and business processes
- KPI uses business entities and business processes
- prompt studio uses semantic summary as the top-level grounding layer

### 3. Relationship Architecture

#### Inputs

- governance package
- semantic package
- metadata graph
- FK graph
- cluster metadata

#### Output Relationship Package

Target contract:

- `cluster_summary`
- `cluster_confidence`
- `entity_graph[]`
- `hidden_relationships[]`
- `lifecycle_flows[]`

Optional downstream-enrichment fields may exist in persistence, but they should not define the prompt contract.

#### Persistence Models

- `SchemaRelationshipGraph`

#### API Contracts

- build relationship graph by database
- build relationship graph by table neighborhood
- expose graph snapshots for UI and downstream services

#### Downstream consumption

- KPI discovery should use cluster intelligence
- readiness should use graph completeness and hidden relationship coverage
- prompt studio should reuse the resolved graph context

### 4. KPI Architecture

#### Inputs

- governance package
- semantic package
- relationship package

#### Output KPI Package

- candidate metrics
- business definitions
- grain assumptions
- dependencies
- recommended KPI formulas

#### Persistence Models

- KPI-specific tables if already present or new KPI intelligence table if not

#### API Contracts

- generate KPIs for a database
- retrieve KPI suggestions and lineage

### 5. Embedding Architecture

#### Inputs

- governance package
- semantic package
- relationship package

#### Output Vector Assets

- chunked semantic documents
- table-level embedding docs
- relationship-aware documents
- prompt studio artifacts ready for retrieval

#### Persistence Models

- existing embedding models and Qdrant collections

#### API Contracts

- generate embeddings by database
- query semantic retrieval

### 6. Prompt Studio Architecture

#### Inputs

- governance package
- semantic package
- relationship package
- KPI package
- readiness signals

#### Output Generated Artifacts

- database context
- system prompt
- RAG context
- agent context
- text-to-SQL context
- database intelligence package

#### Persistence Models

- `ArtifactManifest`

#### API Contracts

- generate artifacts from the latest intelligence packages
- list generated artifacts
- export artifacts

### 7. Readiness Architecture

#### Inputs

- governance package
- semantic package
- relationship package
- KPI package
- embedding status
- prompt artifacts

#### Output Readiness Assessment

- readiness score
- readiness dimensions
- blockers
- warnings
- action items

#### Persistence Models

- `ReadinessSnapshot`

#### API Contracts

- recompute readiness
- retrieve readiness history

### 8. Agent Architecture

#### Inputs

- governance package
- semantic package
- relationship package
- KPI package
- embeddings
- prompt artifacts
- readiness status

#### Output Agent Intelligence

- grounded assistant context
- retrieval configuration
- safe response rules
- tool routing hints

#### Persistence Models

- if needed, future agent registry or agent profile table

#### API Contracts

- generate agent-ready bundle
- consume all upstream intelligence packages

## Governance Architecture

### Input Metadata

Governance should receive only compact metadata:

- database name
- business domain if already known
- schema name
- table name
- table description
- columns with name, type, and description

### Output Governance Package

The output must be compact and deterministic in shape:

- `table_summary`
- `business_purpose`
- `resolved_columns[]`

### Downstream Consumption

- relationship intelligence should use PII awareness to avoid exposing protected identifiers
- prompt studio should reflect governance-sensitive areas
- readiness should count governance completeness and risk concentration
- embeddings should mask or skip protected content when configured

### Governance design principle

No hardcoded PII heuristics should define final truth. The LLM should reason from metadata, and the system should validate the returned contract, not invent classifications.

## Semantic Architecture

### Input

- metadata graph
- governance package

### Output

- business domain
- summary
- key entities
- capabilities
- processes
- table semantics

### Role

Semantic intelligence is the bridge between raw metadata and business context.

It should be the first AI stage after metadata is persisted, so downstream stages can consume business context instead of re-deriving it.

## Relationship Architecture

### Input

- governance package
- semantic package
- metadata graph

### Output

- cluster summary
- cluster confidence
- entity graph
- hidden relationships
- lifecycle flows

### Role

Relationship intelligence should:

- discover declared and hidden relationships
- reason about business-level flow across tables
- batch large clusters to stay within GPT-5 Nano limits
- persist graph intelligence in normalized rows

## KPI Architecture

### Input

- governance package
- semantic package
- relationship package

### Output

- KPI candidates
- metric definitions
- dimensional assumptions
- lineage hints

### Role

KPI intelligence should be a consumer of earlier intelligence, not another raw metadata parser.

## Embedding Architecture

### Input

- governance package
- semantic package
- relationship package

### Output

- vectorized context units
- retrievable documents

### Role

Embeddings should preserve business context and respect governance masking.

## Prompt Studio Architecture

### Input

- all intelligence packages

### Output

- reusable prompt artifacts
- system prompt
- RAG prompt
- agent prompt

### Role

Prompt generation should use the latest stored packages and not regenerate business meaning on its own.

## Readiness Architecture

### Input

- all intelligence packages

### Output

- readiness score
- blockers
- suggestions

### Role

Readiness should answer: “Is this database ready for AI consumption?”

## Agent Architecture

### Input

- all intelligence packages

### Output

- agent-ready policy bundle
- context package
- safe retrieval instructions

### Role

The agent layer should consume already-produced intelligence, not recreate it.

## Database Changes

### Required migrations

The current schema already includes many needed tables. Any future migrations should focus on normalization and contract alignment, not duplicate storage.

### New tables

Potential future additions if the product matures:

- `governance_packages`
- `semantic_packages`
- `relationship_packages`
- `kpi_packages`
- `agent_packages`
- `intelligence_runs`

These are not mandatory if the existing models are extended cleanly, but they may be the right long-term direction if stage outputs need versioned snapshots.

### Deprecated tables

Legacy or redundant representations should be phased out if they duplicate normalized intelligence packages or create conflicting truth sources.

## API Changes

### Needed direction

- stage-specific generation endpoints should expose explicit input/output contracts
- sync endpoints should trigger the pipeline, not embed AI logic
- job/status APIs should expose stage outputs and failure reasons
- retrieval APIs should fetch persisted intelligence packages

### Contract consistency

The API layer should not invent schema rules. It should expose stored intelligence in the same shape that downstream consumers use.

## UI Changes

### Needed direction

The frontend should show:

- latest package per stage
- status and failure reason
- token usage and latency
- prompt version
- raw response preview in development mode
- stage dependencies

### UI contract principle

UI should render stored intelligence, not call stage logic directly.

## Observability Changes

### Required signals

- request id / trace id
- prompt id
- prompt version
- model / deployment
- finish reason
- prompt tokens
- completion tokens
- total tokens
- latency
- raw response
- parse result
- persistence status

### Logging standards

- log raw Azure response before extraction
- log final parsed content
- log failure reason when parsing fails
- log stage-level success/failure separately from request success/failure

## Prompt Design Standards

- keep each prompt stage-specific
- keep payloads compact
- avoid legacy contract fields in new prompts
- do not mix business reasoning and persistence concerns
- always define required output keys explicitly
- prefer compact JSON only for AI-generated outputs
- use defensive rendering defaults for optional context

## Token Budget Standards

Suggested budgets for GPT-5 Nano:

- semantic database summary: compact, under a few thousand tokens total input
- governance per table batch: keep table payloads small, favor batching
- relationship cluster batches: keep per-batch payloads bounded and deterministic
- prompt studio: should consume persisted packages, not raw metadata dumps

General standard:

- favor multiple small, valid calls over one large unstable call
- batch by logical scope, not by arbitrary text length only
- prefer predictable contracts over free-form explanation

## Rollout Plan

### Phase 1

- finalize architecture contracts
- align prompts with persistence shapes
- align observability with failure handling

### Phase 2

- normalize governance, semantic, and relationship package persistence
- remove contract drift and legacy aliases from target paths
- ensure downstream consumers use stored packages

### Phase 3

- split orchestration from generation logic more cleanly
- add explicit package versioning and stage snapshots
- make UI consume package snapshots consistently

### Phase 4

- strengthen readiness, KPI, embeddings, and prompt studio around the new packages
- introduce package lineage and run history

### Phase 5

- add agent-layer package assembly
- deprecate redundant legacy output pathways
- optimize for large enterprise databases and long-lived sync history

## Progress

- Phase 1: complete
- Phase 2: complete
- Phase 3: complete
- Completed implementation scope: canonical stage contract schemas aligned to the architecture target shapes
- Completed implementation scope for phase 2: canonical governance package persistence and semantic package retrieval contract
- Governance implementation phase: complete
- Governance package now persists as a first-class table and is exposed through dedicated governance APIs
- Completed implementation scope for semantic phase: canonical semantic package persistence, package retrieval APIs, and semantic dashboard contract
- Completed implementation scope for relationship phase: canonical relationship package persistence, cluster telemetry, and relationship package APIs
- Remaining phase 4 work: KPI/package consumption alignment and any required downstream UI/API wiring
- No later phases have been started

## Repository-Specific Findings

Based on the current codebase, these are the most important architecture observations:

- `app/services/sync_service.py` is currently the main operational sync path and already sequences semantic generation before relationship graph building.
- `app/services/database_pipeline_orchestrator.py` defines the higher-level stage graph, but still has to stay aligned with the sync path.
- `app/services/ai_observability_service.py` is the right place for Azure OpenAI instrumentation, tracing, and response capture.
- `app/services/database_semantic_service.py` is the right place for database-level semantic persistence, but it should remain focused on orchestration and storage, not prompt parsing logic beyond contract validation.
- `app/services/column_semantic_service.py` should remain table-level governance orchestration and persistence.
- `app/schema_engine/relationship_graph.py` is currently doing too much: graph creation, batching, prompt shaping, parsing, validation, and persistence. That should be simplified in the next implementation phase.
- `app/prompts/*` already contains the right prompt families, but prompt payloads and required output contracts need to stay aligned with code.

## Decision Summary

The target system should be:

- metadata-first
- AI-native
- contract-driven
- stage-batched
- observability-rich
- persistence-backed
- downstream-aware

The near-term goal is not “more AI.” It is “better intelligence flow”:

- collect metadata
- generate semantic meaning
- classify governance
- synthesize relationships
- derive KPIs
- build embeddings
- generate prompt artifacts
- score readiness
- assemble agent intelligence
