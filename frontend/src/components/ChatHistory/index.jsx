import { useEffect, useState } from "react";
import { chatAPI } from "../../services/api";

const C = "#272163";

export default function ChatHistory({ onSelect }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await chatAPI.conversations();
      setItems(data);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <aside className="botiq-chat-history" style={{ background: "var(--botiq-card-bg)", borderRight: "1px solid var(--botiq-border)", minHeight: "calc(100vh - 58px)", padding: 16, overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h3 style={{ color: C, fontSize: 14, margin: 0 }}>Historial</h3>
        <button onClick={load} style={smallBtn}>↻</button>
      </div>

      {loading ? (
        <p style={muted}>Cargando...</p>
      ) : items.length === 0 ? (
        <p style={muted}>No tienes conversaciones registradas.</p>
      ) : (
        <div style={{ display: "grid", gap: 9 }}>
          {items.map((c) => (
            <button key={c.id} onClick={() => onSelect?.(c)} style={itemBtn}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span style={{ color: C, fontSize: 12, fontWeight: 800 }}>
                  {c.selected_profile === "support_engineer" ? "Soporte" : "Empleado"}
                </span>
                <span style={{ fontSize: 10, color: statusColor(c.session_status), fontWeight: 700 }}>
                  {c.session_status || "active"}
                </span>
              </div>

              <div style={{ color: "var(--botiq-muted)", fontSize: 11, marginTop: 6 }}>
                {new Date(c.created_at).toLocaleString()}
              </div>

              {c.detected_url && (
                <div style={{ color: "#0284c7", fontSize: 10, marginTop: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  🔗 {c.detected_url}
                </div>
              )}

              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                <Tag>{c.question_count || 0} preguntas</Tag>
                {c.ticket_eligible && <Tag warn>ticket elegible</Tag>}
                {c.aranda_ticket_id && <Tag ok>{c.aranda_ticket_id}</Tag>}
                {c.out_of_scope_count > 0 && <Tag danger>{c.out_of_scope_count} fuera alcance</Tag>}
                {c.support_network_validated && <Tag ok>red ok</Tag>}
              </div>
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}

function statusColor(status) {
  if (status === "active") return "#059669";
  if (status === "blocked") return "#dc2626";
  return "var(--botiq-muted)";
}

function Tag({ children, danger = false, ok = false, warn = false }) {
  let background = "var(--botiq-surface)";
  let color = C;
  let border = "var(--botiq-border)";

  if (danger) {
    background = "#fef2f2";
    color = "#991b1b";
    border = "#fecaca";
  }

  if (ok) {
    background = "#ecfdf5";
    color = "#065f46";
    border = "#bbf7d0";
  }

  if (warn) {
    background = "#fffbeb";
    color = "#92400e";
    border = "#fde68a";
  }

  return (
    <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 999, background, color, border: `1px solid ${border}`, fontWeight: 700 }}>
      {children}
    </span>
  );
}

const muted = { color: "var(--botiq-muted)", fontSize: 12, lineHeight: 1.5 };

const smallBtn = {
  border: "1px solid var(--botiq-border)",
  background: "var(--botiq-surface)",
  color: C,
  width: 28,
  height: 28,
  borderRadius: 8,
  cursor: "pointer",
};

const itemBtn = {
  textAlign: "left",
  border: "1px solid var(--botiq-border)",
  background: "#fdfdff",
  borderRadius: 12,
  padding: 11,
  cursor: "pointer",
};
