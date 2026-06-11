import { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line } from "recharts";
import { MessageSquare, Server, BookOpen, AlertTriangle, TrendingUp, Users,
  RefreshCw, Activity, Brain, ArrowUpCircle } from "lucide-react";
import { dashboardAPI } from "../../services/api";

const PRIMARY = "#1E3A5F";
const COLORS = [PRIMARY, "#3B82F6", "#8B5CF6", "#10B981", "#F59E0B", "#EF4444"];

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [metrics, setMetrics] = useState(null);
  const [summary, setSummary] = useState(null);
  const [byModule, setByModule] = useState([]);
  const [byDay, setByDay] = useState([]);
  const [topFaqs, setTopFaqs] = useState([]);
  const [tokenData, setTokenData] = useState([]);
  const [gaps, setGaps] = useState([]);
  const [escalation, setEscalation] = useState(null);

  useEffect(() => { fetchAll(); }, [days]);

  const fetchAll = async () => {
    setLoading(true); setError(null);
    try {
      const [m, s, mod, day, faqs, tok, g, esc] = await Promise.all([
        dashboardAPI.metrics(days),
        dashboardAPI.summary(),
        dashboardAPI.byModule(days),
        dashboardAPI.byDay(days),
        dashboardAPI.topFaqs(8),
        dashboardAPI.tokenConsumption(days),
        dashboardAPI.knowledgeGaps(8),
        dashboardAPI.escalationRate(days),
      ]);
      setMetrics(m.data); setSummary(s.data);
      setByModule(mod.data); setByDay(day.data);
      setTopFaqs(faqs.data); setTokenData(tok.data);
      setGaps(g.data); setEscalation(esc.data);
    } catch (e) {
      setError("Error cargando métricas. Verifica tu sesión de administrador.");
    } finally { setLoading(false); }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorScreen msg={error} onRetry={fetchAll} />;

  const moduleChartData = byModule.map((m, i) => ({
    name: { employee: "Empleados", support_rag: "Soporte RAG", server_validation: "Servidores" }[m.module] || m.module,
    value: m.count,
    color: COLORS[i % COLORS.length],
  }));

  return (
    <div style={{ padding: "28px 32px", background: "#F9FAFB", minHeight: "100vh" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 700, color: "#111827" }}>Dashboard BOTIQ</h1>
          <p style={{ color: "#6B7280", fontSize: 13, marginTop: 4 }}>
            Datos reales — últimos {days} días
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select value={days} onChange={(e) => setDays(+e.target.value)}
            style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #E5E7EB", fontSize: 13, background: "#fff" }}>
            <option value={7}>Últimos 7 días</option>
            <option value={30}>Últimos 30 días</option>
            <option value={90}>Últimos 90 días</option>
          </select>
          <button onClick={fetchAll}
            style={{ padding: "8px 12px", background: PRIMARY, color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <RefreshCw size={13} /> Actualizar
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 16, marginBottom: 24 }}>
        <KPI icon={<MessageSquare size={17} />} label="Conversaciones"    value={metrics?.total_conversations ?? 0}            color={COLORS[0]} />
        <KPI icon={<Users size={17} />}         label="Mensajes totales"   value={metrics?.total_messages ?? 0}                  color={COLORS[1]} />
        <KPI icon={<TrendingUp size={17} />}    label="Tokens Vertex AI"   value={(metrics?.total_tokens_used ?? 0).toLocaleString()} color={COLORS[2]} />
        <KPI icon={<Activity size={17} />}      label="Resp. prom. (ms)"   value={Math.round(metrics?.avg_response_time_ms ?? 0)} color={COLORS[3]} />
        <KPI icon={<AlertTriangle size={17} />} label="Escalados Aranda"   value={metrics?.escalations_to_aranda ?? 0}           color={COLORS[4]} />
        <KPI icon={<Brain size={17} />}         label="Brechas RAG abiertas" value={metrics?.open_knowledge_gaps ?? 0}           color={COLORS[5]} />
      </div>

      {/* Fila 1: Trend + Módulos */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card title="Conversaciones por día">
          {byDay.length > 0 ? (
            <ResponsiveContainer width="100%" height={190}>
              <LineChart data={byDay}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke={PRIMARY} strokeWidth={2} dot={{ r: 3 }} name="Conversaciones" />
              </LineChart>
            </ResponsiveContainer>
          ) : <EmptyChart />}
        </Card>

        <Card title="Por módulo">
          {moduleChartData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={120}>
                <PieChart>
                  <Pie data={moduleChartData} dataKey="value" cx="50%" cy="50%" outerRadius={55} paddingAngle={3}>
                    {moduleChartData.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 8 }}>
                {moduleChartData.map((m) => (
                  <div key={m.name} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
                    <div style={{ width: 9, height: 9, borderRadius: "50%", background: m.color }} />
                    <span style={{ flex: 1, color: "#6B7280" }}>{m.name}</span>
                    <span style={{ fontWeight: 600 }}>{m.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <EmptyChart />}
        </Card>
      </div>

      {/* Fila 2: Tokens + Escalaciones */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card title="Consumo de tokens Vertex AI por día">
          {tokenData.length > 0 ? (
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={tokenData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="tokens" fill={COLORS[2]} radius={[3, 3, 0, 0]} name="Tokens" />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyChart />}
        </Card>

        <Card title="Tasa de escalaciones">
          {escalation ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 8 }}>
              <StatRow label="Total conversaciones" value={escalation.total} />
              <StatRow label="Escaladas a Aranda" value={escalation.escalated} />
              <div style={{ textAlign: "center", marginTop: 8 }}>
                <div style={{ fontSize: 36, fontWeight: 800, color: escalation.rate_pct > 20 ? "#EF4444" : COLORS[3] }}>
                  {escalation.rate_pct}%
                </div>
                <div style={{ fontSize: 12, color: "#6B7280" }}>tasa de escalación</div>
              </div>
            </div>
          ) : <EmptyChart />}
        </Card>
      </div>

      {/* Fila 3: FAQs + Knowledge Gaps */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <Card title="FAQs más consultadas">
          {topFaqs.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {topFaqs.map((f, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", borderBottom: "1px solid #F9FAFB" }}>
                  <div style={{ width: 22, height: 22, borderRadius: "50%", background: `${PRIMARY}18`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: PRIMARY, flexShrink: 0 }}>{i + 1}</div>
                  <span style={{ flex: 1, fontSize: 12, color: "#374151" }}>{f.question.slice(0, 55)}{f.question.length > 55 ? "…" : ""}</span>
                  <span style={{ fontSize: 11, color: "#9CA3AF", whiteSpace: "nowrap" }}>{f.hits}x</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: "#9CA3AF", fontSize: 13, textAlign: "center", marginTop: 20 }}>
              Sin FAQs consultadas aún
            </p>
          )}
        </Card>

        <Card title="Brechas de Conocimiento RAG">
          <p style={{ fontSize: 11, color: "#9CA3AF", marginBottom: 12 }}>
            Consultas sin respuesta confiable — requieren documentación
          </p>
          {gaps.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {gaps.map((g, i) => (
                <div key={i}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 12, color: "#374151", fontWeight: 500 }}>{g.query.slice(0, 50)}{g.query.length > 50 ? "…" : ""}</span>
                    <span style={{ fontSize: 11, color: "#9CA3AF" }}>{g.frequency}x</span>
                  </div>
                  <div style={{ background: "#F3F4F6", borderRadius: 3, height: 4 }}>
                    <div style={{
                      background: g.avg_confidence < 0.4 ? "#EF4444" : "#F59E0B",
                      width: `${g.avg_confidence * 100}%`, height: "100%", borderRadius: 3,
                    }} />
                  </div>
                  <div style={{ fontSize: 10, color: "#9CA3AF", marginTop: 2 }}>
                    Confianza: {(g.avg_confidence * 100).toFixed(0)}% · {g.module}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: "#10B981", fontSize: 13, textAlign: "center", marginTop: 20 }}>
              ✅ Sin brechas detectadas
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}

function KPI({ icon, label, value, color }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: "16px 18px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: `${color}18`, display: "flex", alignItems: "center", justifyContent: "center", color, marginBottom: 10 }}>{icon}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: "#111827" }}>{value.toLocaleString?.() ?? value}</div>
      <div style={{ fontSize: 11, color: "#6B7280", marginTop: 3 }}>{label}</div>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: "20px 22px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, color: "#111827", marginBottom: 14 }}>{title}</h3>
      {children}
    </div>
  );
}

function StatRow({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, paddingBottom: 8, borderBottom: "1px solid #F9FAFB" }}>
      <span style={{ color: "#6B7280" }}>{label}</span>
      <span style={{ fontWeight: 600, color: "#111827" }}>{value}</span>
    </div>
  );
}

function EmptyChart() {
  return (
    <div style={{ height: 120, display: "flex", alignItems: "center", justifyContent: "center", color: "#D1D5DB", fontSize: 13 }}>
      Sin datos para este período
    </div>
  );
}

function Loader() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#F9FAFB" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ width: 38, height: 38, border: `3px solid #E5E7EB`, borderTop: `3px solid ${PRIMARY}`, borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 14px" }} />
        <p style={{ color: "#6B7280", fontSize: 13 }}>Cargando métricas reales...</p>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </div>
  );
}

function ErrorScreen({ msg, onRetry }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100vh", gap: 14 }}>
      <AlertTriangle size={38} color="#EF4444" />
      <p style={{ color: "#374151", fontSize: 14, textAlign: "center", maxWidth: 300 }}>{msg}</p>
      <button onClick={onRetry} style={{ padding: "8px 20px", background: PRIMARY, color: "#fff", border: "none", borderRadius: 8, cursor: "pointer" }}>Reintentar</button>
    </div>
  );
}
