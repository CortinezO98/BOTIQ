import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { dashboardAPI, supportAPI } from "../../services/api";
import { Skeleton, SkeletonCard, SkeletonKpiRow } from "../Skeleton";

const C = "#272163";
const CH = "var(--botiq-heading)"; // texto/headings: sí se adapta a modo oscuro (C se mantiene fijo por los patrones ${C}XX de alpha-transparencia)
const COLORS = ["#272163", "#4f46e5", "#7c3aed", "#0284c7", "#059669", "#d97706", "#dc2626"];

const MOD_NAMES = {
  employee: "Empleados",
  support_rag: "Soporte RAG",
  server_validation: "Servidores",
};

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState({
    metrics: null,
    summary: null,
    byModule: [],
    byDay: [],
    topFaqs: [],
    tokens: [],
    gaps: [],
    escalation: null,
  });

  const moduleChart = useMemo(
    () => data.byModule.map((item, index) => ({
      name: MOD_NAMES[item.module] || item.module,
      value: item.count,
      color: COLORS[index % COLORS.length],
    })),
    [data.byModule]
  );

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [metrics, summary, byModule, byDay, topFaqs, tokens, gaps, escalation] = await Promise.all([
        dashboardAPI.metrics(days),
        dashboardAPI.summary(),
        dashboardAPI.byModule(days),
        dashboardAPI.byDay(days),
        dashboardAPI.topFaqs(8),
        dashboardAPI.tokenConsumption(days),
        dashboardAPI.knowledgeGaps(8),
        dashboardAPI.escalationRate(days),
      ]);

      setData({
        metrics: metrics.data,
        summary: summary.data,
        byModule: byModule.data,
        byDay: byDay.data,
        topFaqs: topFaqs.data,
        tokens: tokens.data,
        gaps: gaps.data,
        escalation: escalation.data,
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Error cargando métricas. Verifica tu sesión de administrador.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  const syncDrive = async () => {
    setSyncing(true);
    try {
      const response = await supportAPI.sync();
      alert(response.data.message || "Sincronización iniciada");
    } catch (err) {
      alert(err.response?.data?.detail || err.message || "Error al sincronizar Google Drive");
    } finally {
      setSyncing(false);
    }
  };

  if (loading) return <Loader />;
  if (error) return <ErrorScreen msg={error} onRetry={load} />;

  const metrics = data.metrics || {};
  const escalation = data.escalation || { total: 0, escalated: 0, rate_pct: 0 };

  return (
    <main className="botiq-container" style={{ display: "grid", gap: 22 }}>
      <header style={headerStyle}>
        <div>
          <div style={eyebrow}>Panel administrativo</div>
          <h1 style={titleStyle}>Dashboard BOTIQ</h1>
          <p style={subtitleStyle}>Métricas en tiempo real — últimos {days} días</p>
        </div>

        <div style={toolbarStyle}>
          <button onClick={syncDrive} disabled={syncing} style={{ ...secondaryButton, opacity: syncing ? 0.65 : 1 }}>
            {syncing ? "⏳ Sincronizando..." : "☁️ Sync Drive"}
          </button>

          <select value={days} onChange={(event) => setDays(Number(event.target.value))} style={selectStyle}>
            <option value={7}>7 días</option>
            <option value={30}>30 días</option>
            <option value={90}>90 días</option>
          </select>

          <button onClick={load} style={primaryButton}>🔄 Actualizar</button>
        </div>
      </header>

      <section style={kpiGridStyle}>
        <KPI label="Conversaciones" value={metrics.total_conversations ?? 0} icon="💬" color="#6d28d9" />
        <KPI label="Mensajes totales" value={metrics.total_messages ?? 0} icon="📩" color="#4f46e5" />
        <KPI label="Tokens Vertex AI" value={(metrics.total_tokens_used ?? 0).toLocaleString()} icon="⚡" color="#7c3aed" />
        <KPI
          label="Costo estimado (COP)"
          value={(() => {
            // Gemini 2.5 Flash: ~$0.30 USD/M tokens entrada + $2.50 USD/M salida
            // Estimación conservadora mezclada ~$0.50 USD/M tokens
            // TRM referencia: $4.200 COP/USD (actualizar en settings o .env si se desea)
            const tokens = metrics.total_tokens_used ?? 0;
            const usd = (tokens / 1_000_000) * 0.50;
            const cop = usd * 4200;
            return cop < 1 ? "< $1" : `$${Math.round(cop).toLocaleString("es-CO")}`;
          })()}
          icon="🇨🇴"
          color="#059669"
          subtitle="estimado"
        />
        <KPI label="Resp. prom. (ms)" value={Math.round(metrics.avg_response_time_ms ?? 0)} icon="⏱️" color="#0284c7" />
        <KPI label="Escalados Aranda" value={metrics.escalations_to_aranda ?? 0} icon="🎫" color="#059669" />
        <KPI label="Brechas RAG" value={metrics.open_knowledge_gaps ?? 0} icon="🧠" color="#d97706" />
      </section>

      <section style={twoColStyle}>
        <Card title="Conversaciones por día">
          {data.byDay.length > 0 ? (
            <ChartBox>
              <LineChart data={data.byDay}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--botiq-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--botiq-muted)" }} tickFormatter={(value) => String(value).slice(5)} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--botiq-muted)" }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="count" stroke={C} strokeWidth={3} dot={{ r: 4, fill: C }} name="Conversaciones" />
              </LineChart>
            </ChartBox>
          ) : <Empty />}
        </Card>

        <Card title="Por módulo">
          {moduleChart.length > 0 ? (
            <div style={{ display: "grid", gap: 14 }}>
              <div style={{ width: "100%", height: 170 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={moduleChart} dataKey="value" cx="50%" cy="50%" innerRadius={45} outerRadius={72} paddingAngle={3}>
                      {moduleChart.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div style={{ display: "grid", gap: 8 }}>
                {moduleChart.map((item) => (
                  <Legend key={item.name} color={item.color} label={item.name} value={item.value} />
                ))}
              </div>
            </div>
          ) : <Empty />}
        </Card>
      </section>

      <section style={twoColStyle}>
        <Card title="Consumo de tokens Vertex AI">
          {data.tokens.length > 0 ? (
            <ChartBox>
              <BarChart data={data.tokens}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--botiq-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--botiq-muted)" }} tickFormatter={(value) => String(value).slice(5)} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--botiq-muted)" }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="tokens" fill="#4f46e5" radius={[8, 8, 0, 0]} name="Tokens" />
              </BarChart>
            </ChartBox>
          ) : <Empty />}
        </Card>

        <Card title="Escalaciones a Aranda">
          <div style={{ display: "grid", gap: 14 }}>
            <StatRow label="Total conversaciones" value={escalation.total} />
            <StatRow label="Escaladas" value={escalation.escalated} />
            <div style={{ textAlign: "center", padding: "14px 0" }}>
              <div style={{ color: escalation.rate_pct > 20 ? "#dc2626" : escalation.rate_pct > 10 ? "#d97706" : "#059669", fontSize: 44, fontWeight: 900, letterSpacing: "-1.6px" }}>
                {escalation.rate_pct}%
              </div>
              <p style={{ margin: 0, color: "var(--botiq-muted)", fontSize: 12 }}>tasa de escalación</p>
            </div>
          </div>
        </Card>
      </section>

      <section style={twoColBottomStyle}>
        <Card title="FAQs más consultadas">
          {data.topFaqs.length > 0 ? (
            <div style={{ display: "grid", gap: 10 }}>
              {data.topFaqs.map((faq, index) => (
                <ListRow key={`${faq.question}-${index}`} index={index + 1} title={faq.question} meta={`${faq.hits} consultas`} />
              ))}
            </div>
          ) : <Empty />}
        </Card>

        <Card title="Brechas de conocimiento">
          {data.gaps.length > 0 ? (
            <div style={{ display: "grid", gap: 10 }}>
              {data.gaps.map((gap, index) => (
                <ListRow key={gap.id || index} index={index + 1} title={gap.query} meta={`${gap.frequency} veces · ${gap.module}`} warn />
              ))}
            </div>
          ) : <Empty text="Sin brechas abiertas" />}
        </Card>
      </section>
    </main>
  );
}

function KPI({ label, value, icon, color, subtitle }) {
  return (
    <article style={{ ...kpiCard, borderTop: `3px solid ${color}` }}>
      <div style={{ ...kpiIcon, color, background: `${color}10` }}>{icon}</div>
      <strong style={kpiValue}>{value}</strong>
      <span style={kpiLabel}>{label}</span>
      {subtitle && <span style={{ fontSize: 10, color: "#9ca3af", marginTop: 2 }}>{subtitle}</span>}
    </article>
  );
}

function Card({ title, children }) {
  return (
    <article className="botiq-card" style={cardStyle}>
      <h2 style={cardTitle}>{title}</h2>
      {children}
    </article>
  );
}

function ChartBox({ children }) {
  return (
    <div style={{ width: "100%", height: 260, minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

function Legend({ color, label, value }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13 }}>
      <span style={{ width: 10, height: 10, borderRadius: "50%", background: color, flexShrink: 0 }} />
      <span style={{ flex: 1, color: "var(--botiq-muted)" }}>{label}</span>
      <strong style={{ color: "var(--botiq-text)" }}>{value}</strong>
    </div>
  );
}

function StatRow({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 14, paddingBottom: 10, borderBottom: "1px solid #f0effe", fontSize: 13 }}>
      <span style={{ color: "var(--botiq-muted)" }}>{label}</span>
      <strong style={{ color: "var(--botiq-text)" }}>{value}</strong>
    </div>
  );
}

function ListRow({ index, title, meta, warn = false }) {
  return (
    <div style={listRowStyle}>
      <span style={{ ...listIndexStyle, background: warn ? "#fffbeb" : "#f0effe", color: warn ? "#92400e" : C }}>{index}</span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={listTitleStyle}>{title}</div>
        <div style={listMetaStyle}>{meta}</div>
      </div>
    </div>
  );
}

function Empty({ text = "Sin datos aún" }) {
  return <div style={{ minHeight: 130, display: "flex", alignItems: "center", justifyContent: "center", color: "#9b96c5", fontSize: 13 }}>{text}</div>;
}

function Loader() {
  return (
    <main className="botiq-container" style={{ display: "grid", gap: 22 }} aria-busy="true" aria-label="Cargando dashboard">
      <div>
        <Skeleton height={12} width={140} style={{ marginBottom: 10 }} />
        <Skeleton height={26} width={260} style={{ marginBottom: 8 }} />
        <Skeleton height={13} width={220} />
      </div>

      <SkeletonKpiRow count={5} />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
        <SkeletonCard lines={4} />
        <SkeletonCard lines={4} />
      </div>
    </main>
  );
}

function ErrorScreen({ msg, onRetry }) {
  return (
    <div style={{ minHeight: "calc(100vh - 64px)", display: "grid", placeItems: "center", padding: 24 }}>
      <div className="botiq-card" style={{ padding: 26, maxWidth: 430, textAlign: "center" }}>
        <div style={{ fontSize: 38, marginBottom: 10 }}>⚠️</div>
        <p style={{ color: "#374151", fontSize: 14, lineHeight: 1.6 }}>{msg}</p>
        <button onClick={onRetry} style={{ ...primaryButton, marginTop: 14 }}>Reintentar</button>
      </div>
    </div>
  );
}

const headerStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 18,
  flexWrap: "wrap",
};

const eyebrow = {
  display: "inline-flex",
  color: CH,
  background: "rgba(39,33,99,0.08)",
  padding: "5px 10px",
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 850,
  marginBottom: 10,
};

const titleStyle = { color: CH, fontSize: "clamp(24px, 3vw, 34px)", margin: 0, letterSpacing: "-1px", fontWeight: 900 };
const subtitleStyle = { color: "var(--botiq-muted)", fontSize: 14, margin: "6px 0 0", lineHeight: 1.5 };

const toolbarStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-end",
  gap: 10,
  flexWrap: "wrap",
};

const primaryButton = {
  border: "none",
  borderRadius: 12,
  background: `linear-gradient(135deg, ${C}, #3a3490)`,
  color: "#fff",
  padding: "11px 16px",
  cursor: "pointer",
  fontWeight: 800,
  boxShadow: "0 8px 22px rgba(39,33,99,0.22)",
};

const secondaryButton = {
  border: "1px solid #d8d6ea",
  borderRadius: 12,
  background: "var(--botiq-card-bg)",
  color: CH,
  padding: "11px 16px",
  cursor: "pointer",
  fontWeight: 800,
};

const selectStyle = {
  border: "1px solid #d8d6ea",
  borderRadius: 12,
  background: "var(--botiq-card-bg)",
  color: CH,
  padding: "11px 12px",
  fontWeight: 750,
  outline: "none",
  minWidth: 120,
};

const kpiGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 16,
};

const kpiCard = {
  background: "var(--botiq-card-bg)",
  border: "1px solid var(--botiq-border)",
  borderRadius: 18,
  padding: 18,
  boxShadow: "0 10px 28px rgba(39,33,99,0.07)",
  minHeight: 132,
  display: "grid",
  alignContent: "space-between",
};

const kpiIcon = { width: 38, height: 38, borderRadius: 12, display: "grid", placeItems: "center", fontSize: 18 };
const kpiValue = { color: "#101026", fontSize: 28, lineHeight: 1, letterSpacing: "-1px" };
const kpiLabel = { color: "var(--botiq-muted)", fontSize: 12, fontWeight: 650 };

const twoColStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 2fr) minmax(320px, 1fr)",
  gap: 18,
};

const twoColBottomStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: 18,
};

const cardStyle = { padding: 20, minWidth: 0, overflow: "hidden" };
const cardTitle = { color: CH, fontSize: 15, margin: "0 0 18px", fontWeight: 900 };
const tooltipStyle = { borderRadius: 12, border: "1px solid var(--botiq-border)", boxShadow: "0 10px 24px rgba(39,33,99,0.12)", fontSize: 12 };

const listRowStyle = { display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: "1px solid #f0effe" };
const listIndexStyle = { width: 28, height: 28, borderRadius: "50%", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 900, flexShrink: 0 };
const listTitleStyle = { color: "var(--botiq-text)", fontSize: 13, fontWeight: 750, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" };
const listMetaStyle = { color: "var(--botiq-muted)", fontSize: 11, marginTop: 3 };

// Responsive rules injected here because this component usa estilos inline.

if (typeof document !== "undefined" && !document.getElementById("botiq-dashboard-responsive-style")) {
  const style = document.createElement("style");
  style.id = "botiq-dashboard-responsive-style";
  style.textContent = `
    @media (max-width: 1120px) {
      .botiq-container section[style*="minmax(0, 2fr)"] { grid-template-columns: 1fr !important; }
    }
    @media (max-width: 820px) {
      .botiq-container section[style*="repeat(2"] { grid-template-columns: 1fr !important; }
    }
  `;
  document.head.appendChild(style);
}



