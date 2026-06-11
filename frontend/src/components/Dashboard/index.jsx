import { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line } from "recharts";
import { dashboardAPI, supportAPI } from "../../services/api";

const C = "#272163";
const COLORS = [C, "#4f46e5", "#7c3aed", "#0284c7", "#059669", "#d97706", "#dc2626"];

const MOD_NAMES = {
  employee: "Empleados",
  support_rag: "Soporte RAG",
  server_validation: "Servidores",
};

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState({
    metrics: null, summary: null, byModule: [], byDay: [],
    topFaqs: [], tokens: [], gaps: [], escalation: null,
  });
  const [syncing, setSyncing] = useState(false);

  useEffect(() => { fetch(); }, [days]);

  const fetch = async () => {
    setLoading(true); setError(null);
    try {
      const [m, s, mod, day, faqs, tok, g, esc] = await Promise.all([
        dashboardAPI.metrics(days), dashboardAPI.summary(),
        dashboardAPI.byModule(days), dashboardAPI.byDay(days),
        dashboardAPI.topFaqs(8), dashboardAPI.tokenConsumption(days),
        dashboardAPI.knowledgeGaps(8), dashboardAPI.escalationRate(days),
      ]);
      setData({
        metrics: m.data, summary: s.data,
        byModule: mod.data, byDay: day.data,
        topFaqs: faqs.data, tokens: tok.data,
        gaps: g.data, escalation: esc.data,
      });
    } catch { setError("Error cargando métricas. Verifica tu sesión de administrador."); }
    finally { setLoading(false); }
  };

  const syncDrive = async () => {
    setSyncing(true);
    try {
      const r = await supportAPI.sync();
      alert(r.data.message || "Sincronización iniciada");
    } catch (e) {
      alert("Error al sincronizar: " + (e.response?.data?.detail || e.message));
    } finally { setSyncing(false); }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorScreen msg={error} onRetry={fetch} />;

  const { metrics, summary, byModule, byDay, topFaqs, tokens, gaps, escalation } = data;
  const modChart = byModule.map((m, i) => ({ name: MOD_NAMES[m.module] || m.module, value: m.count, color: COLORS[i % COLORS.length] }));

  return (
    <div style={{ padding: "28px 32px", background: "#f5f5fa", minHeight: "100vh" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: C, margin: 0 }}>Dashboard BOTIQ</h1>
          <p style={{ color: "#6b6b8a", fontSize: 13, marginTop: 4 }}>Métricas en tiempo real — últimos {days} días</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button onClick={syncDrive} disabled={syncing} style={{
            padding: "8px 14px", background: syncing ? "#e2e1f0" : `${C}15`,
            border: `1px solid ${C}30`, borderRadius: 8, cursor: syncing ? "not-allowed" : "pointer",
            fontSize: 12, color: C, fontWeight: 500, display: "flex", alignItems: "center", gap: 5,
          }}>
            {syncing ? "⏳ Sincronizando..." : "☁️ Sync Drive"}
          </button>
          <select value={days} onChange={e => setDays(+e.target.value)} style={{
            padding: "8px 12px", borderRadius: 8, border: `1px solid ${C}25`,
            fontSize: 13, background: "#fff", color: C, cursor: "pointer",
          }}>
            <option value={7}>7 días</option>
            <option value={30}>30 días</option>
            <option value={90}>90 días</option>
          </select>
          <button onClick={fetch} style={{
            padding: "8px 14px", background: C, border: "none", borderRadius: 8,
            cursor: "pointer", fontSize: 12, color: "#fff", fontWeight: 500,
            display: "flex", alignItems: "center", gap: 5,
            boxShadow: `0 2px 8px ${C}30`,
          }}>
            🔄 Actualizar
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px,1fr))", gap: 16, marginBottom: 24 }}>
        <KPI label="Conversaciones"    value={metrics?.total_conversations ?? 0} icon="💬" color={COLORS[0]} />
        <KPI label="Mensajes totales"  value={metrics?.total_messages ?? 0}      icon="📩" color={COLORS[1]} />
        <KPI label="Tokens Vertex AI"  value={(metrics?.total_tokens_used ?? 0).toLocaleString()} icon="⚡" color={COLORS[2]} />
        <KPI label="Resp. prom. (ms)"  value={Math.round(metrics?.avg_response_time_ms ?? 0)} icon="⏱️" color={COLORS[3]} />
        <KPI label="Escalados Aranda"  value={metrics?.escalations_to_aranda ?? 0} icon="🎫" color={COLORS[4]} />
        <KPI label="Brechas RAG"       value={metrics?.open_knowledge_gaps ?? 0} icon="🧠" color={COLORS[5]} />
      </div>

      {/* Fila 1 */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card title="Conversaciones por día">
          {byDay.length > 0 ? (
            <ResponsiveContainer width="100%" height={190}>
              <LineChart data={byDay}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e1f0" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b6b8a" }} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fontSize: 11, fill: "#6b6b8a" }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: `1px solid ${C}20`, fontSize: 12 }} />
                <Line type="monotone" dataKey="count" stroke={C} strokeWidth={2.5} dot={{ r: 3, fill: C }} name="Conversaciones" />
              </LineChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        <Card title="Por módulo">
          {modChart.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={120}>
                <PieChart>
                  <Pie data={modChart} dataKey="value" cx="50%" cy="50%" outerRadius={52} paddingAngle={3} innerRadius={24}>
                    {modChart.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip formatter={(v, n) => [v, n]} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                {modChart.map(m => (
                  <div key={m.name} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12 }}>
                    <div style={{ width: 9, height: 9, borderRadius: "50%", background: m.color, flexShrink: 0 }} />
                    <span style={{ flex: 1, color: "#6b6b8a" }}>{m.name}</span>
                    <span style={{ fontWeight: 600, color: C }}>{m.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <Empty />}
        </Card>
      </div>

      {/* Fila 2 */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card title="Consumo de tokens Vertex AI">
          {tokens.length > 0 ? (
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={tokens}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e1f0" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b6b8a" }} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fontSize: 11, fill: "#6b6b8a" }} />
                <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="tokens" fill="#4f46e5" radius={[4,4,0,0]} name="Tokens" />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        <Card title="Escalaciones a Aranda">
          {escalation && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 4 }}>
              <StatRow label="Total conversaciones" value={escalation.total} />
              <StatRow label="Escaladas" value={escalation.escalated} />
              <div style={{ textAlign: "center", marginTop: 8 }}>
                <div style={{
                  fontSize: 38, fontWeight: 700,
                  color: escalation.rate_pct > 20 ? "#dc2626" : escalation.rate_pct > 10 ? "#d97706" : "#059669",
                }}>
                  {escalation.rate_pct}%
                </div>
                <div style={{ fontSize: 11, color: "#6b6b8a" }}>tasa de escalación</div>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Fila 3 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <Card title="FAQs más consultadas">
          {topFaqs.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {topFaqs.map((f, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "7px 0", borderBottom: "1px solid #f0effe",
                }}>
                  <div style={{
                    width: 22, height: 22, borderRadius: "50%",
                    background: `${C}15`, fontSize: 11, fontWeight: 700,
                    color: C, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>{i+1}</div>
                  <span style={{ flex: 1, fontSize: 12, color: "#374151" }}>
                    {f.question.slice(0,55)}{f.question.length>55?"…":""}
                  </span>
                  <span style={{
                    background: `${C}12`, color: C, fontSize: 10, fontWeight: 600,
                    padding: "2px 8px", borderRadius: 20, whiteSpace: "nowrap",
                  }}>{f.hits}x</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: "#9CA3AF", fontSize: 12, textAlign: "center", marginTop: 20 }}>
              Sin FAQs consultadas aún
            </p>
          )}
        </Card>

        <Card title="Brechas de conocimiento RAG">
          <p style={{ fontSize: 11, color: "#6b6b8a", marginBottom: 12 }}>
            Consultas sin respuesta confiable — requieren documentación en Drive
          </p>
          {gaps.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {gaps.map((g, i) => (
                <div key={i}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 12, color: "#374151", fontWeight: 500 }}>
                      {g.query.slice(0,50)}{g.query.length>50?"…":""}
                    </span>
                    <span style={{ fontSize: 11, color: "#6b6b8a" }}>{g.frequency}x</span>
                  </div>
                  <div style={{ background: "#e2e1f0", borderRadius: 3, height: 4 }}>
                    <div style={{
                      background: g.avg_confidence < 0.4 ? "#dc2626" : g.avg_confidence < 0.6 ? "#d97706" : "#059669",
                      width: `${g.avg_confidence * 100}%`, height: "100%", borderRadius: 3,
                      transition: "width 0.5s ease",
                    }} />
                  </div>
                  <div style={{ fontSize: 10, color: "#9CA3AF", marginTop: 2 }}>
                    Confianza: {(g.avg_confidence*100).toFixed(0)}% · {MOD_NAMES[g.module] || g.module}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: "#059669", fontSize: 12, textAlign: "center", marginTop: 20, fontWeight: 500 }}>
              ✅ Sin brechas detectadas
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}

function KPI({ label, value, icon, color }) {
  return (
    <div style={{
      background: "#fff", borderRadius: 12, padding: "16px 18px",
      border: `1px solid ${color}20`,
      boxShadow: "0 1px 4px rgba(39,33,99,0.06)",
    }}>
      <div style={{
        width: 34, height: 34, borderRadius: 9,
        background: `${color}12`, color,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 18, marginBottom: 10,
      }}>{icon}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: "#1a1a2e" }}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      <div style={{ fontSize: 11, color: "#6b6b8a", marginTop: 3 }}>{label}</div>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div style={{
      background: "#fff", borderRadius: 14, padding: "20px 22px",
      border: "1px solid #e2e1f0",
      boxShadow: "0 1px 4px rgba(39,33,99,0.06)",
    }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, color: C, marginBottom: 14 }}>{title}</h3>
      {children}
    </div>
  );
}

function StatRow({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, paddingBottom: 8, borderBottom: "1px solid #f5f5fa" }}>
      <span style={{ color: "#6b6b8a" }}>{label}</span>
      <span style={{ fontWeight: 600, color: "#1a1a2e" }}>{value}</span>
    </div>
  );
}

function Empty() {
  return <div style={{ height: 100, display: "flex", alignItems: "center", justifyContent: "center", color: "#e2e1f0", fontSize: 13 }}>Sin datos aún</div>;
}

function Loader() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#f5f5fa" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{
          width: 40, height: 40,
          border: `3px solid #e2e1f0`, borderTop: `3px solid ${C}`,
          borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 14px",
        }} />
        <p style={{ color: "#6b6b8a", fontSize: 13 }}>Cargando métricas...</p>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </div>
  );
}

function ErrorScreen({ msg, onRetry }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100vh", gap: 14 }}>
      <span style={{ fontSize: 36 }}>⚠️</span>
      <p style={{ color: "#374151", fontSize: 14, textAlign: "center", maxWidth: 320 }}>{msg}</p>
      <button onClick={onRetry} style={{ padding: "9px 22px", background: C, color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 500 }}>
        Reintentar
      </button>
    </div>
  );
}
