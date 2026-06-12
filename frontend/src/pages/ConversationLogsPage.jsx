import { useEffect, useState } from "react";
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
    <div style={{ minHeight: "100vh", background: "#f5f5fa" }}>
      <Navbar currentPage="conversation-logs" />

      <main style={{ padding: "28px 32px" }}>
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ color: C, fontSize: 24, margin: 0 }}>Logs de conversaciones</h1>
          <p style={{ color: "#6b6b8a", marginTop: 6, fontSize: 13 }}>
            Consulta trazabilidad por usuario, perfil, sesión, URL/IP, elegibilidad de ticket y escalamiento a Aranda.
          </p>
        </header>

        {error && <div style={alertStyle}>⚠️ {error}</div>}

        <section style={cardStyle}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "end" }}>
            <label style={labelStyle}>
              Buscar
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="usuario, correo o texto consultado"
                style={{ ...inputStyle, minWidth: 280 }}
              />
            </label>

            <label style={labelStyle}>
              Perfil
              <select value={profile} onChange={(e) => setProfile(e.target.value)} style={inputStyle}>
                <option value="">Todos</option>
                <option value="employee">Empleado</option>
                <option value="support_engineer">Ingeniero de soporte</option>
              </select>
            </label>

            <label style={labelStyle}>
              Estado
              <select value={status} onChange={(e) => setStatus(e.target.value)} style={inputStyle}>
                <option value="">Todos</option>
                <option value="active">Activa</option>
                <option value="ended">Finalizada</option>
                <option value="blocked">Bloqueada</option>
              </select>
            </label>

            <button onClick={load} style={primaryBtn}>Buscar</button>
          </div>
        </section>

        <section style={cardStyle}>
          {loading ? (
            <p style={{ color: "#6b6b8a" }}>Cargando logs...</p>
          ) : logs.length === 0 ? (
            <p style={{ color: "#6b6b8a" }}>No hay registros para mostrar.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 1180 }}>
                <thead>
                  <tr style={{ background: "#f5f5fa", color: C, textAlign: "left", fontSize: 12 }}>
                    <Th>Fecha</Th>
                    <Th>Usuario</Th>
                    <Th>Perfil</Th>
                    <Th>Estado</Th>
                    <Th>Preguntas</Th>
                    <Th>URL/IP</Th>
                    <Th>Ticket</Th>
                    <Th>Último mensaje</Th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id} style={{ borderBottom: "1px solid #e2e1f0", fontSize: 12 }}>
                      <Td>{new Date(log.created_at).toLocaleString()}</Td>
                      <Td>
                        <strong style={{ color: C }}>{log.user_full_name}</strong>
                        <div style={{ color: "#6b6b8a", fontSize: 11 }}>{log.user_email}</div>
                      </Td>
                      <Td>
                        <Badge>{log.selected_profile === "support_engineer" ? "Soporte" : "Empleado"}</Badge>
                        {log.support_network_validated && <Badge ok>red ok</Badge>}
                      </Td>
                      <Td><StatusBadge status={log.session_status} /></Td>
                      <Td>
                        {log.question_count}
                        <div style={{ color: "#6b6b8a", fontSize: 11 }}>
                          intentos: {log.resolution_attempts}
                        </div>
                      </Td>
                      <Td>
                        {log.detected_url && <div style={{ color: "#0284c7" }}>🔗 {log.detected_url}</div>}
                        {log.detected_ip && <div style={{ color: "#0284c7" }}>IP {log.detected_ip}</div>}
                        {!log.detected_url && !log.detected_ip && <span style={{ color: "#9ca3af" }}>N/A</span>}
                      </Td>
                      <Td>
                        {log.aranda_ticket_id ? (
                          <Badge ok>{log.aranda_ticket_id}</Badge>
                        ) : log.ticket_eligible ? (
                          <Badge warn>elegible</Badge>
                        ) : (
                          <span style={{ color: "#9ca3af" }}>No</span>
                        )}
                      </Td>
                      <Td style={{ maxWidth: 300 }}>
                        <span style={{ color: "#374151" }}>{log.last_message || "Sin mensaje"}</span>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Th({ children }) {
  return <th style={{ padding: "10px 12px", borderBottom: "1px solid #e2e1f0" }}>{children}</th>;
}

function Td({ children, style = {} }) {
  return <td style={{ padding: "12px", verticalAlign: "top", ...style }}>{children}</td>;
}

function Badge({ children, ok = false, warn = false }) {
  let background = "#f5f5fa";
  let color = C;
  let border = "#e2e1f0";

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

  return <span style={{ display: "inline-block", background, color, border: `1px solid ${border}`, borderRadius: 999, padding: "3px 8px", fontSize: 11, fontWeight: 700, marginRight: 4 }}>{children}</span>;
}

function StatusBadge({ status }) {
  if (status === "active") return <Badge ok>activa</Badge>;
  if (status === "blocked") return <span style={{ background: "#fef2f2", color: "#991b1b", border: "1px solid #fecaca", borderRadius: 999, padding: "3px 8px", fontSize: 11, fontWeight: 700 }}>bloqueada</span>;
  return <Badge>{status || "ended"}</Badge>;
}

const cardStyle = {
  background: "#fff",
  border: "1px solid #e2e1f0",
  borderRadius: 14,
  padding: 20,
  marginBottom: 20,
  boxShadow: "0 1px 4px rgba(39,33,99,0.06)",
};

const labelStyle = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
  fontSize: 12,
  fontWeight: 700,
  color: "#374151",
};

const inputStyle = {
  border: "1px solid #e2e1f0",
  borderRadius: 8,
  padding: "9px 10px",
  fontSize: 13,
  outline: "none",
  background: "#fff",
};

const primaryBtn = {
  background: C,
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "10px 16px",
  cursor: "pointer",
  fontWeight: 700,
};

const alertStyle = {
  background: "#fef2f2",
  color: "#991b1b",
  border: "1px solid #fecaca",
  borderRadius: 10,
  padding: "12px 14px",
  marginBottom: 18,
  fontSize: 13,
};
