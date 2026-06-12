import { useEffect, useMemo, useState } from "react";

import Navbar from "../components/Layout/Navbar";
import { chatAPI } from "../services/api";

const C = "#272163";

export default function ConversationLogsPage() {
  const [logs, setLogs] = useState([]);
  const [q, setQ] = useState("");
  const [profile, setProfile] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const stats = useMemo(() => {
    const total = logs.length;
    const active = logs.filter((item) => item.session_status === "active").length;
    const blocked = logs.filter((item) => item.session_status === "blocked").length;
    const tickets = logs.filter((item) => item.ticket_eligible || item.aranda_ticket_id).length;
    return { total, active, blocked, tickets };
  }, [logs]);

  const load = async () => {
    setLoading(true);
    setError("");

    try {
      const params = { limit: 200 };
      if (q.trim()) params.q = q.trim();
      if (profile) params.selected_profile = profile;
      if (status) params.session_status = status;

      const { data } = await chatAPI.adminConversationLogs(params);
      setLogs(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error cargando logs de conversaciones");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="botiq-page botiq-admin-page">
      <Navbar currentPage="conversation-logs" />

      <main className="botiq-page-main">
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ color: C, fontSize: "clamp(22px, 3vw, 28px)", margin: 0 }}>
            Logs de conversaciones
          </h1>
          <p style={{ color: "#6b6b8a", marginTop: 6, fontSize: 13, lineHeight: 1.6 }}>
            Consulta trazabilidad por usuario, perfil, sesión, URL/IP, elegibilidad de ticket y escalamiento a Aranda.
          </p>
        </header>

        <section
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gap: 12,
            marginBottom: 16,
          }}
        >
          <Metric label="Total" value={stats.total} />
          <Metric label="Activas" value={stats.active} color="#059669" />
          <Metric label="Bloqueadas" value={stats.blocked} color="#dc2626" />
          <Metric label="Tickets / elegibles" value={stats.tickets} color="#d97706" />
        </section>

        {error && <div style={alertStyle}>⚠️ {error}</div>}

        <section className="botiq-card" style={{ padding: 16, marginBottom: 16 }}>
          <div className="botiq-log-filters">
            <label style={labelStyle}>
              Buscar
              <input
                value={q}
                onChange={(event) => setQ(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") load();
                }}
                placeholder="usuario, correo, URL o texto consultado"
                className="botiq-form-control"
                style={{ minWidth: 280 }}
              />
            </label>

            <label style={labelStyle}>
              Perfil
              <select value={profile} onChange={(event) => setProfile(event.target.value)} className="botiq-form-control">
                <option value="">Todos</option>
                <option value="employee">Empleado</option>
                <option value="support_engineer">Ingeniero de soporte</option>
              </select>
            </label>

            <label style={labelStyle}>
              Estado
              <select value={status} onChange={(event) => setStatus(event.target.value)} className="botiq-form-control">
                <option value="">Todos</option>
                <option value="active">Activa</option>
                <option value="ended">Finalizada</option>
                <option value="blocked">Bloqueada</option>
              </select>
            </label>

            <button onClick={load} style={primaryBtn}>
              {loading ? "Consultando..." : "Filtrar"}
            </button>
          </div>
        </section>

        <section className="botiq-log-grid">
          {loading ? (
            <div className="botiq-card" style={{ padding: 18, color: "#6b6b8a" }}>
              Cargando logs...
            </div>
          ) : logs.length === 0 ? (
            <div className="botiq-card" style={{ padding: 18, color: "#6b6b8a" }}>
              No hay logs para mostrar.
            </div>
          ) : (
            logs.map((item) => <LogCard key={item.id} item={item} />)
          )}
        </section>
      </main>
    </div>
  );
}

function LogCard({ item }) {
  const profile = item.selected_profile === "support_engineer" ? "Ingeniero de soporte" : "Empleado";
  const statusColor = getStatusColor(item.session_status);

  return (
    <article className="botiq-log-card">
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
          <Badge color={statusColor}>{item.session_status || "active"}</Badge>
          <Badge color={item.selected_profile === "support_engineer" ? "#0284c7" : "#059669"}>{profile}</Badge>
          {item.ticket_eligible && <Badge color="#d97706">ticket elegible</Badge>}
          {item.aranda_ticket_id && <Badge color="#059669">Aranda {item.aranda_ticket_id}</Badge>}
        </div>

        <h3 style={{ color: C, fontSize: 14, marginBottom: 4, overflowWrap: "anywhere" }}>
          {item.user_full_name || "Usuario"} · {item.user_email}
        </h3>

        <p style={{ color: "#6b6b8a", fontSize: 12, lineHeight: 1.55, overflowWrap: "anywhere" }}>
          {item.last_message || "Sin mensaje de usuario registrado."}
        </p>

        {(item.detected_url || item.detected_ip) && (
          <p style={{ color: "#0284c7", fontSize: 12, marginTop: 8, overflowWrap: "anywhere" }}>
            {item.detected_url ? `🔗 ${item.detected_url}` : ""}
            {item.detected_ip ? ` · 🖥️ ${item.detected_ip}` : ""}
          </p>
        )}
      </div>

      <div style={{ display: "grid", gap: 6, color: "#374151", fontSize: 12 }}>
        <Info label="Preguntas" value={item.question_count ?? 0} />
        <Info label="Fuera de alcance" value={item.out_of_scope_count ?? 0} />
        <Info label="Intentos solución" value={item.resolution_attempts ?? 0} />
        <Info label="Usuario red" value={item.support_network_username || "N/A"} />
      </div>

      <div style={{ textAlign: "right", color: "#6b6b8a", fontSize: 11, lineHeight: 1.6 }}>
        <div>{item.created_at ? new Date(item.created_at).toLocaleString() : "N/A"}</div>
        {item.ended_at && <div>Fin: {new Date(item.ended_at).toLocaleString()}</div>}
      </div>
    </article>
  );
}

function Metric({ label, value, color = C }) {
  return (
    <article className="botiq-card" style={{ padding: 16 }}>
      <div style={{ color: "#6b6b8a", fontSize: 12, fontWeight: 700 }}>{label}</div>
      <div style={{ color, fontSize: 26, fontWeight: 900, marginTop: 4 }}>{value}</div>
    </article>
  );
}

function Info({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
      <span style={{ color: "#6b6b8a" }}>{label}</span>
      <strong style={{ color: C, textAlign: "right", overflowWrap: "anywhere" }}>{value}</strong>
    </div>
  );
}

function Badge({ children, color }) {
  return (
    <span
      style={{
        background: `${color}14`,
        color,
        border: `1px solid ${color}30`,
        borderRadius: 999,
        padding: "4px 8px",
        fontSize: 10,
        fontWeight: 850,
        textTransform: "uppercase",
        letterSpacing: ".2px",
      }}
    >
      {children}
    </span>
  );
}

function getStatusColor(status) {
  if (status === "active") return "#059669";
  if (status === "blocked") return "#dc2626";
  if (status === "ended") return "#6b6b8a";
  return "#0284c7";
}

const labelStyle = {
  display: "grid",
  gap: 6,
  fontSize: 12,
  color: "#374151",
  fontWeight: 750,
};

const primaryBtn = {
  border: "none",
  borderRadius: 12,
  background: C,
  color: "#fff",
  padding: "12px 18px",
  cursor: "pointer",
  fontWeight: 850,
  minHeight: 44,
};

const alertStyle = {
  background: "#fef2f2",
  color: "#991b1b",
  border: "1px solid #fecaca",
  borderRadius: 14,
  padding: "12px 14px",
  marginBottom: 16,
  fontSize: 13,
};
