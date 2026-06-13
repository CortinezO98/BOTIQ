import { useEffect, useMemo, useState } from "react";

import Navbar from "../components/Layout/Navbar";
import BotiqAvatar from "../components/Brand/BotiqAvatar";
import { chatAPI, downloadBlob } from "../services/api";

const C = "#272163";

const STATUS_LABELS = {
  active: { label: "Activa", color: "#059669" },
  ended: { label: "Finalizada", color: "#6b6b8a" },
  blocked: { label: "Bloqueada", color: "#dc2626" },
};

const PROFILE_LABELS = {
  employee: { label: "Empleado", color: "#059669", icon: "👤" },
  support_engineer: { label: "Ing. Soporte", color: "#0284c7", icon: "🛠️" },
};

export default function ConversationLogsPage() {
  const [logs, setLogs] = useState([]);
  const [q, setQ] = useState("");
  const [profile, setProfile] = useState("");
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null); // log abierto en el modal

  const stats = useMemo(() => {
    const total = logs.length;
    const active = logs.filter((i) => i.session_status === "active").length;
    const ended = logs.filter((i) => i.session_status === "ended").length;
    const blocked = logs.filter((i) => i.session_status === "blocked").length;
    const escalated = logs.filter((i) => i.escalated_to_aranda || i.aranda_ticket_id).length;
    return { total, active, ended, blocked, escalated };
  }, [logs]);

  const buildParams = (limit = 200) => {
    const params = { limit };
    if (q.trim()) params.q = q.trim();
    if (profile) params.selected_profile = profile;
    if (status) params.session_status = status;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    return params;
  };

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await chatAPI.adminConversationLogs(buildParams(200));
      setLogs(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error cargando logs de conversaciones");
    } finally {
      setLoading(false);
    }
  };

  const exportCsv = async () => {
    setExporting(true);
    setError("");
    try {
      const { data } = await chatAPI.adminConversationLogsExport(buildParams(500));
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      downloadBlob(data, `botiq_logs_${stamp}.csv`);
    } catch (err) {
      setError(err.response?.data?.detail || "Error exportando CSV");
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="botiq-page botiq-admin-page">
      <Navbar currentPage="conversation-logs" />

      <main className="botiq-page-main">
        <header
          className="animate__animated animate__fadeIn"
          style={{ marginBottom: 22, display: "flex", flexWrap: "wrap", gap: 14, alignItems: "flex-end", justifyContent: "space-between" }}
        >
          <div style={{ minWidth: 0 }}>
            <h1 style={{ color: C, fontSize: "clamp(22px, 3vw, 28px)", margin: 0, letterSpacing: "-0.5px" }}>
              🧾 Logs de conversaciones
            </h1>
            <p style={{ color: "#6b6b8a", marginTop: 6, fontSize: 13, lineHeight: 1.6, maxWidth: 640 }}>
              Trazabilidad completa por usuario, perfil, sesión, URL/IP, elegibilidad de ticket y escalamiento a Aranda.
              Haz clic en una conversación para ver el detalle completo.
            </p>
          </div>

          <button onClick={exportCsv} disabled={exporting || loading} style={exportBtn}>
            {exporting ? "Exportando..." : "⬇️ Exportar CSV"}
          </button>
        </header>

        <section className="botiq-kpi-row animate__animated animate__fadeInUp">
          <Metric label="Total" value={stats.total} icon="💬" />
          <Metric label="Activas" value={stats.active} color="#059669" icon="🟢" />
          <Metric label="Finalizadas" value={stats.ended} color="#6b6b8a" icon="🏁" />
          <Metric label="Bloqueadas" value={stats.blocked} color="#dc2626" icon="🚫" />
          <Metric label="Escaladas a Aranda" value={stats.escalated} color="#d97706" icon="🎫" />
        </section>

        {error && <div style={alertStyle}>⚠️ {error}</div>}

        <section className="botiq-card" style={{ padding: 16, marginBottom: 16 }}>
          <div className="botiq-log-filters-grid">
            <label style={labelStyle}>
              Buscar
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && load()}
                placeholder="usuario, correo, URL, IP, ticket o texto consultado"
                className="botiq-form-control"
              />
            </label>

            <label style={labelStyle}>
              Perfil
              <select value={profile} onChange={(e) => setProfile(e.target.value)} className="botiq-form-control">
                <option value="">Todos</option>
                <option value="employee">Empleado</option>
                <option value="support_engineer">Ingeniero de soporte</option>
              </select>
            </label>

            <label style={labelStyle}>
              Estado
              <select value={status} onChange={(e) => setStatus(e.target.value)} className="botiq-form-control">
                <option value="">Todos</option>
                <option value="active">Activa</option>
                <option value="ended">Finalizada</option>
                <option value="blocked">Bloqueada</option>
              </select>
            </label>

            <label style={labelStyle}>
              Desde
              <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="botiq-form-control" />
            </label>

            <label style={labelStyle}>
              Hasta
              <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="botiq-form-control" />
            </label>

            <button onClick={load} style={primaryBtn}>
              {loading ? "Consultando..." : "🔍 Filtrar"}
            </button>
          </div>
        </section>

        {loading ? (
          <div className="botiq-card" style={{ padding: 18, color: "#6b6b8a" }}>Cargando logs...</div>
        ) : logs.length === 0 ? (
          <div className="botiq-card" style={{ padding: 28, color: "#6b6b8a", textAlign: "center" }}>
            <div style={{ fontSize: 34, marginBottom: 8 }}>🗂️</div>
            No hay conversaciones que coincidan con los filtros.
          </div>
        ) : (
          <>
            {/* Escritorio: tabla */}
            <section className="botiq-card botiq-desktop-only" style={{ padding: 0 }}>
              <div className="botiq-table-wrap">
                <table className="botiq-logs-table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Usuario</th>
                      <th>Perfil</th>
                      <th>Estado</th>
                      <th style={{ textAlign: "center" }}>Preguntas</th>
                      <th>Última consulta</th>
                      <th>URL / IP</th>
                      <th>Ticket</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((item) => (
                      <LogRow key={item.id} item={item} onOpen={() => setSelected(item)} />
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Móvil: tarjetas */}
            <section className="botiq-log-grid botiq-mobile-only">
              {logs.map((item) => (
                <LogCard key={item.id} item={item} onOpen={() => setSelected(item)} />
              ))}
            </section>
          </>
        )}
      </main>

      {selected && <ConversationModal item={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

/* ---------- Fila de tabla (escritorio) ---------- */

function LogRow({ item, onOpen }) {
  const st = STATUS_LABELS[item.session_status] || STATUS_LABELS.active;
  const pf = PROFILE_LABELS[item.selected_profile] || PROFILE_LABELS.employee;

  return (
    <tr onClick={onOpen} className="botiq-logs-row" title="Ver conversación completa">
      <td style={{ whiteSpace: "nowrap", color: "#6b6b8a", fontSize: 12 }}>
        {item.created_at ? new Date(item.created_at).toLocaleString() : "N/A"}
      </td>
      <td>
        <div style={{ fontWeight: 750, color: C, fontSize: 13 }}>{item.user_full_name || "Usuario"}</div>
        <div style={{ color: "#6b6b8a", fontSize: 11 }}>{item.user_email}</div>
      </td>
      <td><Badge color={pf.color}>{pf.icon} {pf.label}</Badge></td>
      <td><Badge color={st.color}>{st.label}</Badge></td>
      <td style={{ textAlign: "center", fontWeight: 800, color: C }}>{item.question_count ?? 0}</td>
      <td style={{ maxWidth: 260 }}>
        <span style={{ color: "#374151", fontSize: 12, display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {item.last_message || "—"}
        </span>
      </td>
      <td style={{ maxWidth: 180 }}>
        <span style={{ color: "#0284c7", fontSize: 11, display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {item.detected_url || item.detected_ip || "—"}
        </span>
      </td>
      <td style={{ whiteSpace: "nowrap" }}>
        {item.aranda_ticket_id ? (
          <Badge color="#059669">🎫 {item.aranda_ticket_id}</Badge>
        ) : item.ticket_eligible ? (
          <Badge color="#d97706">elegible</Badge>
        ) : (
          <span style={{ color: "#9ca3af", fontSize: 11 }}>—</span>
        )}
      </td>
      <td>
        <button onClick={(e) => { e.stopPropagation(); onOpen(); }} style={viewBtn}>Ver</button>
      </td>
    </tr>
  );
}

/* ---------- Tarjeta (móvil) ---------- */

function LogCard({ item, onOpen }) {
  const st = STATUS_LABELS[item.session_status] || STATUS_LABELS.active;
  const pf = PROFILE_LABELS[item.selected_profile] || PROFILE_LABELS.employee;

  return (
    <article className="botiq-log-card" onClick={onOpen} style={{ cursor: "pointer" }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
        <Badge color={st.color}>{st.label}</Badge>
        <Badge color={pf.color}>{pf.icon} {pf.label}</Badge>
        {item.ticket_eligible && !item.aranda_ticket_id && <Badge color="#d97706">ticket elegible</Badge>}
        {item.aranda_ticket_id && <Badge color="#059669">🎫 {item.aranda_ticket_id}</Badge>}
      </div>

      <h3 style={{ color: C, fontSize: 14, marginBottom: 4, overflowWrap: "anywhere" }}>
        {item.user_full_name || "Usuario"}
      </h3>
      <p style={{ color: "#6b6b8a", fontSize: 11, marginBottom: 8 }}>{item.user_email}</p>

      <p style={{ color: "#374151", fontSize: 12, lineHeight: 1.55, overflowWrap: "anywhere" }}>
        {item.last_message || "Sin mensaje de usuario registrado."}
      </p>

      {(item.detected_url || item.detected_ip) && (
        <p style={{ color: "#0284c7", fontSize: 11, marginTop: 8, overflowWrap: "anywhere" }}>
          {item.detected_url ? `🔗 ${item.detected_url}` : ""}
          {item.detected_ip ? ` · 🖥️ ${item.detected_ip}` : ""}
        </p>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10, color: "#6b6b8a", fontSize: 11 }}>
        <span>💬 {item.question_count ?? 0} preguntas</span>
        <span>{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</span>
      </div>

      <button style={{ ...viewBtn, width: "100%", marginTop: 10 }}>Ver conversación completa</button>
    </article>
  );
}

/* ---------- Modal: resumen + conversación completa ---------- */

function ConversationModal({ item, onClose }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let alive = true;
    chatAPI
      .adminConversationMessages(item.id)
      .then(({ data }) => alive && setMessages(data))
      .catch((err) => alive && setError(err.response?.data?.detail || "Error cargando la conversación"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [item.id]);

  const summary = useMemo(() => buildSummary(item, messages), [item, messages]);
  const st = STATUS_LABELS[item.session_status] || STATUS_LABELS.active;
  const pf = PROFILE_LABELS[item.selected_profile] || PROFILE_LABELS.employee;

  return (
    <div className="botiq-modal-backdrop" onClick={onClose}>
      <div className="botiq-modal animate__animated animate__fadeInUp animate__faster" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ background: `linear-gradient(135deg, ${C}, #3a3490)`, padding: "16px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
            <BotiqAvatar size={38} color={C} />
            <div style={{ minWidth: 0 }}>
              <div style={{ color: "#fff", fontWeight: 800, fontSize: 15, overflowWrap: "anywhere" }}>
                {item.user_full_name || "Usuario"}
              </div>
              <div style={{ color: "rgba(255,255,255,0.7)", fontSize: 12, overflowWrap: "anywhere" }}>{item.user_email}</div>
            </div>
          </div>
          <button onClick={onClose} style={modalCloseBtn} title="Cerrar">✕</button>
        </div>

        <div className="botiq-modal-body">
          {/* Resumen */}
          <section style={{ background: "#f5f5fa", border: "1px solid #e2e1f0", borderRadius: 14, padding: 14, marginBottom: 16 }}>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
              <Badge color={st.color}>{st.label}</Badge>
              <Badge color={pf.color}>{pf.icon} {pf.label}</Badge>
              {item.support_network_username && (
                <Badge color={item.support_network_validated ? "#059669" : "#dc2626"}>
                  red: {item.support_network_username} {item.support_network_validated ? "✓" : "✗"}
                </Badge>
              )}
              {item.ticket_eligible && <Badge color="#d97706">ticket elegible</Badge>}
              {item.escalated_to_aranda && <Badge color="#059669">escalado a Aranda</Badge>}
              {item.aranda_ticket_id && <Badge color="#059669">🎫 {item.aranda_ticket_id}{item.aranda_ticket_status ? ` · ${item.aranda_ticket_status}` : ""}</Badge>}
            </div>

            <p style={{ fontSize: 13, color: "#1a1a2e", lineHeight: 1.7, margin: 0 }}>
              <strong style={{ color: C }}>Resumen:</strong> {summary}
            </p>

            <div className="botiq-summary-stats">
              <SummaryStat label="Inicio" value={item.created_at ? new Date(item.created_at).toLocaleString() : "N/A"} />
              <SummaryStat label="Fin" value={item.ended_at ? new Date(item.ended_at).toLocaleString() : "En curso"} />
              <SummaryStat label="Preguntas" value={item.question_count ?? 0} />
              <SummaryStat label="Fuera de alcance" value={item.out_of_scope_count ?? 0} />
              <SummaryStat label="Intentos solución" value={item.resolution_attempts ?? 0} />
              <SummaryStat label="URL / IP" value={item.detected_url || item.detected_ip || "—"} />
            </div>
          </section>

          {/* Conversación completa */}
          <h4 style={{ color: C, fontSize: 13, margin: "0 0 10px", textTransform: "uppercase", letterSpacing: ".4px" }}>
            💬 Conversación completa
          </h4>

          {loading ? (
            <p style={{ color: "#6b6b8a", fontSize: 13 }}>Cargando mensajes...</p>
          ) : error ? (
            <div style={alertStyle}>⚠️ {error}</div>
          ) : messages.length === 0 ? (
            <p style={{ color: "#6b6b8a", fontSize: 13 }}>Esta conversación no tiene mensajes registrados.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {messages.map((msg) => <TranscriptBubble key={msg.id} msg={msg} />)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TranscriptBubble({ msg }) {
  const isUser = msg.role === "user";
  const isSystem = msg.role === "system";

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexDirection: isUser ? "row-reverse" : "row" }}>
      <div style={{ width: 28, height: 28, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, background: isUser ? "#e2e1f0" : `${C}12` }}>
        {isUser ? "👤" : "🤖"}
      </div>

      <div style={{ maxWidth: "82%", minWidth: 0 }}>
        <div
          style={{
            background: isUser ? `linear-gradient(135deg, ${C}, ${C}dd)` : isSystem ? "#eef2ff" : "#f5f5fa",
            color: isUser ? "#fff" : "#1a1a2e",
            border: isUser ? "none" : "1px solid #e2e1f0",
            borderRadius: isUser ? "14px 4px 14px 14px" : "4px 14px 14px 14px",
            padding: "10px 14px",
            fontSize: 13,
            lineHeight: 1.65,
            whiteSpace: "pre-wrap",
            overflowWrap: "anywhere",
          }}
        >
          {msg.content}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 4, fontSize: 10, color: "#9ca3af", justifyContent: isUser ? "flex-end" : "flex-start", flexWrap: "wrap" }}>
          <span>{msg.created_at ? new Date(msg.created_at).toLocaleString() : ""}</span>
          {isSystem && <span style={{ color: "#7c3aed", fontWeight: 700 }}>sistema</span>}
          {msg.tokens_used != null && <span>{Math.round(msg.tokens_used)} tokens</span>}
          {msg.has_image && <span>📎 imagen adjunta</span>}
        </div>
      </div>
    </div>
  );
}

/* ---------- Resumen automático (sin IA, derivado de los datos) ---------- */

function buildSummary(item, messages) {
  const pf = item.selected_profile === "support_engineer" ? "ingeniero de soporte" : "empleado";
  const userMsgs = messages.filter((m) => m.role === "user");
  const first = userMsgs[0]?.content?.slice(0, 160);

  const parts = [];
  parts.push(`Sesión de ${pf} con ${item.question_count ?? userMsgs.length} pregunta(s)`);
  if (first) parts.push(`iniciada con la consulta “${first}${userMsgs[0].content.length > 160 ? "…" : ""}”`);
  if (item.detected_url) parts.push(`se detectó la URL ${item.detected_url}`);
  else if (item.detected_ip) parts.push(`se detectó la IP ${item.detected_ip}`);
  if (item.out_of_scope_count > 0) parts.push(`${item.out_of_scope_count} consulta(s) fuera de alcance`);
  if (item.resolution_attempts > 0) parts.push(`${item.resolution_attempts} intento(s) de solución guiada`);

  if (item.aranda_ticket_id) parts.push(`finalizó con ticket Aranda ${item.aranda_ticket_id}`);
  else if (item.escalated_to_aranda) parts.push("fue escalada a Aranda");
  else if (item.ticket_eligible) parts.push("quedó elegible para ticket como última instancia");

  if (item.session_status === "blocked") parts.push(`la sesión fue bloqueada${item.ended_reason ? ` (${item.ended_reason})` : ""}`);
  else if (item.session_status === "ended") parts.push(`la sesión finalizó${item.ended_reason ? ` (${item.ended_reason})` : ""}`);
  else parts.push("la sesión sigue activa");

  return parts.join("; ") + ".";
}

/* ---------- Componentes auxiliares ---------- */

function Metric({ label, value, color = C, icon }) {
  return (
    <article className="botiq-card" style={{ padding: "14px 16px" }}>
      <div style={{ color: "#6b6b8a", fontSize: 11, fontWeight: 750, display: "flex", alignItems: "center", gap: 6 }}>
        <span>{icon}</span> {label}
      </div>
      <div style={{ color, fontSize: 25, fontWeight: 900, marginTop: 4 }}>{value}</div>
    </article>
  );
}

function SummaryStat({ label, value }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e2e1f0", borderRadius: 10, padding: "8px 10px", minWidth: 0 }}>
      <div style={{ color: "#6b6b8a", fontSize: 10, fontWeight: 750, textTransform: "uppercase", letterSpacing: ".3px" }}>{label}</div>
      <div style={{ color: C, fontSize: 12, fontWeight: 800, marginTop: 2, overflowWrap: "anywhere" }}>{value}</div>
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
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

/* ---------- Estilos ---------- */

const labelStyle = { display: "grid", gap: 6, fontSize: 12, color: "#374151", fontWeight: 750, minWidth: 0 };

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

const exportBtn = {
  border: `1px solid ${C}30`,
  borderRadius: 12,
  background: "#fff",
  color: C,
  padding: "11px 18px",
  cursor: "pointer",
  fontWeight: 850,
  minHeight: 44,
  boxShadow: "0 4px 14px rgba(39,33,99,0.08)",
};

const viewBtn = {
  border: `1px solid ${C}25`,
  borderRadius: 10,
  background: `${C}08`,
  color: C,
  padding: "7px 14px",
  cursor: "pointer",
  fontWeight: 800,
  fontSize: 12,
};

const modalCloseBtn = {
  background: "rgba(255,255,255,0.12)",
  border: "1px solid rgba(255,255,255,0.2)",
  color: "rgba(255,255,255,0.8)",
  width: 32,
  height: 32,
  borderRadius: 9,
  cursor: "pointer",
  flexShrink: 0,
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
