# Streamlit to React Mapping

This document maps the current Streamlit frontend to the target React frontend without redesigning business workflows.

## Source Of Truth

- Existing Streamlit app under `ui/`
- Existing FastAPI backend
- Existing intelligence pipeline and package APIs

## Navigation Mapping

| Streamlit Page | Purpose | React Target |
| --- | --- | --- |
| `ui/app.py` | Home dashboard and platform overview | `pages/DashboardPage` |
| `ui/pages/1_connect_database.py` | Connection setup and onboarding | `pages/ConnectionsPage` |
| `ui/pages/2_connected_sources.py` | Connected sources list and source actions | `pages/ConnectionsPage` + `components/connections` |
| `ui/pages/3_schema_explorer.py` | Metadata explorer for schemas, tables, columns | `pages/DatabaseExplorerPage` |
| `ui/pages/4_relationship_graph.py` | Relationship graph, lineage, dependency paths | `pages/RelationshipPage` |
| `ui/pages/5_semantic_intelligence.py` | Semantic intelligence and semantic packages | `pages/SemanticsPage` |
| `ui/pages/6_ai_readiness.py` | Readiness scoring and remediation | `pages/ReadinessPage` |
| `ui/pages/7_embeddings_retrieval.py` | Embeddings, Qdrant status, semantic search | `pages/EmbeddingsPage` |
| `ui/pages/8_prompt_studio.py` | Prompt context and prompt artifacts | `pages/PromptStudioPage` |
| `ui/pages/9_exports.py` | Artifact registry and exports | `pages/PromptStudioPage` + `pages/ArtifactsPage` |
| `ui/pages/10_operations.py` | Pipeline monitoring and orchestration | `pages/JobsPage` |
| `ui/pages/11_settings.py` | Runtime settings and platform status | `pages/SettingsPage` |
| `ui/pages/12_jobs_dashboard.py` | Job control center | `pages/JobsPage` |
| `ui/pages/13_kpi_intelligence.py` | KPI intelligence and KPI artifacts | `pages/KpiPage` |
| `ui/pages/14_governance.py` | Governance intelligence and PII packages | `pages/GovernancePage` |

## Component Mapping

| Streamlit Component | React Equivalent |
| --- | --- |
| `st.sidebar` | `AppSidebar` |
| `st.metric` | `MetricCard` |
| `st.dataframe` | `DataTable` |
| `st.tabs` | `Tabs` |
| `st.expander` | `Accordion` |
| `st.form` | `FormDialog` or structured form section |
| `st.progress` | `ProgressBar` |
| `st.selectbox` | `Select` |
| `st.multiselect` | `MultiSelect` |
| `st.text_area` | `TextArea` |
| `st.text_input` | `TextInput` |
| `st.number_input` | `NumberInput` |
| `st.radio` | `RadioGroup` |
| `st.button` | `Button` |
| `st.download_button` | `DownloadButton` |
| `st.json` | `JsonViewer` |
| `st.code` | `CodeBlock` |
| `st.spinner` | `LoadingState` |
| `st.success` / `st.error` / `st.warning` / `st.info` | `Alert` variants |

## Discovered Workflow Groups

### Dashboard

- Health status
- Connection summary
- Sync activity
- Export activity
- Platform overview cards

### Connection Management

- Create connection
- Test connection
- Refresh connection
- Sync metadata
- Regenerate semantics
- Regenerate embeddings
- Delete connection

### Database Explorer

- Connection selector
- Schema selector
- Table selector
- Column list
- Relationship list

### Governance

- Governance rescan
- Governance packages
- PII summaries
- Column-level classification detail

### Semantics

- Semantic generation
- Semantic package overview
- Entities
- Processes
- Capabilities
- Glossary

### Relationships

- Relationship graph
- Cluster intelligence
- Hidden relationships
- Process flows
- Dependency paths
- Graph metrics

### KPI

- KPI generation
- KPI catalog
- KPI lineage
- KPI coverage
- KPI readiness

### Embeddings

- Generate embeddings
- Embedding health
- Qdrant collections
- Semantic search

### Prompt Studio

- Prompt inventory
- Prompt templates
- Prompt artifacts
- Download bundle

### Readiness

- Readiness snapshot
- AI assessment
- Remediation recommendations
- Missing stages

### Jobs / Operations

- Pipeline execution history
- Job queue
- Retry / cancel
- Stage timeline
- Failure inspection

### Settings

- Runtime status
- AI configuration
- Vector/retrieval health
- Connected platform context

## API Usage Observed In Streamlit

- Connection endpoints under `/connections`
- Metadata explorer endpoints under `/metadata`
- Governance package endpoints under `/column-semantics`
- Semantic endpoints under `/semantics`
- Relationship endpoints under `/relationships`
- KPI endpoints under `/kpi-intelligence`
- Embeddings endpoints under `/embeddings`
- Prompt Studio endpoints under `/prompt-studio`
- Readiness endpoints under `/readiness`
- Job and pipeline endpoints under `/pipeline`
- Export endpoints under `/export`

## Migration Notes

- The React app should preserve the same workflows and state transitions.
- The first React pass should mirror these screens before any UX redesign.
- Streamlit remains the source of truth until React verification is complete.
