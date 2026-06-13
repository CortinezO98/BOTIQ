import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import Navbar from "../components/Layout/Navbar";
import { chatAPI, dashboardAPI, downloadBlob, downloadCsvFromRows } from "../services/api";

const C = "#272163";
const PIE_COLORS = ["#272163", "#4f46e5", "#0284c7", "#059669", "#d97706"];

const MODULE_LABELS = {
  employee: "Empleado (FAQ)",
  support_rag: "Base conocimiento",
  server_validation: "Servidores",
};

const PERIODS = [
  { value: 7, label: "Últimos 7 días" },
  { value: 30, label: "Últimos 30 días" },
  { value: 90, label: "Últimos 90 días" },
  { value: 180, label: "Últimos 180 días" },
];

export default function ReportsPage() {
  const [days, setDays] = useState(30);
  const [metrics, setMetrics] = useState(null);
  const [byDay, setByDay] = useState([]);
  const [byModule, setByModule] = useState([]);
  const [tokens, setTokens] = useState([]);
  const [escalation, setEscalation] = useState(null);
  const [topFaqs, setTopFaqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");

  const load = async (period = days) => {
    setLoading(true);
    setError("");
    try {
      const [m, d, mod, t, e, f] = await Promise.all([
        dashboardAPI.metrics(period),
        dashboardAPI.byDay(period),
        dashboardAPI.byModule(period),
        dashboardAPI.tokenConsumption(period),
        dashboardAPI.escalationRate(period),
        dashboardAPI.topFaqs(10),
      ]);
      setMetrics(m.data);
      setByDay(d.data);
      setByModule(mod.data.map((row) => ({ ...row, name: MODULE_LABELS[row.module] || row.module })));
      setTokens(t.data);
      setEscalation(e.data);
      setTopFaqs(f.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error cargando reportería");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(days);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  const stamp = () => new Date().toISOString().slice(0, 10);

  const exportLogsCsv = async () => {
    setExporting(true);
    setError("");
    try {
      const dateFrom = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
      const { data } = await chatAPI.adminConversationLogsExport({ limit: 500, date_from: dateFrom });
      downloadBlob(data, `botiq_reporte_conversaciones_${stamp()}.csv`);
    } catch (err) {
      setError(err.response?.data?.detail || "Error exportando logs");
    } finally {
      setExporting(false);
    }
  };

  const avgPerDay = useMemo(() => {
    if (!byDay.length) return 0;
    return Math.round(byDay.reduce((acc, r) => acc + r.count, 0) / byDay.length);
  }, [byDay]);

  return (
    <div className="botiq-page botiq-admin-page">
      <Navbar currentPage="reports" />

      <main className="botiq-page-main">
        <header
          className="animate__animated animate__fadeIn"
          style={{ marginBottom: 22, display: "flex", flexWrap: "wrap", gap: 14, alignItems: "flex-end", justifyContent: "space-between" }}
        >
          <div style={{ minWidth: 0 }}>
            <h1 style={{ color: C, fontSize: "clamp(22px, 3vw, 28px)", margin: 0, letterSpacing: "-0.5px" }}>
              📈 Reportería
            </h1>
            <p style={{ color: "#6b6b8a", marginTop: 6, fontSize: 13, lineHeight: 1.6, maxWidth: 640 }}>
              Indicadores operativos de BOTIQ: volumen de conversaciones, uso por módulo, consumo de tokens,
              escalamiento a Aranda y exportación de datos para análisis externo.
            </p>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="botiq-form-control" style={{ minHeight: 44, borderRadius: 12, padding: "0 12px", border: "1px solid #e2e1f0", background: "#fff", fontWeight: 700, color: C }}>
              {PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
            <button onClick={() => load(days)} style={secondaryBtn} disabled={loading}>
              {loading ? "Actualizando..." : "↺ Actualizar"}
            </button>
          </div>
        </header>

        {error && <div style={alertStyle}>⚠️ {error}</div>}

        {/* KPIs */}
        <section className="botiq-kpi-row animate__animated animate__fadeInUp">
          <Kpi label="Conversaciones" value={metrics?.total_conversations ?? "—"} icon="💬" />
          <Kpi label="Mensajes" value={metrics?.total_messages ?? "—"} icon="✉️" />
          <Kpi label="Promedio diario" value={avgPerDay} icon="📅" color="#0284c7" />
          <Kpi label="Tokens consumidos" value={metrics ? formatNumber(metrics.total_tokens_used) : "—"} icon="🔋" color="#4f46e5" />
          <Kpi label="Tiempo resp. (ms)" value={metrics?.avg_response_time_ms ?? "—"} icon="⚡" color="#059669" />
          <Kpi label="Escalamiento" value={escalation ? `${escalation.rate_pct}%` : "—"} icon="🎫" color="#d97706" sub={escalation ? `${escalation.escalated} de ${escalation.total}` : ""} />
        </section>

        {/* Gráficas fila 1 */}
        <section className="botiq-reports-grid">
          <ChartCard
            title="Conversaciones por día"
            onExport={() => downloadCsvFromRows(byDay.map((r) => ({ fecha: r.date, conversaciones: r.count })), `botiq_conversaciones_por_dia_${stamp()}.csv`)}
          >
            {byDay.length === 0 ? <Empty /> : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={byDay} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <defs>
                    <linearGradient id="convGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={C} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={C} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e1f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b6b8a" }} />
                  <YAxis tick={{ fontSize: 10, fill: "#6b6b8a" }} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area type="monotone" dataKey="count" name="Conversaciones" stroke={C} strokeWidth={2.5} fill="url(#convGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard
            title="Conversaciones por módulo"
            onExport={() => downloadCsvFromRows(byModule.map((r) => ({ modulo: r.name, conversaciones: r.count })), `botiq_por_modulo_${stamp()}.csv`)}
          >
            {byModule.length === 0 ? <Empty /> : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={byModule} dataKey="count" nameKey="name" cx="50%" cy="50%" innerRadius="48%" outerRadius="78%" paddingAngle={3}>
                    {byModule.map((entry, index) => (
                      <Cell key={entry.module} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
            )}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center", marginTop: 6 }}>
              {byModule.map((entry, index) => (
                <span key={entry.module} style={{ fontSize: 11, color: "#374151", display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{ width: 9, height: 9, borderRadius: 3, background: PIE_COLORS[index % PIE_COLORS.length], display: "inline-block" }} />
                  {entry.name} ({entry.count})
                </span>
              ))}
            </div>
          </ChartCard>
        </section>

        {/* Gráficas fila 2 */}
        <section className="botiq-reports-grid">
          <ChartCard
            title="Consumo de tokens por día"
            onExport={() => downloadCsvFromRows(tokens.map((r) => ({ fecha: r.date, tokens: r.tokens })), `botiq_tokens_por_dia_${stamp()}.csv`)}
          >
            {tokens.length === 0 ? <Empty /> : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={tokens} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e1f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b6b8a" }} />
                  <YAxis tick={{ fontSize: 10, fill: "#6b6b8a" }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="tokens" name="Tokens" fill="#4f46e5" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard
            title="FAQs más consultadas"
            onExport={() => downloadCsvFromRows(topFaqs.map((f) => ({ pregunta: f.question, categoria: f.category, consultas: f.hits })), `botiq_top_faqs_${stamp()}.csv`)}
            scroll
          >
            {topFaqs.length === 0 ? <Empty text="Aún no hay FAQs con consultas registradas." /> : (
              <div style={{ display: "grid", gap: 8 }}>
                {topFaqs.map((faq, index) => (
                  <div key={`${faq.question}-${index}`} style={{ display: "flex", gap: 10, alignItems: "center", background: "#f5f5fa", border: "1px solid #e2e1f0", borderRadius: 10, padding: "9px 12px" }}>
                    <span style={{ color: C, fontWeight: 900, fontSize: 13, width: 22, flexShrink: 0 }}>#{index + 1}</span>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontSize: 12, color: "#1a1a2e", fontWeight: 650, overflowWrap: "anywhere" }}>{faq.question}</div>
                      {faq.category && <div style={{ fontSize: 10, color: "#6b6b8a" }}>{faq.category}</div>}
                    </div>
                    <span style={{ color: "#4f46e5", fontWeight: 850, fontSize: 12, flexShrink: 0 }}>{faq.hits} 👁️</span>
                  </div>
                ))}
              </div>
            )}
          </ChartCard>
        </section>

        {/* Exportaciones */}
        <section className="botiq-card animate__animated animate__fadeInUp" style={{ padding: 18 }}>
          <h3 style={{ color: C, fontSize: 14, margin: "0 0 6px" }}>⬇️ Exportar reportes</h3>
          <p style={{ color: "#6b6b8a", fontSize: 12, margin: "0 0 14px", lineHeight: 1.6 }}>
            Descarga datos en CSV compatibles con Excel para el período seleccionado ({days} días).
            Las exportaciones de logs quedan registradas en auditoría.
          </p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button onClick={exportLogsCsv} disabled={exporting} style={primaryBtn}>
              {exporting ? "Exportando..." : "🧾 Logs de conversaciones (CSV)"}
            </button>
            <button onClick={() => downloadCsvFromRows(byDay.map((r) => ({ fecha: r.date, conversaciones: r.count })), `botiq_conversaciones_por_dia_${stamp()}.csv`)} style={secondaryBtn} disabled={byDay.length === 0}>
              📅 Conversaciones por día
            </button>
            <button onClick={() => downloadCsvFromRows(tokens.map((r) => ({ fecha: r.date, tokens: r.tokens })), `botiq_tokens_por_dia_${stamp()}.csv`)} style={secondaryBtn} disabled={tokens.length === 0}>
              🔋 Consumo de tokens
            </button>
            <button onClick={() => downloadCsvFromRows(topFaqs.map((f) => ({ pregunta: f.question, categoria: f.category, consultas: f.hits })), `botiq_top_faqs_${stamp()}.csv`)} style={secondaryBtn} disabled={topFaqs.length === 0}>
              ❓ Top FAQs
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

/* ---------- Componentes auxiliares ---------- */

function Kpi({ label, value, icon, color = C, sub }) {
  return (
    <article className="botiq-card" style={{ padding: "14px 16px" }}>
      <div style={{ color: "#6b6b8a", fontSize: 11, fontWeight: 750, display: "flex", alignItems: "center", gap: 6 }}>
        <span>{icon}</span> {label}
      </div>
      <div style={{ color, fontSize: 24, fontWeight: 900, marginTop: 4, overflowWrap: "anywhere" }}>{value}</div>
      {sub && <div style={{ color: "#6b6b8a", fontSize: 10, marginTop: 2 }}>{sub}</div>}
    </article>
  );
}

function ChartCard({ title, children, onExport, scroll = false }) {
  return (
    <article className="botiq-card animate__animated animate__fadeInUp" style={{ padding: 16, display: "flex", flexDirection: "column", minWidth: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <h3 style={{ color: C, fontSize: 14, margin: 0 }}>{title}</h3>
        {onExport && (
          <button onClick={onExport} title="Exportar CSV" style={miniBtn}>CSV ⬇️</button>
        )}
      </div>
      <div style={{ height: scroll ? "auto" : 250, maxHeight: scroll ? 290 : undefined, overflowY: scroll ? "auto" : "visible", minWidth: 0 }}>
        {children}
      </div>
    </article>
  );
}

function Empty({ text = "Sin datos para el período seleccionado." }) {
  return (
    <div style={{ height: "100%", minHeight: 120, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: 13 }}>
      {text}
    </div>
  );
}

function formatNumber(n) {
  const num = Number(n || 0);
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}k`;
  return Math.round(num).toString();
}

/* ---------- Estilos ---------- */

const tooltipStyle = {
  background: "#fff",
  border: "1px solid #e2e1f0",
  borderRadius: 10,
  fontSize: 12,
  boxShadow: "0 8px 24px rgba(39,33,99,0.12)",
};

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

const secondaryBtn = {
  border: `1px solid ${C}30`,
  borderRadius: 12,
  background: "#fff",
  color: C,
  padding: "11px 16px",
  cursor: "pointer",
  fontWeight: 800,
  minHeight: 44,
};

const miniBtn = {
  border: `1px solid ${C}25`,
  borderRadius: 8,
  background: `${C}08`,
  color: C,
  padding: "5px 10px",
  cursor: "pointer",
  fontWeight: 800,
  fontSize: 11,
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
