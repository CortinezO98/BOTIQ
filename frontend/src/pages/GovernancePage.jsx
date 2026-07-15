import { useEffect, useState } from "react";
import Navbar from "../components/Layout/Navbar";
import { adminAPI } from "../services/api";
import { SkeletonCard } from "../components/Skeleton";

const C = "#272163";

const SEVERITY_INFO = {
  critical: { label: "Crítica", color: "#dc2626", bg: "#fef2f2" },
  high: { label: "Alta", color: "#d97706", bg: "#fffbeb" },
  medium: { label: "Media", color: "#0284c7", bg: "#eff6ff" },
  low: { label: "Baja", color: "var(--botiq-muted)", bg: "var(--botiq-surface)" },
};

const INCIDENT_STATUS_TABS = [
  { value: "open", label: "Abiertas" },
  { value: "acknowledged", label: "Reconocidas" },
  { value: "resolved", label: "Resueltas" },
  { value: "all", label: "Todas" },
];

const AI_STATUS_TABS = [
  { value: "pending", label: "Pendientes" },
  { value: "approved", label: "Aprobadas" },
  { value: "rejected", label: "Rechazadas" },
];

export default function GovernancePage() {
  const [feedback, setFeedback] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [incidentStatus, setIncidentStatus] = useState("open");
  const [aiItems, setAiItems] = useState([]);
  const [aiStatus, setAiStatus] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadAll = async () => {
    setLoading(true);
    setError("");
    try {
      const [feedbackRes, incidentsRes, aiRes] = await Promise.all([
        adminAPI.feedbackSummary(10),
        adminAPI.listIncidentAlerts(incidentStatus, 50),
        adminAPI.listAiKnowledge(aiStatus, "", 100),
      ]);
      setFeedback(feedbackRes.data);
      setIncidents(incidentsRes.data);
      setAiItems(aiRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error cargando el panel de gobierno de IA");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentStatus, aiStatus]);

  const handleAcknowledge = async (id) => {
    setError("");
    try {
      await adminAPI.acknowledgeIncident(id);
      setNotice("Alerta marcada como reconocida.");
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Error reconociendo la alerta");
    }
  };

  const handleResolve = async (id) => {
    const ok = window.confirm("¿Marcar esta alerta como resuelta?");
    if (!ok) return;
    setError("");
    try {
      await adminAPI.resolveIncident(id);
      setNotice("Alerta marcada como resuelta.");
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Error resolviendo la alerta");
    }
  };

  const handleApproveAi = async (id) => {
    setError("");
    try {
      await adminAPI.approveAiKnowledge(id, { create_faq: true });
      setNotice("Respuesta aprobada y convertida en FAQ.");
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Error aprobando la respuesta");
    }
  };

  const handleRejectAi = async (id) => {
    const reason = window.prompt("Motivo del rechazo (opcional):", "");
    if (reason === null) return;
    setError("");
    try {
      await adminAPI.rejectAiKnowledge(id, reason);
      setNotice("Respuesta rechazada.");
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Error rechazando la respuesta");
    }
  };

  const feedbackStats = feedback?.feedback;
  const satisfactionStats = feedback?.satisfaction;
  const openIncidentsCount = incidents.filter((i) => i.status === "open").length;

  return (
    <div className="botiq-page botiq-admin-page">
      <Navbar currentPage="governance" />

      <main className="botiq-page-main">
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ color: C, fontSize: 24, margin: 0 }}>Gobierno de IA</h1>
          <p style={{ color: "var(--botiq-muted)", marginTop: 6, fontSize: 13 }}>
            Incidentes masivos, calidad de respuestas y aprobación de conocimiento generado sin fuente interna.
          </p>
        </header>

        {error && <div style={alertStyle}>⚠️ {error}</div>}
        {notice && <div style={successAlertStyle}>✅ {notice}</div>}

        {/* KPIs */}
        <section className="botiq-kpi-row" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14, marginBottom: 22 }}>
          <Kpi label="👍 Aprobación de respuestas" value={feedbackStats ? `${feedbackStats.approval_rate}%` : "—"} sub={feedbackStats ? `${feedbackStats.total_up} 👍 / ${feedbackStats.total_down} 👎` : ""} />
          <Kpi label="✅ Tasa de resolución" value={satisfactionStats ? `${satisfactionStats.resolution_rate}%` : "—"} sub={satisfactionStats ? `${satisfactionStats.total_surveys} encuestas` : ""} />
          <Kpi label="🚨 Incidentes abiertos" value={loading ? "—" : openIncidentsCount} danger={openIncidentsCount > 0} />
          <Kpi label="🤖 Respuestas IA pendientes" value={loading ? "—" : aiItems.filter((i) => i.status === "pending").length} />
        </section>

        {/* Alertas de incidentes masivos */}
        <section style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
            <h2 style={sectionTitle}>Alertas de incidentes masivos</h2>
            <Tabs tabs={INCIDENT_STATUS_TABS} value={incidentStatus} onChange={setIncidentStatus} />
          </div>

          {loading ? (
            <div style={{ display: "grid", gap: 12 }}>
              <SkeletonCard lines={2} />
              <SkeletonCard lines={2} />
            </div>
          ) : incidents.length === 0 ? (
            <p style={{ color: "var(--botiq-muted)", fontSize: 13 }}>No hay alertas en este estado.</p>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {incidents.map((alert) => {
                const sev = SEVERITY_INFO[alert.severity] || SEVERITY_INFO.medium;
                return (
                  <div key={alert.id} style={{ ...itemCard, borderLeft: `4px solid ${sev.color}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                      <div>
                        <strong style={{ color: C, fontSize: 14 }}>
                          {alert.application_name || alert.app_or_url || "Aplicativo no identificado"}
                        </strong>
                        <span style={{ ...badgeStyle, background: sev.bg, color: sev.color, marginLeft: 10 }}>
                          {sev.label}
                        </span>
                      </div>
                      <span style={{ color: "var(--botiq-muted)", fontSize: 12 }}>
                        {alert.affected_users_count} usuario(s) afectado(s)
                      </span>
                    </div>

                    {alert.app_or_url && (
                      <div style={{ color: "#0284c7", fontSize: 12, marginTop: 6 }}>🔗 {alert.app_or_url}</div>
                    )}

                    {alert.recommendation && (
                      <p style={{ color: "#374151", fontSize: 12, marginTop: 8, marginBottom: 0 }}>
                        💡 {alert.recommendation}
                      </p>
                    )}

                    <div style={{ color: "#9ca3af", fontSize: 11, marginTop: 8 }}>
                      Primera detección: {alert.first_seen_at ? new Date(alert.first_seen_at).toLocaleString() : "—"} · Última: {alert.last_seen_at ? new Date(alert.last_seen_at).toLocaleString() : "—"}
                    </div>

                    {alert.status !== "resolved" && (
                      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                        {alert.status === "open" && (
                          <button style={smallSecondaryBtn} onClick={() => handleAcknowledge(alert.id)}>
                            Reconocer
                          </button>
                        )}
                        <button style={smallPrimaryBtn} onClick={() => handleResolve(alert.id)}>
                          Marcar resuelta
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Respuestas de IA general pendientes de revisión */}
        <section style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 8 }}>
            <div>
              <h2 style={sectionTitle}>Respuestas de IA general</h2>
              <p style={{ color: "var(--botiq-muted)", fontSize: 12, margin: 0, maxWidth: 560 }}>
                Respuestas generadas por Gemini sin fuente interna ni resultado de búsqueda web (último eslabón de
                la cadena de respuesta). Aprobarlas las convierte en FAQ para futuras consultas.
              </p>
            </div>
            <Tabs tabs={AI_STATUS_TABS} value={aiStatus} onChange={setAiStatus} />
          </div>

          {loading ? (
            <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
              <SkeletonCard lines={3} />
              <SkeletonCard lines={3} />
            </div>
          ) : aiItems.length === 0 ? (
            <p style={{ color: "var(--botiq-muted)", fontSize: 13, marginTop: 14 }}>No hay respuestas en este estado.</p>
          ) : (
            <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
              {aiItems.map((item) => (
                <div key={item.id} style={itemCard}>
                  <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                    <strong style={{ color: C, fontSize: 13 }}>{item.question}</strong>
                    {item.confidence != null && <ConfidenceBadge value={item.confidence} />}
                  </div>

                  <p style={{ color: "#374151", fontSize: 13, marginTop: 8, whiteSpace: "pre-wrap" }}>{item.answer}</p>

                  <div style={{ color: "#9ca3af", fontSize: 11, marginTop: 8 }}>
                    Usado {item.usage_count} vez(ces) · {item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
                  </div>

                  {item.status === "pending" && (
                    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                      <button style={smallPrimaryBtn} onClick={() => handleApproveAi(item.id)}>
                        ✅ Aprobar y crear FAQ
                      </button>
                      <button style={smallDangerBtn} onClick={() => handleRejectAi(item.id)}>
                        ✖ Rechazar
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Mensajes peor calificados */}
        {feedback?.worst_rated_messages?.length > 0 && (
          <section style={cardStyle}>
            <h2 style={sectionTitle}>Mensajes peor calificados</h2>
            <p style={{ color: "var(--botiq-muted)", fontSize: 12, marginTop: 0, marginBottom: 14 }}>
              Respuestas del bot con más 👎 — candidatas a revisar en la base de conocimiento.
            </p>
            <div style={{ display: "grid", gap: 8 }}>
              {feedback.worst_rated_messages.map((m) => (
                <div key={m.message_id} style={{ ...itemCard, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <code style={{ fontSize: 11, color: "var(--botiq-muted)" }}>{m.message_id}</code>
                  <span style={{ ...badgeStyle, background: "#fef2f2", color: "#991b1b" }}>{m.total_down} 👎</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function Kpi({ label, value, sub, danger = false }) {
  return (
    <div style={{ ...cardStyle, marginBottom: 0, padding: 16, textAlign: "center" }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: danger ? "#dc2626" : C }}>{value}</div>
      <div style={{ fontSize: 11, color: "var(--botiq-muted)", marginTop: 4 }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color: "#9ca3af", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function ConfidenceBadge({ value }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "#059669" : pct >= 45 ? "#d97706" : "#dc2626";
  return (
    <span style={{ ...badgeStyle, background: `${color}18`, color, whiteSpace: "nowrap" }}>
      Confianza: {pct}%
    </span>
  );
}

function Tabs({ tabs, value, onChange }) {
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          style={{
            border: "1px solid var(--botiq-border)",
            borderRadius: 8,
            padding: "6px 12px",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            background: value === tab.value ? C : "var(--botiq-surface)",
            color: value === tab.value ? "#fff" : C,
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

const cardStyle = {
  background: "var(--botiq-card-bg)",
  border: "1px solid var(--botiq-border)",
  borderRadius: 14,
  padding: 22,
  marginBottom: 22,
  boxShadow: "0 1px 4px rgba(39,33,99,0.06)",
};

const itemCard = {
  background: "#fdfdff",
  border: "1px solid var(--botiq-border)",
  borderRadius: 12,
  padding: 14,
};

const sectionTitle = { color: C, fontSize: 16, margin: "0 0 4px" };

const badgeStyle = {
  display: "inline-block",
  borderRadius: 999,
  padding: "3px 10px",
  fontSize: 11,
  fontWeight: 700,
};

const primaryBtnBase = {
  color: "#fff",
  border: "none",
  borderRadius: 8,
  cursor: "pointer",
  fontWeight: 600,
};

const smallPrimaryBtn = { ...primaryBtnBase, background: C, padding: "7px 12px", fontSize: 12 };
const smallSecondaryBtn = { background: "var(--botiq-surface)", color: C, border: "1px solid var(--botiq-border)", borderRadius: 8, padding: "7px 12px", cursor: "pointer", fontWeight: 600, fontSize: 12 };
const smallDangerBtn = { background: "#fef2f2", color: "#991b1b", border: "1px solid #fecaca", borderRadius: 8, padding: "7px 12px", cursor: "pointer", fontWeight: 600, fontSize: 12 };

const alertStyle = {
  background: "#fef2f2",
  color: "#991b1b",
  border: "1px solid #fecaca",
  borderRadius: 10,
  padding: "12px 14px",
  marginBottom: 18,
  fontSize: 13,
};

const successAlertStyle = {
  background: "#f0fdf4",
  color: "#166534",
  border: "1px solid #bbf7d0",
  borderRadius: 10,
  padding: "12px 14px",
  marginBottom: 18,
  fontSize: 13,
};
