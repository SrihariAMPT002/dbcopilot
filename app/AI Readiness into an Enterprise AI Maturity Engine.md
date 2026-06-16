# AI Readiness Redesign — Enterprise AI Maturity Engine

Redesign the AI Readiness module into an Enterprise AI Maturity Engine.

This module is the final intelligence layer of the platform.

Its purpose is NOT to display a single score.

Its purpose is to answer:

* Is this database AI ready?
* Is it safe for agents?
* Is it ready for RAG?
* Is Text-to-SQL reliable?
* What prevents production deployment?
* What should be fixed next?

Follow existing repository structure.

Reuse:

* AI observability
* trace_id
* package architecture
* migrations
* ORM patterns
* APIs
* frontend architecture

Do NOT create parallel systems.

AI Readiness consumes ALL previous stages.

---

# Architecture Dependency

AI Readiness depends on:

Metadata
→ Governance Package
→ Semantic Package
→ Relationship Package
→ KPI Package
→ Prompt Package
→ Embeddings Package
→ Retrieval Metrics
→ Agent Memory
→ AI Readiness

No stage should bypass package persistence.

Consume persisted packages only.

---

# 1. AI Readiness Snapshot

Create:

app/models/ai_readiness_snapshot.py

Migration:

add_ai_readiness_snapshots_table.py

Fields:

* id
* database_id
* overall_score
* maturity_level
* summary
* confidence_score
* evidence
* trace_id
* model_name
* created_at
* updated_at

Readiness snapshots must be versioned.

Each run creates a new snapshot.

Do not overwrite history.

---

# 2. Readiness Dimensions

AI readiness is multi-dimensional.

Create:

app/models/ai_readiness_dimension.py

Migration:

add_ai_readiness_dimensions_table.py

Fields:

* id
* snapshot_id
* dimension_name
* score
* confidence_score
* evidence
* recommendations
* created_at

Supported dimensions:

* governance_readiness
* semantic_readiness
* relationship_readiness
* retrieval_readiness
* rag_readiness
* text_to_sql_readiness
* prompt_readiness
* agent_readiness
* analytics_readiness
* overall_ai_maturity

Do NOT hardcode scoring.

AI should infer scoring dynamically.

---

# 3. Maturity Levels

Infer maturity dynamically.

Examples only:

Level 1:
Exploration

Level 2:
Managed

Level 3:
Operational

Level 4:
AI Ready

Level 5:
Autonomous Enterprise

These are illustrative only.

AI determines maturity.

Do not hardcode thresholds.

---

# 4. Remediation Engine

This is a differentiator.

Create:

app/models/remediation_action.py
app/services/remediation_service.py

Migration:

add_remediation_actions_table.py

Fields:

* issue
* recommendation
* expected_impact
* priority
* confidence_score
* evidence
* trace_id

AI generates remediation actions.

Examples only:

Issue:
Low relationship coverage

Recommendation:
Define foreign keys between customers and orders

Expected Impact:
Increase RAG quality by improving graph retrieval

Never hardcode recommendations.

AI must infer them dynamically.

---

# 5. Readiness Scoring Service

Create:

app/services/readiness_scoring_service.py

Responsibilities:

* aggregate package metrics
* compute readiness dimensions
* normalize scores
* persist snapshots

Consume:

* governance_packages
* semantic_packages
* relationship_packages
* kpi_packages
* prompt_packages
* embedding_documents
* retrieval_evaluations
* agent_memory

Do not compute from raw metadata if packages exist.

---

# 6. AI Readiness Service

Create:

app/services/ai_readiness_service.py

Responsibilities:

* orchestrate readiness generation
* call AI
* validate output
* persist snapshots
* trigger remediation

Reuse AI observability.

Persist:

* trace_id
* token usage
* model name
* execution status
* failure reason

---

# 7. Retrieval Readiness

Readiness must evaluate retrieval quality.

Consume:

* retrieval precision
* recall
* MRR
* NDCG
* cache hit rate
* reranker quality
* graph coverage

Generate:

retrieval_readiness score.

This score powers RAG readiness.

---

# 8. Agent Readiness

Evaluate:

* semantic coverage
* governance coverage
* prompt quality
* retrieval quality
* memory quality

Generate:

agent_readiness score.

Explain:

Why agents may fail.

Provide remediation.

---

# 9. Text-to-SQL Readiness

Evaluate:

* schema quality
* relationship coverage
* business glossary coverage
* semantic completeness
* prompt quality

Generate:

text_to_sql_readiness score.

Provide recommendations.

---

# 10. Prompt Readiness

Consume:

* prompt quality scores
* prompt evaluation metrics
* observability logs
* hallucination risk

Generate:

prompt_readiness score.

---

# 11. Explainability

AI must explain:

Why each score exists.

Persist:

* evidence
* packages used
* reasoning summary

Examples:

"RAG readiness is reduced because relationship coverage is incomplete."

"Agent readiness is high due to strong governance and retrieval quality."

No hardcoded text.

AI generates explanations dynamically.

---

# 12. Prompt Files

Create:

app/prompts/readiness/

ai_readiness.yaml
governance_readiness.yaml
rag_readiness.yaml
agent_readiness.yaml
text_to_sql_readiness.yaml
remediation.yaml

Prompt rules:

* AI-first inference
* package-driven
* explainable
* confidence scored
* no hardcoded domain logic

Examples are illustrative only.

All prompts must contain:

* constraints
* output schema
* examples

Follow prompt registry requirements.

---

# 13. APIs

Create:

GET /readiness/{db_id}
GET /readiness/history/{db_id}
GET /readiness/remediation/{db_id}
POST /readiness/recalculate/{db_id}

Follow existing API conventions.

---

# 14. Frontend Architecture

Follow:

routes → routing only
pages → screen composition only
components → UI only
hooks → data fetching
services → business logic
api → transport
types → backend contracts

No API calls inside pages.

---

# 15. Frontend Components

Create:

frontend/src/components/readiness/

ReadinessOverview.tsx
DimensionScoreCard.tsx
RadarChart.tsx
RemediationPanel.tsx
TrendChart.tsx
AIRecommendations.tsx

---

# 16. Hooks

Create:

useReadiness.ts
useReadinessHistory.ts
useRemediation.ts

---

# 17. Services

Create:

readinessService.ts
remediationService.ts

---

# 18. UI Design

AI Readiness page tabs:

1. Overview
2. Dimensions
3. Retrieval
4. Agents
5. Text-to-SQL
6. RAG
7. Remediation
8. History

Display:

* Overall AI Score
* Maturity Level
* Dimension Scores
* Trend History
* Top Risks
* Recommendations
* Confidence
* Last Evaluation
* Trace ID

---

# 19. Dashboard Integration

Expose metrics for dashboard:

* AI Maturity Score
* Agent Score
* RAG Score
* Prompt Score
* Retrieval Quality
* Top Risks
* Critical Actions

Dashboard consumes readiness snapshots.

Do not recompute.

---

# 20. Constraints

* No hardcoded scoring
* No healthcare assumptions
* No insurance assumptions
* AI-driven inference only
* Package-first architecture
* Reuse observability
* Reuse migrations
* Reuse trace_id
* Reuse package patterns

Final goal:

Transform AI Readiness into an Enterprise AI Maturity Engine that explains not only current capability, but also how to become production-ready for AI.
