"""
API client for the Streamlit frontend.
All HTTP calls to the FastAPI backend go through this module.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
TIMEOUT = 30


def _get(path: str, **params) -> Tuple[bool, Any]:
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=TIMEOUT)
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


def _post(path: str, payload: Dict) -> Tuple[bool, Any]:
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=TIMEOUT)
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


def _delete(path: str) -> Tuple[bool, Any]:
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=TIMEOUT)
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
    return _post(f"/connections/{db_id}/sync", {})


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
    return _post(f"/embeddings/generate/{db_id}", {})


def get_embedding_status(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/embedding-status/{db_id}")


def regenerate_semantics(db_id: int) -> Tuple[bool, Any]:
    return _post(f"/semantic/enrichment/run/{db_id}", {})


def get_semantic_summary(table_id: int) -> Tuple[bool, Any]:
    return _get(f"/semantic/summary/{table_id}")


def get_prompt_context(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/prompt-context/{db_id}")


def generate_prompt(payload: Dict) -> Tuple[bool, Any]:
    return _post("/prompt/generate", payload)


def semantic_search(payload: Dict) -> Tuple[bool, Any]:
    return _post("/semantic-search", payload)


def get_relationship_graph(db_id: int) -> Tuple[bool, Any]:
    return _get(f"/relationship-graph/{db_id}")


def get_table_neighbors(table_id: int, depth: int = 1) -> Tuple[bool, Any]:
    return _get(f"/table-neighbors/{table_id}", depth=depth)


def get_join_paths(table_a: int, table_b: int, max_paths: int = 5) -> Tuple[bool, Any]:
    return _get(f"/join-paths/{table_a}/{table_b}", max_paths=max_paths)


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


def health_check() -> Tuple[bool, Any]:
    try:
        api_root = API_BASE.replace("/api/v1", "")
        r = requests.get(f"{api_root}/health", timeout=5)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, {"error": str(e)}
