# Pipeline Execution Audit

## Intended Order

1. Metadata Extraction
2. Governance Intelligence
3. Semantic Intelligence
4. Relationship Intelligence
5. KPI Intelligence
6. Prompt Studio
7. Embeddings & Retrieval
8. AI Readiness
9. Agents

## Runtime Entry Points

- `app/services/sync_service.py`
- `app/api/routes/connections.py`
- `app/api/routes/pipeline.py`
- `app/services/database_pipeline_orchestrator.py`
- background tasks queued from the connection sync and pipeline APIs

## Dependencies Now Reflected in Code

- Metadata → Governance
- Governance → Semantics
- Governance + Semantics → Relationships
- Governance + Semantics + Relationships → KPI
- KPI → Prompt Studio
- Prompt Studio → Embeddings
- Embeddings + Prompt Studio → Readiness

## Persistence Added

- `pipeline_executions`
- `stage_executions`

Each stage execution stores:
- `database_id`
- `stage_name`
- `status`
- `start_time`
- `end_time`
- `duration_seconds`
- `trace_id`
- `model_name`
- `token_usage_json`
- `error_message`
- `execution_order`

## Implemented Changes

- Sync flow now records explicit stage execution rows.
- Main sync order now runs Governance before Semantics.
- Prompt Studio now runs before Embeddings.
- Readiness runs after Embeddings.
- Pipeline stage graph was updated to match the package-first sequence.
- Pipeline job queue order was updated to include Prompt and Readiness before export-style work.

## Remaining Notes

- Business intelligence modules still run after readiness as a downstream package family.
- Retry logic still relies on existing pipeline job retry semantics.
- Incremental refresh is already enforced in readiness by package freshness checks, and can be extended to other stages using the same pattern.

