import { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from "recharts";
import { MessageSquare, Server, BookOpen, AlertTriangle, TrendingUp, Users, RefreshCw, Activity } from "lucide-react";
import { dashboardAPI } from "../../services/api";

const COLORS = ["#1E3A5F", "#3B82F6", "#8B5CF6", "#10B981", "#F59E0B"];
const PRIMARY = "#1E3A5F";

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [error, setError] = useState(null);

  useEffect(() => { fetchData(); }, [days]);

  const fetchData = async () => {
    setLoading(true); setError(null);
    try {
      const [m, s] = await Promise.all([dashboardAPI.metrics(days), dashboardAPI.summary()]);
      setMetrics(m.data); setSummary(s.data);
    } catch (e) {
      setError("Error cargando métricas. Verifica tu sesión.");
    } finally { setLoading(false); }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorScreen msg={error} onRetry={fetchData} />;

  const moduleData = [
    { name: "Empleados",    value: 45, color: COLORS[0] },
    { name: "Soporte RAG",  value: 35, color: COLORS[1] },
    { name: "Servidores",   value: 20, color: COLORS[2] },
  ];

  const mockTrend = Array.from({ length: 7 }, (_, i) => ({
    day: ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"][i],
    conversaciones: Math.floor(Math.random() * 50) + 10,
    tokens: Math.floor(Math.random() * 5000) + 1000,
  }));

  return (
    <div style={{ padding: "28px 32px", background: "#F9FAFB", minHeight: "100vh" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "#111827" }}>Dashboard BOTIQ</h1>
          <p style={{ color: "#6B7280", fontSize: 14, marginTop: 4 }}>
            Métricas del chatbot corporativo — últimos {days} días
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select value={days} onChange={(e) => setDays(+e.target.value)}
            style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #E5E7EB", fontSize: 13, background: "#fff", cursor: "pointer" }}>
            <option value={7}>Últimos 7 días</option>
            <option value={30}>Últimos 30 días</option>
            <option value={90}>Últimos 90 días</option>
          </select>
          <button onClick={fetchData}
            style={{ padding: "8px 12px", background: PRIMARY, color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <RefreshCw size={14} /> Actualizar
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 18, marginBottom: 24 }}>
        <KPI icon={<MessageSquare size={18} />} label="Conversaciones" value={metrics?.total_conversations ?? 0} color={COLORS[0]} />
        <KPI icon={<Users size={18} />} label="Mensajes totales" value={metrics?.total_messages ?? 0} color={COLORS[1]} />
        <KPI icon={<TrendingUp size={18} />} label="Tokens Vertex AI" value={(metrics?.total_tokens_used ?? 0).toLocaleString()} color={COLORS[2]} />
        <KPI icon={<Activity size={18} />} label="Tiempo respuesta (ms)" value={Math.round(metrics?.avg_response_time_ms ?? 0)} color={COLORS[3]} />
        <KPI icon={<AlertTriangle size={18} />} label="Escalados a Aranda" value={metrics?.escalations_to_aranda ?? 0} color={COLORS[4]} />
      </div>

      {/* Fila 1: Tendencia + Módulos */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card title="Conversaciones por día">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={mockTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="conversaciones" stroke={PRIMARY} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Uso por módulo">
          <ResponsiveContainer width="100%" height={140}>
            <PieChart>
              <Pie data={moduleData} dataKey="value" cx="50%" cy="50%" outerRadius={60} paddingAngle={3}>
                {moduleData.map((e, i) => <Cell key={i} fill={e.color} />)}
              </Pie>
              <Tooltip formatter={(v) => `${v}%`} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
            {moduleData.map((m) => (
              <div key={m.name} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: m.color, flexShrink: 0 }} />
                <span style={{ color: "#6B7280", flex: 1 }}>{m.name}</span>
                <span style={{ fontWeight: 600, color: "#111827" }}>{m.value}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Fila 2: Tokens + Resumen hoy */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card title="Consumo de tokens Vertex AI">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={mockTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="tokens" fill={COLORS[2]} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Resumen del período">
          {summary && (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <StatRow label="Conversaciones hoy" value={summary.today_conversations} />
              <StatRow label="Esta semana" value={summary.week_conversations} />
              <StatRow label="Módulo más usado" value={summary.top_module} isText />
              <StatRow label="Brechas de conocimiento" value={summary.support_gap_count} />
              {summary.most_reported_server && (
                <StatRow label="Servidor más reportado" value={summary.most_reported_server} isText />
              )}
            </div>
          )}
        </Card>
      </div>

      {/* Fila 3: Servidores + Brechas */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <ServerTable />
        <SupportGaps />
      </div>
    </div>
  );
}

function KPI({ icon, label, value, color }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: "18px 20px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
      <div style={{ width: 34, height: 34, borderRadius: 8, background: `${color}18`, display: "flex", alignItems: "center", justifyContent: "center", color, marginBottom: 12 }}>
        {icon}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: "#111827" }}>{value}</div>
      <div style={{ fontSize: 12, color: "#6B7280", marginTop: 3 }}>{label}</div>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: "20px 24px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, color: "#111827", marginBottom: 16 }}>{title}</h3>
      {children}
    </div>
  );
}

function StatRow({ label, value, isText }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 12, borderBottom: "1px solid #F9FAFB" }}>
      <span style={{ fontSize: 13, color: "#6B7280" }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>{value}</span>
    </div>
  );
}

function ServerTable() {
  const servers = [
    { name: "Servidor-APP-01", status: "up",       cpu: 45, mem: 67 },
    { name: "Servidor-DB-01",  status: "up",       cpu: 23, mem: 81 },
    { name: "Servidor-WEB-01", status: "degraded", cpu: 89, mem: 92 },
  ];
  return (
    <Card title="Estado de Servidores">
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr>
            {["Servidor", "Estado", "CPU", "RAM"].map(h => (
              <th key={h} style={{ textAlign: h === "CPU" || h === "RAM" ? "right" : "left", padding: "6px 0", color: "#6B7280", fontWeight: 500, borderBottom: "1px solid #F3F4F6" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {servers.map((s) => (
            <tr key={s.name}>
              <td style={{ padding: "10px 0", color: "#111827", fontSize: 12 }}>{s.name}</td>
              <td style={{ padding: "10px 0" }}>
                <span style={{
                  padding: "2px 8px", borderRadius: 20, fontSize: 10, fontWeight: 600,
                  background: s.status === "up" ? "#D1FAE5" : "#FEF3C7",
                  color: s.status === "up" ? "#065F46" : "#92400E",
                }}>
                  {s.status === "up" ? "Activo" : "Degradado"}
                </span>
              </td>
              <td style={{ textAlign: "right", padding: "10px 0", color: s.cpu > 80 ? "#EF4444" : "#374151", fontWeight: s.cpu > 80 ? 600 : 400 }}>{s.cpu}%</td>
              <td style={{ textAlign: "right", padding: "10px 0", color: s.mem > 85 ? "#EF4444" : "#374151", fontWeight: s.mem > 85 ? 600 : 400 }}>{s.mem}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function SupportGaps() {
  const gaps = [
    { query: "Configuración VPN corporativa", freq: 23, conf: 0.32 },
    { query: "Error autenticación LDAP",      freq: 18, conf: 0.41 },
    { query: "Backup base de datos",          freq: 15, conf: 0.28 },
    { query: "Certificados SSL expirados",    freq: 11, conf: 0.35 },
  ];
  return (
    <Card title="Brechas de Conocimiento RAG">
      <p style={{ fontSize: 11, color: "#9CA3AF", marginBottom: 14 }}>
        Consultas frecuentes con baja confianza — agregar a base de conocimiento
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {gaps.map((g, i) => (
          <div key={i}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: "#374151", fontWeight: 500 }}>{g.query}</span>
              <span style={{ fontSize: 11, color: "#9CA3AF" }}>{g.freq}x</span>
            </div>
            <div style={{ background: "#F3F4F6", borderRadius: 4, height: 4 }}>
              <div style={{ background: g.conf < 0.4 ? "#EF4444" : "#F59E0B", width: `${g.conf * 100}%`, height: "100%", borderRadius: 4 }} />
            </div>
            <div style={{ fontSize: 10, color: "#9CA3AF", marginTop: 2 }}>
              Confianza: {(g.conf * 100).toFixed(0)}%
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Loader() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#F9FAFB" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ width: 40, height: 40, border: `3px solid #E5E7EB`, borderTop: `3px solid ${PRIMARY}`, borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 16px" }} />
        <p style={{ color: "#6B7280", fontSize: 14 }}>Cargando métricas...</p>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </div>
  );
}

function ErrorScreen({ msg, onRetry }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100vh", gap: 16 }}>
      <AlertTriangle size={40} color="#EF4444" />
      <p style={{ color: "#374151", fontSize: 15 }}>{msg}</p>
      <button onClick={onRetry} style={{ padding: "8px 20px", background: PRIMARY, color: "#fff", border: "none", borderRadius: 8, cursor: "pointer" }}>Reintentar</button>
    </div>
  );
}
