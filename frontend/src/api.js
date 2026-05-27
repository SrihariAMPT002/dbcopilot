const DEFAULT_API_BASE = 'http://localhost:8000/api/v1';

function apiBase() {
  return (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE).replace(/\/$/, '');
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload?.detail || payload?.message || response.statusText || 'Request failed';
    throw new Error(detail);
  }

  return payload;
}

export async function healthCheck() {
  const root = apiBase().replace(/\/api\/v1$/, '');
  const response = await fetch(`${root}/health`);
  if (!response.ok) {
    throw new Error('API health check failed');
  }
  return response.json();
}

export function getConnections() {
  return request('/connections');
}

export function testConnection(payload) {
  return request('/connections/test', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function connectDatabase(payload) {
  return request('/connections', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function syncSchema(dbId) {
  return request(`/connections/${dbId}/sync`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export function getSchemas(dbId) {
  return request(`/metadata/databases/${dbId}/schemas`);
}

export function getTables(schemaId) {
  return request(`/metadata/schemas/${schemaId}/tables`);
}

export function getColumns(tableId) {
  return request(`/metadata/tables/${tableId}/columns`);
}

export function getRelationships(tableId) {
  return request(`/metadata/tables/${tableId}/relationships`);
}

export function generateEmbeddings(dbId) {
  return request(`/embeddings/generate/${dbId}`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export function getEmbeddingStatus(dbId) {
  return request(`/embedding-status/${dbId}`);
}

export function semanticSearch(payload) {
  return request('/semantic-search', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getRelationshipGraph(dbId) {
  return request(`/relationship-graph/${dbId}`);
}

export function getTableNeighbors(tableId, depth = 1) {
  return request(`/table-neighbors/${tableId}?depth=${depth}`);
}

export function getJoinPaths(tableA, tableB, maxPaths = 5) {
  return request(`/join-paths/${tableA}/${tableB}?max_paths=${maxPaths}`);
}

export function exportRelationshipGraph(dbId, exportFormat = 'json') {
  return request(`/relationship-graph/${dbId}/export?export_format=${exportFormat}`);
}
