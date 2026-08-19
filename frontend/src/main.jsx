import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

function stripExtension(name) {
  return name ? name.replace(/\.[^./\\]+$/, "") : name;
}

const LINK_LABELS = {
  jira: "Ver en Jira",
  document: "Ver en Drive",
  test: "Ver en Drive",
  endpoint: "Ver spec",
  transcript: "Ver origen",
  decision: "Ver origen",
};

async function request(path, options = {}, token = "") {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Error de servidor");
  return data;
}

function Login({ onLogin }) {
  const [email, setEmail] = useState("admin@pih.local");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const data = await request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem("pih_token", data.access_token);
      localStorage.setItem("pih_user", JSON.stringify(data.user));
      onLogin(data.access_token, data.user);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="login">
      <form className="login-card" onSubmit={submit}>
        <div className="brand-mark">PIH</div>
        <h1>Project Intelligence Hub</h1>
        <p>Memoria organizacional y análisis trazable para proyectos de software.</p>
        <label>Email corporativo</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>Contraseña</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <div className="error">{error}</div>}
        <button type="submit">Ingresar</button>
      </form>
    </main>
  );
}

function Metric({ label, value, note }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value ?? 0}</strong>
      <small>{note}</small>
    </article>
  );
}

function Dashboard({ token, user, logout }) {
  const [dashboard, setDashboard] = useState(null);
  const [pending, setPending] = useState([]);
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("info");

  async function refresh() {
    const [dash, relations] = await Promise.all([
      request("/api/dashboard", {}, token),
      request("/api/relations/pending", {}, token),
    ]);
    setDashboard(dash);
    setPending(relations);
  }

  useEffect(() => {
    refresh().catch((e) => { setMessage(e.message); setMessageType("error"); });
  }, []);

  async function action(name, fn) {
    setBusy(name); setMessage(""); setMessageType("info");
    try {
      const value = await fn();
      const text = typeof value === "string" ? value : value?.text || "Operación completada.";
      setMessage(text);
      setMessageType("success");
      await refresh();

      // El ciclo agéntico se dispara solo en background tras la ingesta:
      // sin este refresco demorado, sus resultados (hallazgos, recomendaciones,
      // evaluación) quedan invisibles hasta que alguien refresque a mano.
      if (typeof value === "object" && value?.cycleTriggered) {
        setMessage(`${text} Ciclo agéntico corriendo en segundo plano…`);
        setTimeout(async () => {
          try {
            await refresh();
            setMessage(`${text} Ciclo agéntico completado — memoria organizacional actualizada.`);
          } catch {
            // El refresco de dashboard ya muestra el error si vuelve a fallar.
          }
        }, 2200);
      }
    } catch (e) {
      setMessage(e.message);
      setMessageType("error");
    } finally {
      setBusy("");
    }
  }

  async function search(e) {
    e.preventDefault();
    if (query.trim().length < 3) {
      setMessage("Escribí al menos 3 caracteres para buscar.");
      setMessageType("error");
      return;
    }
    setBusy("search"); setMessage("");
    try {
      setResult(await request("/api/search", {
        method: "POST",
        body: JSON.stringify({ query }),
      }, token));
    } catch (e) {
      setMessage(e.message);
      setMessageType("error");
    } finally {
      setBusy("");
    }
  }

  async function decide(id, decision) {
    await action("relation", async () => {
      await request(`/api/relations/${id}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, comment: "Validado desde el dashboard" }),
      }, token);
      return `Relación ${decision === "approved" ? "aprobada" : "rechazada"}.`;
    });
  }

  const counts = dashboard?.metrics?.artifacts || {};
  const findings = dashboard?.metrics?.findings || {};

  return (
    <div className="app">
      <aside>
        <div className="logo">PIH</div>
        <nav>
          <a className="active">Dashboard</a>
          <a href="#drive">Google Drive</a>
          <a href="#search">Buscador</a>
          <a href="#relations">Relaciones pendientes</a>
          <a href="#report">Reporte diario</a>
        </nav>
        <div className="user">
          <strong>{user.name}</strong>
          <small>{user.role}</small>
          <button className="secondary" onClick={logout}>Salir</button>
        </div>
      </aside>

      <main className="content">
        <header>
          <div>
            <h1>Dashboard</h1>
            <p>Visión consolidada, evidencia y memoria persistente.</p>
          </div>
          <div className="actions">
            <button
              className="secondary"
              disabled={busy}
              onClick={() => action("jira", async () => {
                const result = await request("/api/ingest/jira", {
                  method: "POST"
                }, token);

                return {
                  text: `${result.ingested} tickets sincronizados desde Jira.`,
                  cycleTriggered: result.cycle_triggered,
                };
              })}
            >
              {busy === "jira" ? "Sincronizando…" : "Sincronizar Jira"}
            </button>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => action("drive", async () => {
                const result = await request("/api/ingest/drive", {
                  method: "POST"
                }, token);

                return {
                  text: `${result.ingested} documentos sincronizados desde Drive.`,
                  cycleTriggered: result.cycle_triggered,
                };
              })}
            >
              {busy === "drive" ? "Sincronizando…" : "Sincronizar Drive"}
            </button>
            <button
              disabled={busy}
              title="El ciclo ya se dispara solo después de cada sincronización. Usá esto para forzar una corrida sin ingerir datos nuevos."
              onClick={() => action("cycle", async () => {
                await request("/api/process/run", { method: "POST" }, token);
                return "Ciclo agéntico ejecutado manualmente.";
              })}
            >
              {busy === "cycle" ? "Procesando…" : "Forzar ciclo manual"}
            </button>
          </div>
        </header>

        {message && <div className={`notice ${messageType}`}>{message}</div>}

        <form id="search" className="search" onSubmit={search}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="¿Qué impacta la historia HU-1234?"
          />
          <button disabled={busy === "search" || query.trim().length < 3}>
            {busy === "search" ? "Buscando…" : "Buscar"}
          </button>
        </form>

        <section className="metrics">
          <Metric label="Historias / bugs" value={counts.jira} note="Fuente Jira" />
          <Metric label="Endpoints" value={counts.endpoint} note="Swagger/OpenAPI" />
          <Metric label="Documentos" value={counts.document} note="Memoria documental" />
          <Metric label="Pruebas" value={counts.test} note="QA" />
          <Metric label="Relaciones pendientes" value={dashboard?.metrics?.pending_relations} note="Requieren validación" />
          <Metric label="Hallazgos altos" value={findings.high} note="Consistencia y riesgo" />
        </section>

        <section className="grid">
          <article className="panel">
            <h2>Resultado del buscador</h2>
            {!result && <p className="muted">Ejecutá una consulta para ver respuesta y evidencia.</p>}
            {result && (
              <>
                <div className={`confidence ${result.confidence}`}>
                  Confianza: {result.confidence}
                </div>
                <pre className="answer">{result.answer}</pre>
                {result.risk && (
                  <div className="risk">
                    <strong>Riesgo heurístico: {result.risk.score}/100 — {result.risk.level}</strong>
                    <small>{result.risk.disclaimer}</small>
                  </div>
                )}
                <h3>Evidencias</h3>
                <ul className="evidence">
                  {result.evidence.map((item) => (
                    <li key={`${item.type}-${item.id}`}>
                      {item.type === "document" ? (
                        <>
                          <b>{item.title}</b>
                          <small>{stripExtension(item.title)}</small>
                        </>
                      ) : (
                        <b>{item.id}</b>
                      )}
                      {item.type !== "document" && ` — ${item.title}`}
                      <small>
                        {item.link ? (
                          <a href={item.link} target="_blank" rel="noreferrer">
                            {LINK_LABELS[item.type] || item.type}
                          </a>
                        ) : item.type}
                        {" · "}{item.source}
                      </small>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </article>

          <article id="report" className="panel">
            <h2>Resumen diario</h2>
            <p><b>Fecha:</b> {dashboard?.daily_report?.date || "-"}</p>
            <div className="report-list">
              <span>Artefactos: {Object.values(counts).reduce((a, b) => a + b, 0)}</span>
              <span>Relaciones pendientes: {dashboard?.daily_report?.pending_relations || 0}</span>
              <span>Recomendaciones: {Object.values(dashboard?.daily_report?.recommendations || {}).reduce((a, b) => a + b, 0)}</span>
              <span>
                Último ciclo: {dashboard?.last_cycle?.status || "sin ejecutar"}
                {dashboard?.last_cycle?.finished_at &&
                  ` — ${new Date(dashboard.last_cycle.finished_at).toLocaleString()}`}
              </span>
            </div>
            <h3>Recomendaciones destacadas</h3>
            <ul className="recommendations">
              {(dashboard?.recommendations || []).map((rec) => (
                <li key={rec.id}>
                  <span className={`pill ${rec.priority}`}>{rec.priority}</span>
                  <b>{rec.title}</b>
                  <small>{rec.description}</small>
                </li>
              ))}
            </ul>
          </article>
        </section>

        <section id="relations" className="panel relations">
          <div className="panel-title">
            <div>
              <h2>Relaciones candidatas</h2>
              <p className="muted">
                Las relaciones semánticas no se incorporan automáticamente: requieren validación humana.
              </p>
            </div>
            <span className="badge">{pending.length}</span>
          </div>
          {pending.length === 0 && <p className="muted">No hay relaciones pendientes.</p>}
          {pending.length > 10 && (
            <p className="muted">
              Mostrando 10 de {pending.length} — aprobá o rechazá para ver las siguientes.
            </p>
          )}
          {pending.slice(0, 10).map((rel) => (
            <div className="relation" key={rel.id}>
              <div>
                <b>{rel.source_id}</b> → <b>{rel.target_id}</b>
                <small>{rel.relation_type} · confianza {Math.round(rel.confidence * 100)}%</small>
                <p>{rel.evidence}</p>
              </div>
              <div className="relation-actions">
                <button onClick={() => decide(rel.id, "approved")}>Aprobar</button>
                <button className="danger" onClick={() => decide(rel.id, "rejected")}>Rechazar</button>
              </div>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("pih_token") || "");
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("pih_user") || "null"); }
    catch { return null; }
  });

  if (!token || !user) {
    return <Login onLogin={(t, u) => { setToken(t); setUser(u); }} />;
  }
  return <Dashboard token={token} user={user} logout={() => {
    localStorage.clear(); setToken(""); setUser(null);
  }} />;
}

createRoot(document.getElementById("root")).render(<App />);
