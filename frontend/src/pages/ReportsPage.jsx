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
import {
  Activity,
  AlertCircle,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  CircleGauge,
  Clock3,
  Download,
  FileQuestion,
  Gauge,
  MessageCircleMore,
  RefreshCw,
  Sparkles,
  TicketCheck,
  TrendingUp,
  UsersRound,
  X,
  Zap,
} from "lucide-react";

import AppShell from "../components/Layout/AppShell";
import {
  chatAPI,
  dashboardAPI,
  downloadBlob,
  downloadCsvFromRows,
} from "../services/api";
import "../components/Reports/reports.css";

const MODULE_LABELS = {
  employee: "Empleado (FAQ)",
  support_rag: "Base de conocimiento",
  server_validation: "Servidores",
};

const PERIODS = [
  { value: 7, label: "Últimos 7 días" },
  { value: 30, label: "Últimos 30 días" },
  { value: 90, label: "Últimos 90 días" },
  { value: 180, label: "Últimos 180 días" },
];

const PIE_COLORS = ["#4f46e5", "#7c3aed", "#0284c7", "#059669", "#d97706"];

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
  const [message, setMessage] = useState(null);

  const load = async (period = days) => {
    setLoading(true);
    setMessage(null);

    try {
      const [metricsResponse, dayResponse, moduleResponse, tokenResponse, escalationResponse, faqResponse] =
        await Promise.all([
          dashboardAPI.metrics(period),
          dashboardAPI.byDay(period),
          dashboardAPI.byModule(period),
          dashboardAPI.tokenConsumption(period),
          dashboardAPI.escalationRate(period),
          dashboardAPI.topFaqs(10),
        ]);

      setMetrics(metricsResponse.data || null);
      setByDay(Array.isArray(dayResponse.data) ? dayResponse.data : []);
      setByModule(
        Array.isArray(moduleResponse.data)
          ? moduleResponse.data.map((row) => ({
              ...row,
              name: MODULE_LABELS[row.module] || row.module,
            }))
          : [],
      );
      setTokens(Array.isArray(tokenResponse.data) ? tokenResponse.data : []);
      setEscalation(escalationResponse.data || null);
      setTopFaqs(Array.isArray(faqResponse.data) ? faqResponse.data : []);
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible cargar la reportería.",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const loadPeriod = async () => {
      setLoading(true);
      setMessage(null);

      try {
        const [
          metricsResponse,
          dayResponse,
          moduleResponse,
          tokenResponse,
          escalationResponse,
          faqResponse,
        ] = await Promise.all([
          dashboardAPI.metrics(days),
          dashboardAPI.byDay(days),
          dashboardAPI.byModule(days),
          dashboardAPI.tokenConsumption(days),
          dashboardAPI.escalationRate(days),
          dashboardAPI.topFaqs(10),
        ]);

        if (!mounted) return;

        setMetrics(metricsResponse.data || null);
        setByDay(Array.isArray(dayResponse.data) ? dayResponse.data : []);
        setByModule(
          Array.isArray(moduleResponse.data)
            ? moduleResponse.data.map((row) => ({
                ...row,
                name: MODULE_LABELS[row.module] || row.module,
              }))
            : [],
        );
        setTokens(Array.isArray(tokenResponse.data) ? tokenResponse.data : []);
        setEscalation(escalationResponse.data || null);
        setTopFaqs(Array.isArray(faqResponse.data) ? faqResponse.data : []);
      } catch (error) {
        if (mounted) {
          setMessage({
            type: "error",
            text:
              error.response?.data?.detail ||
              "No fue posible cargar la reportería.",
          });
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    loadPeriod();

    return () => {
      mounted = false;
    };
  }, [days]);

  const stamp = () => new Date().toISOString().slice(0, 10);

  const exportLogsCsv = async () => {
    setExporting(true);
    setMessage(null);

    try {
      const dateFrom = new Date(
        Date.now() - days * 24 * 60 * 60 * 1000,
      )
        .toISOString()
        .slice(0, 10);

      const { data } = await chatAPI.adminConversationLogsExport({
        limit: 500,
        date_from: dateFrom,
      });

      downloadBlob(data, `botiq_reporte_conversaciones_${stamp()}.csv`);
      setMessage({
        type: "success",
        text: "El reporte de conversaciones fue exportado correctamente.",
      });
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible exportar los logs.",
      });
    } finally {
      setExporting(false);
    }
  };

  const avgPerDay = useMemo(() => {
    if (!byDay.length) return 0;

    return Math.round(
      byDay.reduce((total, row) => total + Number(row.count || 0), 0) /
        byDay.length,
    );
  }, [byDay]);

  const totalConversations = Number(metrics?.total_conversations || 0);
  const totalMessages = Number(metrics?.total_messages || 0);
  const totalTokens = Number(metrics?.total_tokens_used || 0);
  const avgResponse = Number(metrics?.avg_response_time_ms || 0);
  const escalationRate = Number(escalation?.rate_pct || 0);

  const strongestModule = useMemo(() => {
    if (!byModule.length) return null;
    return [...byModule].sort(
      (a, b) => Number(b.count || 0) - Number(a.count || 0),
    )[0];
  }, [byModule]);

  const highestDay = useMemo(() => {
    if (!byDay.length) return null;
    return [...byDay].sort(
      (a, b) => Number(b.count || 0) - Number(a.count || 0),
    )[0];
  }, [byDay]);

  const insights = useMemo(() => {
    const items = [];

    if (highestDay) {
      items.push({
        tone: "info",
        icon: TrendingUp,
        title: "Pico de conversaciones",
        text: `${highestDay.date}: ${highestDay.count} conversaciones.`,
      });
    }

    if (strongestModule) {
      items.push({
        tone: "purple",
        icon: UsersRound,
        title: "Módulo más utilizado",
        text: `${strongestModule.name}: ${strongestModule.count} conversaciones.`,
      });
    }

    items.push({
      tone: escalationRate > 20 ? "warning" : "success",
      icon: TicketCheck,
      title: "Nivel de escalamiento",
      text: `${escalationRate}% de las conversaciones fueron escaladas.`,
    });

    items.push({
      tone: avgResponse > 3000 ? "warning" : "success",
      icon: Zap,
      title: "Tiempo de respuesta",
      text: `${formatMilliseconds(avgResponse)} de promedio.`,
    });

    return items;
  }, [highestDay, strongestModule, escalationRate, avgResponse]);

  const periodLabel =
    PERIODS.find((period) => period.value === days)?.label || `${days} días`;

  return (
    <AppShell currentPage="reports">
      <main className="botiq-page-main botiq-reports-page">
        <PageHeading
          days={days}
          loading={loading}
          onDaysChange={setDays}
          onRefresh={() => load(days)}
        />

        {message && (
          <Alert
            type={message.type}
            text={message.text}
            onClose={() => setMessage(null)}
          />
        )}

        <section className="botiq-reports-kpis" aria-label="Indicadores de reportería">
          <MetricCard
            icon={MessageCircleMore}
            label="Conversaciones"
            value={formatNumber(totalConversations)}
            caption={`${avgPerDay} promedio diario`}
            tone="primary"
          />
          <MetricCard
            icon={Activity}
            label="Mensajes"
            value={formatNumber(totalMessages)}
            caption={`${formatRatio(totalMessages, totalConversations)} por conversación`}
            tone="purple"
          />
          <MetricCard
            icon={Sparkles}
            label="Tokens consumidos"
            value={formatNumber(totalTokens)}
            caption={`${formatNumber(Math.round(totalTokens / Math.max(totalConversations, 1)))} por conversación`}
            tone="info"
          />
          <MetricCard
            icon={Clock3}
            label="Tiempo de respuesta"
            value={formatMilliseconds(avgResponse)}
            caption={avgResponse <= 3000 ? "Dentro del objetivo" : "Requiere seguimiento"}
            tone={avgResponse <= 3000 ? "success" : "warning"}
          />
          <MetricCard
            icon={TicketCheck}
            label="Escalamiento"
            value={`${escalationRate}%`}
            caption={
              escalation
                ? `${escalation.escalated || 0} de ${escalation.total || 0}`
                : "Sin datos"
            }
            tone={escalationRate > 20 ? "warning" : "success"}
          />
          <MetricCard
            icon={CalendarDays}
            label="Período analizado"
            value={`${days} días`}
            caption={periodLabel}
            tone="neutral"
          />
        </section>

        <section className="botiq-reports-insights" aria-label="Hallazgos del período">
          <header>
            <div>
              <span>Análisis ejecutivo</span>
              <h2>Hallazgos principales</h2>
            </div>
            <CircleGauge size={24} />
          </header>

          <div className="botiq-reports-insights__grid">
            {insights.map((insight) => (
              <InsightCard key={insight.title} {...insight} />
            ))}
          </div>
        </section>

        <section className="botiq-reports-grid">
          <ReportCard
            title="Conversaciones por día"
            description="Evolución diaria del volumen de sesiones."
            icon={TrendingUp}
            onExport={() =>
              downloadCsvFromRows(
                byDay.map((row) => ({
                  fecha: row.date,
                  conversaciones: row.count,
                })),
                `botiq_conversaciones_por_dia_${stamp()}.csv`,
              )
            }
          >
            {loading ? (
              <ChartSkeleton />
            ) : byDay.length === 0 ? (
              <EmptyState />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={byDay}
                  margin={{ top: 10, right: 12, left: -12, bottom: 0 }}
                >
                  <defs>
                    <linearGradient
                      id="reportsConversationGradient"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop offset="0%" stopColor="#4f46e5" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#4f46e5" stopOpacity={0.03} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--botiq-border)"
                  />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: "var(--botiq-muted)" }}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 10, fill: "var(--botiq-muted)" }}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="count"
                    name="Conversaciones"
                    stroke="#4f46e5"
                    strokeWidth={2.5}
                    fill="url(#reportsConversationGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </ReportCard>

          <ReportCard
            title="Distribución por módulo"
            description="Participación de cada fuente funcional."
            icon={BarChart3}
            onExport={() =>
              downloadCsvFromRows(
                byModule.map((row) => ({
                  modulo: row.name,
                  conversaciones: row.count,
                })),
                `botiq_por_modulo_${stamp()}.csv`,
              )
            }
          >
            {loading ? (
              <ChartSkeleton />
            ) : byModule.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="botiq-reports-pie-layout">
                <div className="botiq-reports-pie">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={byModule}
                        dataKey="count"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius="54%"
                        outerRadius="80%"
                        paddingAngle={3}
                      >
                        {byModule.map((entry, index) => (
                          <Cell
                            key={entry.module}
                            fill={PIE_COLORS[index % PIE_COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip content={<ChartTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>

                  <div className="botiq-reports-pie__center">
                    <strong>{formatNumber(totalConversations)}</strong>
                    <span>conversaciones</span>
                  </div>
                </div>

                <div className="botiq-reports-legend">
                  {byModule.map((entry, index) => (
                    <div key={entry.module}>
                      <i
                        style={{
                          background: PIE_COLORS[index % PIE_COLORS.length],
                        }}
                      />
                      <span>{entry.name}</span>
                      <strong>{entry.count}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </ReportCard>
        </section>

        <section className="botiq-reports-grid">
          <ReportCard
            title="Consumo de tokens"
            description="Demanda diaria de capacidad de modelos de IA."
            icon={Sparkles}
            onExport={() =>
              downloadCsvFromRows(
                tokens.map((row) => ({
                  fecha: row.date,
                  tokens: row.tokens,
                })),
                `botiq_tokens_por_dia_${stamp()}.csv`,
              )
            }
          >
            {loading ? (
              <ChartSkeleton />
            ) : tokens.length === 0 ? (
              <EmptyState />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={tokens}
                  margin={{ top: 10, right: 12, left: -6, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--botiq-border)"
                  />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: "var(--botiq-muted)" }}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "var(--botiq-muted)" }}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar
                    dataKey="tokens"
                    name="Tokens"
                    fill="#7c3aed"
                    radius={[7, 7, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ReportCard>

          <ReportCard
            title="FAQs más consultadas"
            description="Preguntas con mayor demanda durante la operación."
            icon={FileQuestion}
            onExport={() =>
              downloadCsvFromRows(
                topFaqs.map((faq) => ({
                  pregunta: faq.question,
                  categoria: faq.category,
                  consultas: faq.hits,
                })),
                `botiq_top_faqs_${stamp()}.csv`,
              )
            }
            contentClassName="botiq-reports-card__body--scroll"
          >
            {loading ? (
              <RankingSkeleton />
            ) : topFaqs.length === 0 ? (
              <EmptyState text="Todavía no hay FAQs con consultas registradas." />
            ) : (
              <FaqRanking faqs={topFaqs} />
            )}
          </ReportCard>
        </section>

        <section className="botiq-reports-export">
          <div className="botiq-reports-export__content">
            <div className="botiq-reports-export__icon">
              <Download size={26} />
            </div>
            <div>
              <span>Exportación y análisis externo</span>
              <h2>Descargar información del período</h2>
              <p>
                Genera archivos CSV compatibles con Excel. La exportación de
                conversaciones conserva los filtros temporales del período
                seleccionado y queda registrada en auditoría.
              </p>
            </div>
          </div>

          <div className="botiq-reports-export__actions">
            <ExportButton
              primary
              icon={Download}
              label={exporting ? "Exportando logs..." : "Logs de conversaciones"}
              onClick={exportLogsCsv}
              disabled={exporting}
              loading={exporting}
            />
            <ExportButton
              icon={CalendarDays}
              label="Conversaciones por día"
              onClick={() =>
                downloadCsvFromRows(
                  byDay.map((row) => ({
                    fecha: row.date,
                    conversaciones: row.count,
                  })),
                  `botiq_conversaciones_por_dia_${stamp()}.csv`,
                )
              }
              disabled={!byDay.length}
            />
            <ExportButton
              icon={Sparkles}
              label="Consumo de tokens"
              onClick={() =>
                downloadCsvFromRows(
                  tokens.map((row) => ({
                    fecha: row.date,
                    tokens: row.tokens,
                  })),
                  `botiq_tokens_por_dia_${stamp()}.csv`,
                )
              }
              disabled={!tokens.length}
            />
            <ExportButton
              icon={FileQuestion}
              label="Top FAQs"
              onClick={() =>
                downloadCsvFromRows(
                  topFaqs.map((faq) => ({
                    pregunta: faq.question,
                    categoria: faq.category,
                    consultas: faq.hits,
                  })),
                  `botiq_top_faqs_${stamp()}.csv`,
                )
              }
              disabled={!topFaqs.length}
            />
          </div>
        </section>
      </main>
    </AppShell>
  );
}

function PageHeading({ days, loading, onDaysChange, onRefresh }) {
  return (
    <header className="botiq-reports-heading">
      <div className="botiq-reports-heading__main">
        <div className="botiq-reports-heading__icon" aria-hidden="true">
          <BarChart3 size={27} />
        </div>

        <div>
          <span className="botiq-reports-heading__eyebrow">Analítica</span>
          <h1>Reportería</h1>
          <p>
            Analiza volumen, módulos, consumo de IA, tiempos de respuesta,
            FAQs y escalamiento a Aranda.
          </p>
        </div>
      </div>

      <div className="botiq-reports-heading__actions">
        <label className="botiq-reports-period">
          <CalendarDays size={17} />
          <select
            value={days}
            onChange={(event) => onDaysChange(Number(event.target.value))}
            aria-label="Período del reporte"
          >
            {PERIODS.map((period) => (
              <option key={period.value} value={period.value}>
                {period.label}
              </option>
            ))}
          </select>
          <ChevronDown size={15} />
        </label>

        <button
          type="button"
          className="botiq-reports-btn botiq-reports-btn--primary"
          onClick={onRefresh}
          disabled={loading}
        >
          <RefreshCw className={loading ? "spin" : ""} size={17} />
          {loading ? "Actualizando..." : "Recargar"}
        </button>
      </div>
    </header>
  );
}

function MetricCard({ icon: Icon, label, value, caption, tone }) {
  return (
    <article className={`botiq-reports-kpi botiq-reports-kpi--${tone}`}>
      <div className="botiq-reports-kpi__icon">
        <Icon size={21} />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <span>{caption}</span>
      </div>
    </article>
  );
}

function InsightCard({ icon: Icon, title, text, tone }) {
  return (
    <article className={`botiq-reports-insight botiq-reports-insight--${tone}`}>
      <div>
        <Icon size={18} />
      </div>
      <section>
        <h3>{title}</h3>
        <p>{text}</p>
      </section>
    </article>
  );
}

function ReportCard({
  title,
  description,
  icon: Icon,
  children,
  onExport,
  contentClassName = "",
}) {
  return (
    <article className="botiq-reports-card">
      <header>
        <div className="botiq-reports-card__title">
          <div>
            <Icon size={18} />
          </div>
          <section>
            <h2>{title}</h2>
            <p>{description}</p>
          </section>
        </div>

        <button
          type="button"
          className="botiq-reports-card__export"
          onClick={onExport}
          title="Exportar CSV"
          aria-label={`Exportar ${title} en CSV`}
        >
          <Download size={15} />
          CSV
        </button>
      </header>

      <div className={`botiq-reports-card__body ${contentClassName}`.trim()}>
        {children}
      </div>
    </article>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="botiq-reports-tooltip">
      {label && <strong>{label}</strong>}
      {payload.map((entry) => (
        <span key={`${entry.name}-${entry.value}`}>
          <i style={{ background: entry.color || entry.fill }} />
          {entry.name}: {formatNumber(entry.value)}
        </span>
      ))}
    </div>
  );
}

function FaqRanking({ faqs }) {
  const maxHits = Math.max(...faqs.map((faq) => Number(faq.hits || 0)), 1);

  return (
    <div className="botiq-reports-ranking">
      {faqs.map((faq, index) => (
        <article key={`${faq.question}-${index}`}>
          <div className="botiq-reports-ranking__number">#{index + 1}</div>

          <div className="botiq-reports-ranking__content">
            <header>
              <div>
                <h3>{faq.question}</h3>
                <span>{faq.category || "Sin categoría"}</span>
              </div>
              <strong>{faq.hits} consultas</strong>
            </header>

            <div className="botiq-reports-ranking__bar">
              <i
                style={{
                  width: `${Math.max(
                    6,
                    (Number(faq.hits || 0) / maxHits) * 100,
                  )}%`,
                }}
              />
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function ExportButton({
  icon: Icon,
  label,
  onClick,
  disabled,
  primary = false,
  loading = false,
}) {
  return (
    <button
      type="button"
      className={`botiq-reports-btn ${
        primary
          ? "botiq-reports-btn--primary"
          : "botiq-reports-btn--secondary"
      }`}
      onClick={onClick}
      disabled={disabled}
    >
      {loading ? <RefreshCw className="spin" size={17} /> : <Icon size={17} />}
      {label}
    </button>
  );
}

function Alert({ type, text, onClose }) {
  const Icon = type === "success" ? CheckCircle2 : AlertCircle;

  return (
    <div
      className={`botiq-reports-alert botiq-reports-alert--${type}`}
      role={type === "error" ? "alert" : "status"}
    >
      <Icon size={18} />
      <p>{text}</p>
      <button type="button" onClick={onClose} aria-label="Cerrar mensaje">
        <X size={16} />
      </button>
    </div>
  );
}

function EmptyState({ text = "Sin datos para el período seleccionado." }) {
  return (
    <div className="botiq-reports-empty">
      <Gauge size={29} />
      <h3>No hay información disponible</h3>
      <p>{text}</p>
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="botiq-reports-chart-skeleton">
      <span />
      <div>
        {Array.from({ length: 10 }).map((_, index) => (
          <i key={index} style={{ height: `${25 + ((index * 17) % 65)}%` }} />
        ))}
      </div>
    </div>
  );
}

function RankingSkeleton() {
  return (
    <div className="botiq-reports-ranking-skeleton">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index}>
          <span />
          <section>
            <i />
            <i />
          </section>
        </div>
      ))}
    </div>
  );
}

function formatNumber(value) {
  const number = Number(value || 0);

  if (number >= 1_000_000) {
    return `${(number / 1_000_000).toFixed(1)}M`;
  }

  if (number >= 1_000) {
    return `${(number / 1_000).toFixed(1)}k`;
  }

  return Math.round(number).toString();
}

function formatMilliseconds(value) {
  const milliseconds = Number(value || 0);

  if (!milliseconds) return "0 ms";
  if (milliseconds >= 1000) return `${(milliseconds / 1000).toFixed(1)} s`;
  return `${Math.round(milliseconds)} ms`;
}

function formatRatio(total, divisor) {
  if (!divisor) return "0";
  return (total / divisor).toFixed(1);
}
