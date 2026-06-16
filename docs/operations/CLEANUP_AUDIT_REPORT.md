# Cleanup Audit Report

## Scope

Repository cleanup for `docs/` and `tests/`, focused on removing obsolete MVP-era material while preserving the current package-first architecture.

## Kept

### Docs

- `docs/architecture/AI_INTELLIGENCE_ARCHITECTURE.md`
- `docs/architecture/ARCHITECTURE_SPEC.md`
- `docs/architecture/ARCHITECTURE_STABILIZATION_REPORT.md`
- `docs/architecture/PRODUCT_ARCHITECTURE.md`
- `docs/prompts/PROMPT_BUDGET_AUDIT.md`
- `docs/frontend/STREAMLIT_TO_REACT_MAPPING.md` renamed in-place to a parity mapping reference
- `docs/operations/PIPELINE_EXECUTION_AUDIT.md`
- `docs/operations/IMPLEMENTATION_REPORT.md`
- `docs/operations/IMPLEMENTATION_REPORT_PHASE_2.md`

### Tests

- `tests/test_ai_observability_service.py`
- `tests/test_ai_observability_wrapper.py`
- `tests/test_api_routes.py`
- `tests/test_artifact_type_enum.py`
- `tests/test_azure_connectivity.py`
- `tests/test_column_semantic_service.py`
- `tests/test_connection_service.py`
- `tests/test_connectors.py`
- `tests/test_database_semantics.py`
- `tests/test_embeddings_retrieval.py`
- `tests/test_end_to_end_sync.py`
- `tests/test_governance_pipeline.py`
- `tests/test_governance_readiness.py`
- `tests/test_metadata_sanitizer.py`
- `tests/test_prompt_studio.py`
- `tests/test_readiness_service.py`
- `tests/test_relationship_graph.py`
- `tests/test_relationship_pipeline.py`
- `tests/test_semantic_pipeline.py`
- `tests/test_semantic_v3.py`
- `tests/manual/*` diagnostic scripts

## Updated

- `docs/architecture/AI_INTELLIGENCE_ARCHITECTURE.md`
  - removed direct Streamlit wording in favor of legacy UI references
- `docs/architecture/ARCHITECTURE_SPEC.md`
  - removed Streamlit-specific dependency wording
- `docs/frontend/STREAMLIT_TO_REACT_MAPPING.md`
  - renamed the framing to a legacy UI parity reference
  - updated wording so React is the active frontend implementation

## Removed

- `tests/test_BackgroundTasks.py`
  - obsolete manual background-task script
- `tests/test_relationship_v3.py`
  - legacy alias compatibility test for deprecated relationship field names

## Newly Added

- `docs/architecture/`
- `docs/frontend/`
- `docs/operations/`
- `docs/prompts/`
- `docs/operations/CLEANUP_AUDIT_REPORT.md`

## Notes

- No backend or frontend functionality was changed in this cleanup pass.
- Generated `__pycache__` directories were left untouched because they are transient runtime artifacts and not part of the tracked source structure.
- The current test suite still covers persistence, orchestration, observability, prompt registry, readiness, and API behavior through the retained integration and service tests.
