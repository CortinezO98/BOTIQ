import { useEffect, useState } from "react";
import Navbar from "../components/Layout/Navbar";
import { chatAPI } from "../services/api";

const C = "#272163";

export default function ConversationLogsPage() {
  const [logs, setLogs] = useState([]);
  const [filters, setFilters] = useState({ selected_profile: "", session_status: "" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (filters.selected_profile) params.selected_profile = filters.selected_profile;
      if (filters.session_status) params.session_status = filters.session_status;
      const { data } = await chatAPI.adminConversationLogs(params);
      setLogs(data);
    } catch (e) {
      setError(e.response?.data?.detail || "Error cargando logs de conversaciones");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5fa" }}>
      <Navbar currentPage="conversation-logs" />

      <main style={{ padding: "28px 32px" }}>
        <header style={{ marginBottom: 22 }}>
          <h1 style={{ color: C, margin: 0, fontSize: 24 }}>Logs de conversaciones</h1>
          <p style={{ color: "#6b6b8a", fontSize: 13, marginTop: 6 }}>
            Trazabilidad de sesiones por usuario, perfil seleccionado, preguntas consumidas y cierres por control del bot.
          </p>
        </header>

        <section style={card}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "end" }}>
            <Field label="Perfil">
              <select value={filters.selected_profile} onChange={(e) => setFilters({ ...filters, selected_profile: e.target.value })} style={input}>
                <option value="">Todos</option>
                <option value="employee">Empleado</option>
                <option value="support_engineer">Ingeniero de Soporte</option>
              </select>
            </Field>

            <Field label="Estado">
              <select value={filters.session_status} onChange={(e) => setFilters({ ...filters, session_status: e.target.value })} style={input}>
                <option value="">Todos</option>
                <option value="active">Activa</option>
                <option value="ended">Finalizada</option>
                <option value="blocked">Bloqueada</option>
              </select>
            </Field>

            <button onClick={load} style={primaryBtn}>Filtrar</button>
          </div>
        </section>

        {error && <div style={alert}>{error}</div>}

        <section style={card}>
          {loading ? (
            <p style={{ color: "#6b6b8a" }}>Cargando logs...</p>
          ) : logs.length === 0 ? (
            <p style={{ color: "#6b6b8a" }}>No hay logs para mostrar.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ color: C, textAlign: "left", borderBottom: "1px solid #e2e1f0" }}>
                    <th style={th}>Usuario</th>
                    <th style={th}>Perfil</th>
                    <th style={th}>Estado</th>
                    <th style={th}>Preguntas</th>
                    <th style={th}>Fuera alcance</th>
                    <th style={th}>Usuario red</th>
                    <th style={th}>Último mensaje</th>
                    <th style={th}>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id} style={{ borderBottom: "1px solid #f0effe" }}>
                      <td style={td}>
                        <strong>{log.user_full_name}</strong><br />
                        <span style={{ color: "#6b6b8a" }}>{log.user_email}</span>
                      </td>
                      <td style={td}>{log.selected_profile === "support_engineer" ? "Soporte" : "Empleado"}</td>
                      <td style={td}><Status status={log.session_status} reason={log.ended_reason} /></td>
                      <td style={td}>{log.question_count}</td>
                      <td style={td}>{log.out_of_scope_count}</td>
                      <td style={td}>{log.support_network_username || "-"}{log.support_network_validated && <span style={{ color: "#059669", marginLeft: 4 }}>✓</span>}</td>
                      <td style={{ ...td, maxWidth: 260 }}>{log.last_message || "-"}</td>
                      <td style={td}>{new Date(log.created_at).toLocaleString()}</td>
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

function Field({ label, children }) {
  return <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12, color: "#374151", fontWeight: 700 }}>{label}{children}</label>;
}

function Status({ status, reason }) {
  const color = status === "active" ? "#059669" : status === "blocked" ? "#dc2626" : "#6b6b8a";
  return <span title={reason || ""} style={{ color, fontWeight: 800 }}>{status}</span>;
}

const card = { background: "#fff", border: "1px solid #e2e1f0", borderRadius: 14, padding: 20, marginBottom: 18, boxShadow: "0 1px 4px rgba(39,33,99,0.06)" };
const input = { border: "1px solid #e2e1f0", borderRadius: 8, padding: "9px 10px", fontSize: 13, background: "#fff", minWidth: 180 };
const primaryBtn = { background: C, color: "#fff", border: "none", borderRadius: 8, padding: "10px 16px", cursor: "pointer", fontWeight: 700 };
const alert = { background: "#fef2f2", color: "#991b1b", border: "1px solid #fecaca", borderRadius: 10, padding: 12, marginBottom: 18 };
const th = { padding: "10px 8px", fontWeight: 800 };
const td = { padding: "12px 8px", verticalAlign: "top", color: "#374151" };
