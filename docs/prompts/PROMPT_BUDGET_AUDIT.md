# GPT-5 Nano Prompt Budget Audit

Source of truth:
- `app/config/ai_models.yaml`
- `app/prompts/**`

## Summary

GPT-5 Nano in this repository is used for structured reasoning workloads, not simple chat. The dominant failure mode has been `finish_reason=length` with empty content, which indicates prompt budgets were too tight for the amount of reasoning and JSON output required.

## Updated Budget Guidance

| Area | Current | Recommended | Risk |
| --- | ---: | ---: | --- |
| Governance | 2000 | 3000 | Medium |
| Semantics | 2000 | 4000 | Medium |
| Relationships | 2500 | 8000 | High |
| KPI | 1200 | 5000 | High |
| Prompt Studio Generation | 2400 | 8000 | High |
| Prompt Studio Optimization | 1800 | 6000 | Medium |
| Prompt Studio Evaluation | 1200 | 3000 | Medium |
| Readiness | 2500 | 6000 | High |
| Retrieval / Rerank / Evaluation | 800-1000 | 3000 | Medium |

## Notes

- Keep metadata-only prompts at `max_completion_tokens: 0`.
- Use package-first inputs wherever persisted packages exist.
- Prefer explicit JSON schemas and concise evidence fields over narrative outputs.
- If `finish_reason=length` persists, reduce input context before increasing budgets further.

## Files Updated

- `app/config/ai_models.yaml`
- `app/prompts/semantic/pii_classification.yaml`
- `app/prompts/semantic/database_analysis.yaml`
- `app/prompts/relationship/relationship_discovery.yaml`
- `app/prompts/relationship/business_relationship_analysis.yaml`
- `app/prompts/prompt_studio/prompt_generation.yaml`
- `app/prompts/prompt_studio/prompt_optimization.yaml`
- `app/prompts/prompt_studio/prompt_evaluation.yaml`
- `app/prompts/kpi/kpi_candidate_discovery.yaml`
- `app/prompts/readiness/ai_readiness_assessment.yaml`
- `app/prompts/embedding/retrieval.yaml`
- `app/prompts/embedding/reranker.yaml`
- `app/prompts/embedding/retrieval_evaluation.yaml`
- `app/prompts/embedding/graph_retrieval.yaml`
- `app/prompts/system/system_prompt.yaml`
- `app/prompts/system/database_context.yaml`
- `app/prompts/system/rag_context.yaml`
