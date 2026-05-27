import React, { useEffect, useMemo, useState } from 'react';
import {
  connectDatabase,
  getColumns,
  getConnections,
  getRelationships,
  getSchemas,
  getTables,
  healthCheck,
  syncSchema,
  testConnection,
} from './api';

const DEFAULTS = {
  postgresql: 5432,
  mysql: 3306,
  sqlserver: 1433,
  mongodb: 27017,
};

const DB_LABELS = {
  postgresql: 'PostgreSQL',
  mysql: 'MySQL',
  sqlserver: 'SQL Server',
  mongodb: 'MongoDB',
};

const NAV = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'connect', label: 'Connect' },
  { id: 'explorer', label: 'Explorer' },
  { id: 'settings', label: 'Settings' },
];

function formatCount(value) {
  return new Intl.NumberFormat('en-US').format(value || 0);
}

function pickFirst(items) {
  return Array.isArray(items) && items.length ? items[0] : null;
}

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [health, setHealth] = useState({ loading: true, data: null, error: null });
  const [connections, setConnections] = useState([]);
  const [loadingConnections, setLoadingConnections] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState('');
  const [schemas, setSchemas] = useState([]);
  const [selectedSchemaId, setSelectedSchemaId] = useState('');
  const [tables, setTables] = useState([]);
  const [selectedTableId, setSelectedTableId] = useState('');
  const [columns, setColumns] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [statusMessage, setStatusMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    name: '',
    db_type: 'postgresql',
    host: '',
    port: DEFAULTS.postgresql,
    database_name: '',
    username: '',
    password: '',
  });

  const selectedConnection = useMemo(
    () => connections.find((conn) => String(conn.id) === String(selectedConnectionId)) || null,
    [connections, selectedConnectionId],
  );

  async function refreshConnections(opts = {}) {
    const { keepSelection = false } = opts;
    setLoadingConnections(true);
    try {
      const data = await getConnections();
      setConnections(data);
      if (!keepSelection) {
        const first = pickFirst(data);
        setSelectedConnectionId(first ? String(first.id) : '');
      }
    } catch (error) {
      setStatusMessage({ type: 'error', text: error.message });
    } finally {
      setLoadingConnections(false);
    }
  }

  useEffect(() => {
    let ignore = false;
    async function loadHealth() {
      try {
        const data = await healthCheck();
        if (!ignore) setHealth({ loading: false, data, error: null });
      } catch (error) {
        if (!ignore) setHealth({ loading: false, data: null, error: error.message });
      }
    }

    loadHealth();
    refreshConnections();

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    async function loadSchemas() {
      if (!selectedConnectionId) {
        setSchemas([]);
        setSelectedSchemaId('');
        setTables([]);
        setSelectedTableId('');
        setColumns([]);
        setRelationships([]);
        return;
      }

      try {
        const data = await getSchemas(selectedConnectionId);
        if (ignore) return;
        setSchemas(data);
        const firstSchema = pickFirst(data);
        setSelectedSchemaId(firstSchema ? String(firstSchema.id) : '');
        setTables([]);
        setSelectedTableId('');
        setColumns([]);
        setRelationships([]);
      } catch (error) {
        if (!ignore) setStatusMessage({ type: 'error', text: error.message });
      }
    }

    loadSchemas();

    return () => {
      ignore = true;
    };
  }, [selectedConnectionId]);

  useEffect(() => {
    let ignore = false;

    async function loadTables() {
      if (!selectedSchemaId) {
        setTables([]);
        setSelectedTableId('');
        setColumns([]);
        setRelationships([]);
        return;
      }

      try {
        const data = await getTables(selectedSchemaId);
        if (ignore) return;
        setTables(data);
        const firstTable = pickFirst(data);
        setSelectedTableId(firstTable ? String(firstTable.id) : '');
        setColumns([]);
        setRelationships([]);
      } catch (error) {
        if (!ignore) setStatusMessage({ type: 'error', text: error.message });
      }
    }

    loadTables();

    return () => {
      ignore = true;
    };
  }, [selectedSchemaId]);

  useEffect(() => {
    let ignore = false;

    async function loadTableMeta() {
      if (!selectedTableId) {
        setColumns([]);
        setRelationships([]);
        return;
      }

      try {
        const [columnData, relationshipData] = await Promise.all([
          getColumns(selectedTableId),
          getRelationships(selectedTableId),
        ]);
        if (ignore) return;
        setColumns(columnData);
        setRelationships(relationshipData);
      } catch (error) {
        if (!ignore) setStatusMessage({ type: 'error', text: error.message });
      }
    }

    loadTableMeta();

    return () => {
      ignore = true;
    };
  }, [selectedTableId]);

  const totals = {
    connections: connections.length,
    active: connections.filter((item) => item.status === 'active').length,
    schemas: connections.reduce((sum, item) => sum + (item.schema_count || 0), 0),
    tables: connections.reduce((sum, item) => sum + (item.table_count || 0), 0),
  };

  function updateForm(field, value) {
    setForm((current) => {
      const next = { ...current, [field]: value };
      if (field === 'db_type') {
        next.port = DEFAULTS[value] || current.port;
      }
      return next;
    });
  }

  async function handleTestConnection(event) {
    event.preventDefault();
    setBusy(true);
    setStatusMessage(null);
    try {
      const result = await testConnection(form);
      setStatusMessage({
        type: result.success ? 'success' : 'error',
        text: result.message || 'Connection test finished',
      });
    } catch (error) {
      setStatusMessage({ type: 'error', text: error.message });
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateConnection(syncAfter = false) {
    setBusy(true);
    setStatusMessage(null);
    try {
      const connection = await connectDatabase(form);
      setStatusMessage({ type: 'success', text: `Saved connection ${connection.name}` });
      await refreshConnections({ keepSelection: true });

      if (syncAfter) {
        const payload = await syncSchema(connection.id);
        setStatusMessage({
          type: payload.success ? 'success' : 'error',
          text: payload.message || 'Sync finished',
        });
        await refreshConnections({ keepSelection: true });
      }
      setSelectedConnectionId(String(connection.id));
      setActiveTab('explorer');
    } catch (error) {
      setStatusMessage({ type: 'error', text: error.message });
    } finally {
      setBusy(false);
    }
  }

  function renderStatusPill(value) {
    const label = String(value || 'unknown');
    const cls = label === 'active' ? 'pill-success' : label === 'error' ? 'pill-error' : 'pill-muted';
    return <span className={`pill ${cls}`}>{label}</span>;
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div>
          <div className="brand">DB Copilot</div>
          <div className="brand-sub">React UI · API driven</div>
        </div>

        <nav className="nav">
          {NAV.map((item) => (
            <button
              key={item.id}
              className={activeTab === item.id ? 'nav-item active' : 'nav-item'}
              onClick={() => setActiveTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-card">
          <div className="sidebar-label">API</div>
          <div className="sidebar-value">{import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'}</div>
        </div>

        <div className="sidebar-card">
          <div className="sidebar-label">Health</div>
          {health.loading ? (
            <div className="muted">Checking backend...</div>
          ) : health.error ? (
            <div className="error-text">{health.error}</div>
          ) : (
            <div>
              <div className="strong">{health.data?.status || 'unknown'}</div>
              <div className="muted">{health.data?.environment || 'n/a'}</div>
            </div>
          )}
        </div>
      </aside>

      <main className="content">
        <header className="hero">
          <div>
            <div className="eyebrow">Database metadata control center</div>
            <h1>Connect, sync, and explore databases from one React dashboard.</h1>
            <p>
              This frontend talks to the existing FastAPI backend, so the Docker setup stays familiar while the UI moves to React.
            </p>
          </div>
          <div className="hero-grid">
            <div className="stat-card">
              <div className="stat-label">Connections</div>
              <div className="stat-value">{formatCount(totals.connections)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Active</div>
              <div className="stat-value">{formatCount(totals.active)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Schemas</div>
              <div className="stat-value">{formatCount(totals.schemas)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Tables</div>
              <div className="stat-value">{formatCount(totals.tables)}</div>
            </div>
          </div>
        </header>

        {statusMessage && (
          <div className={`banner ${statusMessage.type === 'success' ? 'banner-success' : 'banner-error'}`}>
            {statusMessage.text}
          </div>
        )}

        {activeTab === 'dashboard' && (
          <section className="panel-grid">
            <article className="panel">
              <div className="panel-title">Connected Sources</div>
              <div className="table">
                <div className="table-head">
                  <span>Name</span>
                  <span>Type</span>
                  <span>Status</span>
                </div>
                {loadingConnections ? (
                  <div className="empty">Loading connections...</div>
                ) : connections.length ? (
                  connections.map((conn) => (
                    <button
                      key={conn.id}
                      className={String(selectedConnectionId) === String(conn.id) ? 'row row-active' : 'row'}
                      onClick={() => {
                        setSelectedConnectionId(String(conn.id));
                        setActiveTab('explorer');
                      }}
                    >
                      <span>{conn.name}</span>
                      <span>{DB_LABELS[conn.db_type] || conn.db_type}</span>
                      <span>{renderStatusPill(conn.status)}</span>
                    </button>
                  ))
                ) : (
                  <div className="empty">No connections yet.</div>
                )}
              </div>
            </article>

            <article className="panel">
              <div className="panel-title">What you can do</div>
              <div className="feature-list">
                <div className="feature">
                  <h3>Connect databases</h3>
                  <p>Register PostgreSQL, MySQL, SQL Server, or MongoDB sources from the same backend API.</p>
                </div>
                <div className="feature">
                  <h3>Sync metadata</h3>
                  <p>Pull schemas, tables, columns, and relationships into the metadata store.</p>
                </div>
                <div className="feature">
                  <h3>Explore details</h3>
                  <p>Navigate from connection to schema to table and inspect column metadata in the browser.</p>
                </div>
              </div>
            </article>
          </section>
        )}

        {activeTab === 'connect' && (
          <section className="panel form-panel">
            <div className="panel-title">Connect a database</div>
            <form className="form-grid">
              <label>
                <span>Connection name</span>
                <input
                  value={form.name}
                  onChange={(event) => updateForm('name', event.target.value)}
                  placeholder="production-warehouse"
                />
              </label>
              <label>
                <span>Database type</span>
                <select value={form.db_type} onChange={(event) => updateForm('db_type', event.target.value)}>
                  <option value="postgresql">PostgreSQL</option>
                  <option value="mysql">MySQL</option>
                  <option value="sqlserver">SQL Server</option>
                  <option value="mongodb">MongoDB</option>
                </select>
              </label>
              <label className="full">
                <span>Host</span>
                <input value={form.host} onChange={(event) => updateForm('host', event.target.value)} placeholder="localhost or 127.0.0.1" />
              </label>
              <label>
                <span>Port</span>
                <input
                  type="number"
                  min="1"
                  max="65535"
                  value={form.port}
                  onChange={(event) => updateForm('port', Number(event.target.value))}
                />
              </label>
              <label>
                <span>Database name</span>
                <input
                  value={form.database_name}
                  onChange={(event) => updateForm('database_name', event.target.value)}
                  placeholder="analytics"
                />
              </label>
              <label>
                <span>Username</span>
                <input value={form.username} onChange={(event) => updateForm('username', event.target.value)} placeholder="db_user" />
              </label>
              <label>
                <span>Password</span>
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) => updateForm('password', event.target.value)}
                  placeholder="••••••••"
                />
              </label>

              {form.db_type === 'mongodb' && (
                <div className="full mongo-note">
                  MongoDB uses the host and port for the server itself. If this times out, the issue is usually network reachability or credentials, not the database name.
                </div>
              )}

              <div className="actions full">
                <button type="button" className="secondary" disabled={busy} onClick={handleTestConnection}>
                  Test connection
                </button>
                <button type="button" className="secondary" disabled={busy} onClick={() => handleCreateConnection(false)}>
                  Save connection
                </button>
                <button type="button" className="primary" disabled={busy} onClick={() => handleCreateConnection(true)}>
                  Save and sync
                </button>
              </div>
            </form>
          </section>
        )}

        {activeTab === 'explorer' && (
          <section className="explorer">
            <article className="panel explorer-sidebar">
              <div className="panel-title">Browse metadata</div>
              <label>
                <span>Connection</span>
                <select value={selectedConnectionId} onChange={(event) => setSelectedConnectionId(event.target.value)}>
                  <option value="">Select a connection</option>
                  {connections.map((conn) => (
                    <option key={conn.id} value={conn.id}>
                      {conn.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Schema</span>
                <select value={selectedSchemaId} onChange={(event) => setSelectedSchemaId(event.target.value)} disabled={!schemas.length}>
                  <option value="">Select a schema</option>
                  {schemas.map((schema) => (
                    <option key={schema.id} value={schema.id}>
                      {schema.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Table</span>
                <select value={selectedTableId} onChange={(event) => setSelectedTableId(event.target.value)} disabled={!tables.length}>
                  <option value="">Select a table</option>
                  {tables.map((table) => (
                    <option key={table.id} value={table.id}>
                      {table.name}
                    </option>
                  ))}
                </select>
              </label>

              <div className="mini-summary">
                <div>
                  <div className="sidebar-label">Selected source</div>
                  <div className="strong">{selectedConnection ? selectedConnection.name : 'None'}</div>
                </div>
                <div>
                  <div className="sidebar-label">Type</div>
                  <div className="strong">{selectedConnection ? DB_LABELS[selectedConnection.db_type] || selectedConnection.db_type : '—'}</div>
                </div>
              </div>
            </article>

            <div className="explorer-main">
              <article className="panel">
                <div className="panel-title">Tables</div>
                <div className="table">
                  <div className="table-head">
                    <span>Name</span>
                    <span>Type</span>
                    <span>Rows</span>
                  </div>
                  {tables.length ? (
                    tables.map((table) => (
                      <button
                        key={table.id}
                        className={String(selectedTableId) === String(table.id) ? 'row row-active' : 'row'}
                        onClick={() => setSelectedTableId(String(table.id))}
                      >
                        <span>{table.name}</span>
                        <span>{table.table_type}</span>
                        <span>{table.row_count ?? '—'}</span>
                      </button>
                    ))
                  ) : (
                    <div className="empty">Choose a schema to see its tables.</div>
                  )}
                </div>
              </article>

              <article className="panel">
                <div className="panel-title">Columns</div>
                <div className="table">
                  <div className="table-head">
                    <span>Name</span>
                    <span>Type</span>
                    <span>Length</span>
                  </div>
                  {columns.length ? (
                    columns.map((column) => (
                      <div key={column.id} className="row static">
                        <span>
                          {column.name}
                          {column.is_primary_key ? <em className="chip">PK</em> : null}
                        </span>
                        <span>{column.data_type}</span>
                        <span>{column.max_length ?? '—'}</span>
                      </div>
                    ))
                  ) : (
                    <div className="empty">Choose a table to inspect columns.</div>
                  )}
                </div>
              </article>

              <article className="panel">
                <div className="panel-title">Relationships</div>
                <div className="table">
                  <div className="table-head">
                    <span>Column</span>
                    <span>References</span>
                    <span>Constraint</span>
                  </div>
                  {relationships.length ? (
                    relationships.map((relationship) => (
                      <div key={relationship.id} className="row static">
                        <span>{relationship.column_name}</span>
                        <span>
                          {relationship.referenced_schema ? `${relationship.referenced_schema}.` : ''}
                          {relationship.referenced_table_name}.{relationship.referenced_column_name}
                        </span>
                        <span>{relationship.constraint_name || '—'}</span>
                      </div>
                    ))
                  ) : (
                    <div className="empty">No relationships found for the selected table.</div>
                  )}
                </div>
              </article>
            </div>
          </section>
        )}

        {activeTab === 'settings' && (
          <section className="panel">
            <div className="panel-title">Runtime settings</div>
            <div className="settings-grid">
              <div className="setting">
                <div className="sidebar-label">API base URL</div>
                <div className="strong">{import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'}</div>
              </div>
              <div className="setting">
                <div className="sidebar-label">Frontend port</div>
                <div className="strong">5173</div>
              </div>
              <div className="setting">
                <div className="sidebar-label">Backend CORS</div>
                <div className="strong">localhost:5173, localhost:3000</div>
              </div>
              <div className="setting">
                <div className="sidebar-label">MongoDB note</div>
                <div className="strong">Timeouts usually mean host, port, firewall, or Atlas allowlist issues.</div>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
