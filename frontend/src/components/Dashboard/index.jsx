/**
 * Dashboard de métricas BOTIQ — Solo administradores.
 */

import { useState, useEffect } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from "recharts";
import { MessageSquare, Server, BookOpen, AlertTriangle, TrendingUp, Users } from "lucide-react";
import { dashboardAPI } from "../../services/api";

const COLORS = ["#1E3A5F", "#3B82F6", "#8B5CF6", "#10B981", "#F59E0B"];

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    fetchData();
  }, [days]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [metricsRes, summaryRes] = await Promise.all([
        dashboardAPI.metrics(days),
        dashboardAPI.summary(),
      ]);
      setMetrics(metricsRes.data);
      setSummary(summaryRes.data);
    } catch (err) {
      console.error("Error cargando métricas:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingDashboard />;

  const moduleData = [
    { name: "Empleados", value: 45, color: COLORS[0] },
    { name: "Soporte RAG", value: 35, color: COLORS[1] },
    { name: "Servidores", value: 20, color: COLORS[2] },
  ];

  return (
    <div style={{ padding: "32px", background: "#F9FAFB", minHeight: "100vh" }}>
      {/* Header */}
      <div style={{ marginBottom: "32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: "28px", fontWeight: 700, color: "#111827", margin: 0 }}>
            Dashboard BOTIQ
          </h1>
          <p style={{ color: "#6B7280", margin: "4px 0 0" }}>Métricas y análisis del chatbot corporativo</p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          style={{ padding: "8px 16px", borderRadius: "8px", border: "1px solid #E5E7EB", fontSize: "14px", background: "#fff" }}
        >
          <option value={7}>Últimos 7 días</option>
          <option value={30}>Últimos 30 días</option>
          <option value={90}>Últimos 90 días</option>
        </select>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "20px", marginBottom: "32px" }}>
        <KPICard
          icon={<MessageSquare size={20} />}
          label="Conversaciones"
          value={metrics?.total_conversations?.toLocaleString() || "0"}
          color="#1E3A5F"
        />
        <KPICard
          icon={<Users size={20} />}
          label="Mensajes totales"
          value={metrics?.total_messages?.toLocaleString() || "0"}
          color="#3B82F6"
        />
        <KPICard
          icon={<TrendingUp size={20} />}
          label="Tokens Vertex AI"
          value={metrics?.total_tokens_used?.toLocaleString() || "0"}
          color="#8B5CF6"
        />
        <KPICard
          icon={<AlertTriangle size={20} />}
          label="Escalados a Aranda"
          value={metrics?.escalations_to_aranda?.toLocaleString() || "0"}
          color="#F59E0B"
        />
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px", marginBottom: "24px" }}>
        {/* Conversaciones por módulo */}
        <div style={{ background: "#fff", borderRadius: "12px", padding: "24px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <h3 style={{ margin: "0 0 20px", fontSize: "16px", fontWeight: 600, color: "#111827" }}>
            Distribución por módulo
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={moduleData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {moduleData.map((entry, index) => (
                  <Cell key={index} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Pie chart */}
        <div style={{ background: "#fff", borderRadius: "12px", padding: "24px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
          <h3 style={{ margin: "0 0 20px", fontSize: "16px", fontWeight: 600, color: "#111827" }}>
            Uso de módulos
          </h3>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={moduleData} dataKey="value" cx="50%" cy="50%" outerRadius={70}>
                {moduleData.map((entry, index) => (
                  <Cell key={index} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "8px" }}>
            {moduleData.map((item) => (
              <div key={item.name} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px" }}>
                <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: item.color }} />
                <span style={{ color: "#6B7280" }}>{item.name}</span>
                <span style={{ marginLeft: "auto", fontWeight: 600, color: "#111827" }}>{item.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Server status y Support gaps */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
        <ServerStatusTable />
        <SupportGapsTable />
      </div>
    </div>
  );
}

function KPICard({ icon, label, value, color }) {
  return (
    <div style={{ background: "#fff", borderRadius: "12px", padding: "20px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: `${color}15`, display: "flex", alignItems: "center", justifyContent: "center", color }}>
          {icon}
        </div>
      </div>
      <div style={{ fontSize: "28px", fontWeight: 700, color: "#111827" }}>{value}</div>
      <div style={{ fontSize: "13px", color: "#6B7280", marginTop: "4px" }}>{label}</div>
    </div>
  );
}

function ServerStatusTable() {
  const mockServers = [
    { name: "Servidor-APP-01", status: "up", cpu: 45, memory: 67 },
    { name: "Servidor-DB-01", status: "up", cpu: 23, memory: 81 },
    { name: "Servidor-WEB-01", status: "degraded", cpu: 89, memory: 92 },
  ];

  return (
    <div style={{ background: "#fff", borderRadius: "12px", padding: "24px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
      <h3 style={{ margin: "0 0 16px", fontSize: "16px", fontWeight: 600, color: "#111827", display: "flex", alignItems: "center", gap: "8px" }}>
        <Server size={16} /> Estado de Servidores
      </h3>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #F3F4F6" }}>
            <th style={{ textAlign: "left", padding: "8px 0", color: "#6B7280", fontWeight: 500 }}>Servidor</th>
            <th style={{ textAlign: "center", padding: "8px 0", color: "#6B7280", fontWeight: 500 }}>Estado</th>
            <th style={{ textAlign: "right", padding: "8px 0", color: "#6B7280", fontWeight: 500 }}>CPU</th>
            <th style={{ textAlign: "right", padding: "8px 0", color: "#6B7280", fontWeight: 500 }}>RAM</th>
          </tr>
        </thead>
        <tbody>
          {mockServers.map((server) => (
            <tr key={server.name} style={{ borderBottom: "1px solid #F9FAFB" }}>
              <td style={{ padding: "10px 0", color: "#111827" }}>{server.name}</td>
              <td style={{ textAlign: "center", padding: "10px 0" }}>
                <span style={{
                  padding: "2px 8px", borderRadius: "20px", fontSize: "11px", fontWeight: 600,
                  background: server.status === "up" ? "#D1FAE5" : "#FEF3C7",
                  color: server.status === "up" ? "#065F46" : "#92400E",
                }}>
                  {server.status === "up" ? "Activo" : "Degradado"}
                </span>
              </td>
              <td style={{ textAlign: "right", padding: "10px 0", color: server.cpu > 80 ? "#EF4444" : "#111827" }}>
                {server.cpu}%
              </td>
              <td style={{ textAlign: "right", padding: "10px 0", color: server.memory > 85 ? "#EF4444" : "#111827" }}>
                {server.memory}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SupportGapsTable() {
  const mockGaps = [
    { query: "Configuración VPN corporativa", frequency: 23, confidence: 0.32 },
    { query: "Error autenticación LDAP", frequency: 18, confidence: 0.41 },
    { query: "Backup de base de datos", frequency: 15, confidence: 0.28 },
  ];

  return (
    <div style={{ background: "#fff", borderRadius: "12px", padding: "24px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
      <h3 style={{ margin: "0 0 16px", fontSize: "16px", fontWeight: 600, color: "#111827", display: "flex", alignItems: "center", gap: "8px" }}>
        <BookOpen size={16} /> Brechas de Conocimiento
      </h3>
      <p style={{ fontSize: "12px", color: "#9CA3AF", margin: "0 0 16px" }}>
        Consultas frecuentes sin respuesta confiable en el RAG
      </p>
      {mockGaps.map((gap, i) => (
        <div key={i} style={{ padding: "10px 0", borderBottom: i < mockGaps.length - 1 ? "1px solid #F9FAFB" : "none" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
            <span style={{ fontSize: "13px", color: "#111827", fontWeight: 500 }}>{gap.query}</span>
            <span style={{ fontSize: "12px", color: "#6B7280" }}>{gap.frequency}x</span>
          </div>
          <div style={{ background: "#F3F4F6", borderRadius: "4px", height: "4px" }}>
            <div style={{ background: "#EF4444", width: `${gap.confidence * 100}%`, height: "100%", borderRadius: "4px" }} />
          </div>
          <div style={{ fontSize: "11px", color: "#9CA3AF", marginTop: "4px" }}>
            Confianza: {(gap.confidence * 100).toFixed(0)}% — Agregar a base de conocimiento
          </div>
        </div>
      ))}
    </div>
  );
}

function LoadingDashboard() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#F9FAFB" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ width: "40px", height: "40px", border: "3px solid #E5E7EB", borderTop: "3px solid #1E3A5F", borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 16px" }} />
        <p style={{ color: "#6B7280" }}>Cargando métricas...</p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  );
}
