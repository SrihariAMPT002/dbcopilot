"""
API client for the Streamlit frontend.
All HTTP calls to the FastAPI backend go through this module.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
DEFAULT_TIMEOUT = 30
SYNC_TIMEOUT = int(os.getenv("SYNC_REQUEST_TIMEOUT_SECONDS", "180") or 180)
EMBEDDINGS_TIMEOUT = int(os.getenv("EMBEDDINGS_REQUEST_TIMEOUT_SECONDS", "180") or 180)
PROMPT_STUDIO_TIMEOUT = int(os.getenv("PROMPT_STUDIO_REQUEST_TIMEOUT_SECONDS", "180") or 180)


def _get(path: str, timeout: int = DEFAULT_TIMEOUT, **params) -> Tuple[bool, Any]:
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=timeout)
        r.raise_for_status()
        return True, r.json()
    except requests.exceptions.ConnectionError:
        return False, {"error": "Cannot reach the API server. Is the backend running?"}
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return False, {"error": detail}
    except Exception as e:
        return False, {"error": str(e)}


def _post(path: str, payload: Dict, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, Any]:
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout)
        r.raise_for_status()
        return True, r.json()
    except requests.exceptions.ConnectionError:
        return False, {"error": "Cannot reach the API server. Is the backend running?"}
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return False, {"error": detail}
    except Exception as e:
        return False, {"error": str(e)}


def _delete(path: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, Any]:
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=timeout)
        r.raise_for_status()
        return True, r.json()
    except requests.exceptions.ConnectionError:
        return False, {"error": "Cannot reach the API server."}
    except Exception as e:
        return False, {"error": str(e)}


# ── API methods ───────────────────────────────────────────────────────────────

def test_connection(payload: Dict) -> Tuple[bool, Any]:
    return _post("/connections/test", payload)


def connect_database(payload: Dict) -> Tuple[bool, Any]:
    return _post("/connections", payload)


def sync_schema(db_id: int) -> Tuple[bool, Any]:
    return _post(f"/connections/{db_id}/sync", {}, timeout=SYNC_TIMEOUT)


def get_connections() -> Tuple[bool, Any]:
    return _get("/connections")


def get_connection(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/connections/{db_id}")


def delete_connection(db_id: int) -> Tuple[bool, Any]:
    return _delete(f"/connections/{db_id}")


def get_schemas(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/metadata/databases/{db_id}/schemas")


def get_tables(schema_id: int) -> Tuple[bool, Any]:
    return _get(f"/metadata/schemas/{schema_id}/tables")


def get_columns(table_id: int) -> Tuple[bool, Any]:
    return _get(f"/metadata/tables/{table_id}/columns")


def get_relationships(table_id: int) -> Tuple[bool, Any]:
    return _get(f"/metadata/tables/{table_id}/relationships")


def diagnose_connection(db_id: int) -> Tuple[bool, Any]:
    """Get diagnostic info about a connection's schema state."""
    return _get(f"/metadata/diagnose/{db_id}")


# ── Generic API call method ────────────────────────────────────────────────────

def call_api(method: str, path: str, payload: Optional[Dict] = None) -> Tuple[bool, Any]:
    """
    Generic API call method.
    
    Args:
        method: HTTP method (GET, POST, DELETE)
        path: API path (without /api/v1 prefix)
        payload: Optional request body for POST requests
        
    Returns:
        Tuple of (success, result)
    """
    method = method.upper()
    
    if method == "GET":
        return _get(f"/{path}")
    elif method == "POST":
        return _post(f"/{path}", payload or {})
    elif method == "DELETE":
        return _delete(f"/{path}")
    else:
        return False, {"error": f"Unsupported HTTP method: {method}"}


def get_sync_logs(db_id: int, limit: int = 5) -> Tuple[bool, Any]:
    return _get(f"/metadata/databases/{db_id}/sync-logs", limit=limit)


def generate_embeddings(db_id: int) -> Tuple[bool, Any]:
    return _post(f"/embeddings/generate/{db_id}", {}, timeout=EMBEDDINGS_TIMEOUT)


def get_embedding_status(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/embeddings/status/{db_id}")


def generate_semantics(db_id: int) -> Tuple[bool, Any]:
    return _post(f"/semantics/generate/{db_id}", {})


def regenerate_semantics(db_id: int) -> Tuple[bool, Any]:
    return generate_semantics(db_id)


def get_semantic_profile(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/semantics/{db_id}")


def delete_semantic_profile(db_id: int) -> Tuple[bool, Any]:
    return _delete(f"/semantics/{db_id}")


def export_semantic_profile(db_id: int, export_format: str = "json") -> Tuple[bool, Any]:
    return _get(f"/semantics/{db_id}/export", format=export_format)


def get_prompt_context(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/semantic/prompt-context/{db_id}")


def generate_prompt(payload: Dict) -> Tuple[bool, Any]:
    return _post("/semantic/prompt/generate", payload)


def list_prompt_templates() -> Tuple[bool, Any]:
    return _get("/prompt-studio/templates")


def generate_prompt_artifacts(db_id: int) -> Tuple[bool, Any]:
    return _post(f"/prompt-studio/generate/{db_id}", {}, timeout=PROMPT_STUDIO_TIMEOUT)


def generate_kpi_intelligence(db_id: int) -> Tuple[bool, Any]:
    return _post(f"/kpi-intelligence/generate/{db_id}", {}, timeout=SYNC_TIMEOUT)


def get_kpi_intelligence(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/kpi-intelligence/{db_id}")


def preview_prompt_artifact(db_id: int, artifact_type: str) -> Tuple[bool, Any]:
    return _get(f"/prompt-studio/preview/{db_id}/{artifact_type}")


def download_prompt_artifact(db_id: int, artifact_type: str) -> Tuple[bool, Any]:
    return _get(f"/prompt-studio/download/{db_id}/{artifact_type}")


def download_prompt_bundle(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/prompt-studio/download-bundle/{db_id}")


def semantic_search(payload: Dict) -> Tuple[bool, Any]:
    body = dict(payload or {})
    body.setdefault("collection", "all")
    return _post("/embeddings/search", body)


def get_relationship_graph(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/relationships/graph/{db_id}")


def get_table_neighbors(table_id: int, depth: int = 1) -> Tuple[bool, Any]:
    return _get(f"/relationships/tables/{table_id}/neighbors", depth=depth)


def get_join_paths(table_a: int, table_b: int, max_paths: int = 5) -> Tuple[bool, Any]:
    return _get(f"/relationships/join-paths/{table_a}/{table_b}", max_paths=max_paths)


def export_relationship_graph(db_id: int, export_format: str = "json") -> Tuple[bool, Any]:
    return _get(f"/export/graph/{db_id}", format=export_format)


def export_graph(db_id: int, export_format: str = "json") -> Tuple[bool, Any]:
    return export_relationship_graph(db_id, export_format=export_format)


def export_schema(db_id: int, export_format: str = "json") -> Tuple[bool, Any]:
    return _get(f"/export/schema/{db_id}", format=export_format)


def export_prompts(db_id: int, export_format: str = "json") -> Tuple[bool, Any]:
    return _get(f"/export/prompts/{db_id}", format=export_format)


def export_embeddings(db_id: int, export_format: str = "json") -> Tuple[bool, Any]:
    return _get(f"/export/embeddings/{db_id}", format=export_format)


def list_column_semantics(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/column-semantics/databases/{db_id}")


def rescan_column_semantics(db_id: int, force: bool = False) -> Tuple[bool, Any]:
    return _post(f"/column-semantics/databases/{db_id}/rescan?force={str(force).lower()}", {})


def classify_column(column_id: int, force: bool = False) -> Tuple[bool, Any]:
    return _post(f"/column-semantics/columns/{column_id}/classify?force={str(force).lower()}", {})


def get_readiness(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/readiness/{db_id}")


def get_readiness_breakdown(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/readiness/{db_id}/breakdown")


def get_packages_config() -> Tuple[bool, Any]:
    return _get("/config/packages")


def recompute_readiness(db_id: int) -> Tuple[bool, Any]:
    return _post(f"/readiness/recompute/{db_id}", {})


def run_pipeline(db_id: int, triggered_by: str = "ui") -> Tuple[bool, Any]:
    return _post(f"/pipeline/run/{db_id}?triggered_by={triggered_by}", {})


def generate_ai_context(db_id: int, triggered_by: str = "ui") -> Tuple[bool, Any]:
    return _post(f"/pipeline/generate-ai-context/{db_id}?triggered_by={triggered_by}", {})


def get_pipeline_jobs(limit: int = 100, status: Optional[str] = None) -> Tuple[bool, Any]:
    if status:
        return _get("/pipeline/jobs", limit=limit, status=status)
    return _get("/pipeline/jobs", limit=limit)


def get_pipeline_job(job_id: int) -> Tuple[bool, Any]:
    return _get(f"/pipeline/jobs/{job_id}")


def get_pipeline_job_status(job_id: int) -> Tuple[bool, Any]:
    return get_pipeline_job(job_id)


def retry_pipeline_job(job_id: int, triggered_by: str = "ui") -> Tuple[bool, Any]:
    return _post(f"/pipeline/jobs/{job_id}/retry?triggered_by={triggered_by}", {})


def cancel_pipeline_job(job_id: int) -> Tuple[bool, Any]:
    return _post(f"/pipeline/jobs/{job_id}/cancel", {})


def list_artifacts(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/artifacts/{db_id}")


def export_artifacts(db_id: int) -> Tuple[bool, Any]:
    return _post(f"/artifacts/{db_id}/export", {})


def get_artifact_manifest(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/artifacts/{db_id}/manifest")


def get_artifact_content(db_id: int, artifact_type: str, version: Optional[int] = None) -> Tuple[bool, Any]:
    params = {}
    if version is not None:
        params["version"] = version
    return _get(f"/artifacts/{db_id}/content/{artifact_type}", **params)


def mongodb_databases() -> Tuple[bool, Any]:
    return _get("/mongodb/databases")


def mongodb_collections(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/mongodb/collections/{db_id}")


def mongodb_schema(collection_id: int, limit: int = 200, offset: int = 0) -> Tuple[bool, Any]:
    return _get(f"/mongodb/schema/{collection_id}", limit=limit, offset=offset)


def mongodb_samples(collection_id: int, limit: int = 20, offset: int = 0) -> Tuple[bool, Any]:
    return _get(f"/mongodb/sample/{collection_id}", limit=limit, offset=offset)


def mongodb_infer_schema(collection_id: int, sample_size: int = 100) -> Tuple[bool, Any]:
    return _post(f"/mongodb/infer-schema/{collection_id}?sample_size={sample_size}", {})


def mongodb_relationships(collection_id: int) -> Tuple[bool, Any]:
    return _get(f"/mongodb/relationships/{collection_id}")


def health_check() -> Tuple[bool, Any]:
    try:
        api_root = API_BASE.replace("/api/v1", "")
        r = requests.get(f"{api_root}/health", timeout=5)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, {"error": str(e)}
