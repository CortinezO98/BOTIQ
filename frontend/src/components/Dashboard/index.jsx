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
  ArrowRight,
  BarChart3,
  Banknote,
  BookOpenCheck,
  Bot,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  CircleGauge,
  Clock3,
  FileQuestion,
  FolderSync,
  Gauge,
  MessageCircleMore,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TicketCheck,
  TrendingUp,
  UsersRound,
  X,
  Zap,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { dashboardAPI, supportAPI } from "../../services/api";
import "./dashboard.css";

const PERIODS = [
  { value: 7, label: "Últimos 7 días" },
  { value: 30, label: "Últimos 30 días" },
  { value: 90, label: "Últimos 90 días" },
];

const MODULE_LABELS = {
  employee: "Empleados",
  support_rag: "Soporte RAG",
  server_validation: "Servidores",
};

const PIE_COLORS = ["#4f46e5", "#7c3aed", "#0284c7", "#059669", "#d97706"];

const AI_COST_USD_PER_1M_TOKENS = Number(
  import.meta.env.VITE_AI_COST_USD_PER_1M_TOKENS || 0.5,
);
const USD_COP_RATE = Number(import.meta.env.VITE_USD_COP_RATE || 4000);

export default function Dashboard() {
  const navigate = useNavigate();
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState(null);
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

  const load = async (period = days) => {
    setLoading(true);
    setMessage(null);

    try {
      const [
        metricsResponse,
        summaryResponse,
        moduleResponse,
        dayResponse,
        faqResponse,
        tokenResponse,
        gapsResponse,
        escalationResponse,
      ] = await Promise.all([
        dashboardAPI.metrics(period),
        dashboardAPI.summary(period),
        dashboardAPI.byModule(period),
        dashboardAPI.byDay(period),
        dashboardAPI.topFaqs(6),
        dashboardAPI.tokenConsumption(period),
        dashboardAPI.knowledgeGaps(period),
        dashboardAPI.escalationRate(period),
      ]);

      setData({
        metrics: metricsResponse.data || null,
        summary: summaryResponse.data || null,
        byModule: Array.isArray(moduleResponse.data)
          ? moduleResponse.data.map((row) => ({
              ...row,
              name: MODULE_LABELS[row.module] || row.module,
            }))
          : [],
        byDay: Array.isArray(dayResponse.data) ? dayResponse.data : [],
        topFaqs: Array.isArray(faqResponse.data) ? faqResponse.data : [],
        tokens: Array.isArray(tokenResponse.data) ? tokenResponse.data : [],
        gaps: Array.isArray(gapsResponse.data) ? gapsResponse.data : [],
        escalation: escalationResponse.data || null,
      });
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible cargar el dashboard.",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const loadInitial = async () => {
      setLoading(true);

      try {
        const [
          metricsResponse,
          summaryResponse,
          moduleResponse,
          dayResponse,
          faqResponse,
          tokenResponse,
          gapsResponse,
          escalationResponse,
        ] = await Promise.all([
          dashboardAPI.metrics(days),
          dashboardAPI.summary(days),
          dashboardAPI.byModule(days),
          dashboardAPI.byDay(days),
          dashboardAPI.topFaqs(6),
          dashboardAPI.tokenConsumption(days),
          dashboardAPI.knowledgeGaps(days),
          dashboardAPI.escalationRate(days),
        ]);

        if (!mounted) return;

        setData({
          metrics: metricsResponse.data || null,
          summary: summaryResponse.data || null,
          byModule: Array.isArray(moduleResponse.data)
            ? moduleResponse.data.map((row) => ({
                ...row,
                name: MODULE_LABELS[row.module] || row.module,
              }))
            : [],
          byDay: Array.isArray(dayResponse.data) ? dayResponse.data : [],
          topFaqs: Array.isArray(faqResponse.data) ? faqResponse.data : [],
          tokens: Array.isArray(tokenResponse.data) ? tokenResponse.data : [],
          gaps: Array.isArray(gapsResponse.data) ? gapsResponse.data : [],
          escalation: escalationResponse.data || null,
        });
      } catch (error) {
        if (mounted) {
          setMessage({
            type: "error",
            text:
              error.response?.data?.detail ||
              "No fue posible cargar el dashboard.",
          });
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    loadInitial();

    return () => {
      mounted = false;
    };
  }, [days]);

  const syncKnowledge = async () => {
    setSyncing(true);
    setMessage(null);

    try {
      const { data: response } = await supportAPI.sync(false);
      setMessage({
        type: "success",
        text:
          response?.message ||
          "La sincronización incremental fue iniciada correctamente.",
      });
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible iniciar la sincronización.",
      });
    } finally {
      setSyncing(false);
    }
  };

  const metrics = data.metrics || {};
  const summary = data.summary || {};
  const escalation = data.escalation || {};

  const totalConversations = Number(
    metrics.total_conversations ?? summary.total_conversations ?? 0,
  );
  const totalMessages = Number(
    metrics.total_messages ?? summary.total_messages ?? 0,
  );
  const totalTokens = Number(
    metrics.total_tokens_used ?? summary.total_tokens_used ?? 0,
  );
  const estimatedCostCop =
    (totalTokens / 1_000_000) *
    AI_COST_USD_PER_1M_TOKENS *
    USD_COP_RATE;
  const avgResponse = Number(
    metrics.avg_response_time_ms ?? summary.avg_response_time_ms ?? 0,
  );
  const escalationRate = Number(escalation.rate_pct || 0);
  const satisfaction = Number(
    metrics.avg_satisfaction ?? summary.avg_satisfaction ?? 0,
  );

  const strongestModule = useMemo(() => {
    if (!data.byModule.length) return null;
    return [...data.byModule].sort(
      (a, b) => Number(b.count || 0) - Number(a.count || 0),
    )[0];
  }, [data.byModule]);

  const peakDay = useMemo(() => {
    if (!data.byDay.length) return null;
    return [...data.byDay].sort(
      (a, b) => Number(b.count || 0) - Number(a.count || 0),
    )[0];
  }, [data.byDay]);

  const unresolvedGaps = data.gaps.filter(
    (gap) => !gap.resolved && gap.status !== "resolved",
  ).length;

  const healthScore = useMemo(() => {
    let score = 100;
    if (escalationRate > 20) score -= 15;
    if (avgResponse > 3000) score -= 15;
    if (unresolvedGaps > 5) score -= 10;
    if (satisfaction && satisfaction < 4) score -= 10;
    return Math.max(35, score);
  }, [escalationRate, avgResponse, unresolvedGaps, satisfaction]);

  const insightCards = [
    {
      icon: TrendingUp,
      tone: "info",
      title: "Pico operativo",
      text: peakDay
        ? `${peakDay.date}: ${peakDay.count} conversaciones`
        : "Sin datos suficientes",
    },
    {
      icon: UsersRound,
      tone: "purple",
      title: "Módulo líder",
      text: strongestModule
        ? `${strongestModule.name}: ${strongestModule.count} sesiones`
        : "Sin datos suficientes",
    },
    {
      icon: TicketCheck,
      tone: escalationRate > 20 ? "warning" : "success",
      title: "Escalamiento",
      text: `${escalationRate}% del total`,
    },
    {
      icon: Zap,
      tone: avgResponse > 3000 ? "warning" : "success",
      title: "Respuesta promedio",
      text: formatMilliseconds(avgResponse),
    },
  ];

  return (
    <main className="botiq-page-main botiq-dashboard-page">
      <header className="botiq-dashboard-heading">
        <div className="botiq-dashboard-heading__main">
          <div className="botiq-dashboard-heading__icon">
            <Gauge size={27} />
          </div>
          <div>
            <span className="botiq-dashboard-heading__eyebrow">
              Vista ejecutiva
            </span>
            <h1>Dashboard</h1>
            <p>
              Supervisa la operación de BOTIQ, el consumo de IA, los módulos
              más usados, las brechas de conocimiento y el nivel de
              escalamiento.
            </p>
          </div>
        </div>

        <div className="botiq-dashboard-heading__actions">
          <label className="botiq-dashboard-period">
            <CalendarDays size={17} />
            <select
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
              aria-label="Período del dashboard"
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
            className="botiq-dashboard-btn botiq-dashboard-btn--secondary"
            onClick={() => load(days)}
            disabled={loading}
          >
            <RefreshCw className={loading ? "spin" : ""} size={17} />
            {loading ? "Actualizando..." : "Recargar"}
          </button>

          <button
            type="button"
            className="botiq-dashboard-btn botiq-dashboard-btn--primary"
            onClick={syncKnowledge}
            disabled={syncing}
          >
            {syncing ? (
              <RefreshCw className="spin" size={17} />
            ) : (
              <FolderSync size={17} />
            )}
            {syncing ? "Sincronizando..." : "Sincronizar conocimiento"}
          </button>
        </div>
      </header>

      {message && (
        <Alert
          type={message.type}
          text={message.text}
          onClose={() => setMessage(null)}
        />
      )}

      <section className="botiq-dashboard-kpis" aria-label="Indicadores principales">
        <MetricCard
          icon={MessageCircleMore}
          label="Conversaciones"
          value={formatNumber(totalConversations)}
          caption={`${formatRatio(totalMessages, totalConversations)} mensajes por sesión`}
          tone="primary"
        />
        <MetricCard
          icon={Activity}
          label="Mensajes"
          value={formatNumber(totalMessages)}
          caption="Interacciones procesadas"
          tone="purple"
        />
        <MetricCard
          icon={Sparkles}
          label="Tokens de IA"
          value={formatNumber(totalTokens)}
          caption={`${formatNumber(
            Math.round(totalTokens / Math.max(totalConversations, 1)),
          )} por conversación`}
          tone="info"
        />
        <MetricCard
          icon={Banknote}
          label="Costo IA estimado"
          value={formatCop(estimatedCostCop)}
          caption={`Tarifa configurada: USD ${AI_COST_USD_PER_1M_TOKENS.toFixed(
            2,
          )} por millón · TRM ${formatNumber(USD_COP_RATE)}`}
          tone="success"
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
          caption={`${escalation.escalated || 0} casos escalados`}
          tone={escalationRate > 20 ? "warning" : "success"}
        />
        <MetricCard
          icon={FileQuestion}
          label="Brechas abiertas"
          value={unresolvedGaps}
          caption="Consultas por convertir en conocimiento"
          tone={unresolvedGaps > 5 ? "danger" : "neutral"}
        />
      </section>

      <section className="botiq-dashboard-overview">
        <article className="botiq-dashboard-health">
          <header>
            <div>
              <span>Salud operativa</span>
              <h2>Estado general de BOTIQ</h2>
            </div>
            <CircleGauge size={24} />
          </header>

          <div className="botiq-dashboard-health__body">
            <div
              className="botiq-dashboard-health-ring"
              style={{ "--dashboard-progress": `${healthScore * 3.6}deg` }}
            >
              <div>
                <strong>{healthScore}%</strong>
                <span>{healthScore >= 80 ? "Estable" : "Atención"}</span>
              </div>
            </div>

            <div className="botiq-dashboard-health__items">
              <HealthItem
                label="Respuesta promedio"
                value={formatMilliseconds(avgResponse)}
                good={avgResponse <= 3000}
              />
              <HealthItem
                label="Escalamiento"
                value={`${escalationRate}%`}
                good={escalationRate <= 20}
              />
              <HealthItem
                label="Brechas abiertas"
                value={unresolvedGaps}
                good={unresolvedGaps <= 5}
              />
              <HealthItem
                label="Satisfacción"
                value={satisfaction ? satisfaction.toFixed(1) : "N/D"}
                good={!satisfaction || satisfaction >= 4}
              />
            </div>
          </div>
        </article>

        <article className="botiq-dashboard-insights">
          <header>
            <div>
              <span>Lectura rápida</span>
              <h2>Hallazgos del período</h2>
            </div>
            <Sparkles size={22} />
          </header>

          <div className="botiq-dashboard-insights__grid">
            {insightCards.map((item) => (
              <InsightCard key={item.title} {...item} />
            ))}
          </div>
        </article>
      </section>

      <section className="botiq-dashboard-grid">
        <DashboardCard
          title="Conversaciones por día"
          description="Comportamiento diario del uso de BOTIQ."
          icon={TrendingUp}
          onOpen={() => navigate("/dashboard/reports")}
        >
          {loading ? (
            <ChartSkeleton />
          ) : data.byDay.length === 0 ? (
            <EmptyState />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={data.byDay}
                margin={{ top: 8, right: 12, left: -12, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="dashboardArea" x1="0" y1="0" x2="0" y2="1">
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
                  strokeWidth={2.4}
                  fill="url(#dashboardArea)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </DashboardCard>

        <DashboardCard
          title="Distribución por módulo"
          description="Participación de cada frente funcional."
          icon={BarChart3}
          onOpen={() => navigate("/dashboard/reports")}
        >
          {loading ? (
            <ChartSkeleton />
          ) : data.byModule.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="botiq-dashboard-pie-layout">
              <div className="botiq-dashboard-pie">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data.byModule}
                      dataKey="count"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius="54%"
                      outerRadius="80%"
                      paddingAngle={3}
                    >
                      {data.byModule.map((entry, index) => (
                        <Cell
                          key={entry.module}
                          fill={PIE_COLORS[index % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>

                <div className="botiq-dashboard-pie__center">
                  <strong>{formatNumber(totalConversations)}</strong>
                  <span>sesiones</span>
                </div>
              </div>

              <div className="botiq-dashboard-legend">
                {data.byModule.map((entry, index) => (
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
        </DashboardCard>
      </section>

      <section className="botiq-dashboard-grid">
        <DashboardCard
          title="Consumo de tokens"
          description="Demanda diaria de capacidad de IA."
          icon={Sparkles}
          onOpen={() => navigate("/dashboard/reports")}
        >
          {loading ? (
            <ChartSkeleton />
          ) : data.tokens.length === 0 ? (
            <EmptyState />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.tokens}
                margin={{ top: 8, right: 12, left: -6, bottom: 0 }}
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
        </DashboardCard>

        <DashboardCard
          title="Brechas de conocimiento"
          description="Preguntas no cubiertas que requieren gestión."
          icon={FileQuestion}
          onOpen={() => navigate("/dashboard/knowledge-base")}
          contentClassName="is-scroll"
        >
          {loading ? (
            <ListSkeleton />
          ) : data.gaps.length === 0 ? (
            <EmptyState text="No hay brechas registradas." />
          ) : (
            <GapList gaps={data.gaps.slice(0, 8)} />
          )}
        </DashboardCard>
      </section>

      <section className="botiq-dashboard-bottom">
        <article className="botiq-dashboard-ranking-card">
          <header>
            <div>
              <span>Contenido más usado</span>
              <h2>FAQs más consultadas</h2>
            </div>
            <button
              type="button"
              onClick={() => navigate("/dashboard/faqs")}
            >
              Ver FAQs <ArrowRight size={15} />
            </button>
          </header>

          {loading ? (
            <ListSkeleton />
          ) : data.topFaqs.length === 0 ? (
            <EmptyState text="Aún no hay FAQs con consultas." />
          ) : (
            <FaqList faqs={data.topFaqs} />
          )}
        </article>

        <article className="botiq-dashboard-shortcuts">
          <header>
            <div>
              <span>Accesos rápidos</span>
              <h2>Gestión frecuente</h2>
            </div>
          </header>

          <div>
            <Shortcut
              icon={MessageCircleMore}
              title="Logs de conversaciones"
              text="Revisa trazabilidad, tickets y sesiones."
              onClick={() => navigate("/dashboard/conversation-logs")}
            />
            <Shortcut
              icon={BookOpenCheck}
              title="Base de conocimiento"
              text="Gestiona documentos e indexación RAG."
              onClick={() => navigate("/dashboard/knowledge-base")}
            />
            <Shortcut
              icon={UsersRound}
              title="Usuarios"
              text="Administra roles, estados y MFA."
              onClick={() => navigate("/dashboard/users")}
            />
            <Shortcut
              icon={ShieldAlert}
              title="Gobierno IA"
              text="Monitorea controles y trazabilidad."
              onClick={() => navigate("/dashboard/governance")}
            />
          </div>
        </article>
      </section>
    </main>
  );
}

function MetricCard({ icon: Icon, label, value, caption, tone }) {
  return (
    <article className={`botiq-dashboard-kpi tone-${tone}`}>
      <div className="botiq-dashboard-kpi__icon">
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

function Alert({ type, text, onClose }) {
  const Icon = type === "success" ? CheckCircle2 : AlertCircle;

  return (
    <div
      className={`botiq-dashboard-alert is-${type}`}
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

function HealthItem({ label, value, good }) {
  return (
    <div>
      <span>{label}</span>
      <strong className={good ? "is-good" : "is-warning"}>{value}</strong>
    </div>
  );
}

function InsightCard({ icon: Icon, title, text, tone }) {
  return (
    <article className={`botiq-dashboard-insight tone-${tone}`}>
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

function DashboardCard({
  title,
  description,
  icon: Icon,
  onOpen,
  children,
  contentClassName = "",
}) {
  return (
    <article className="botiq-dashboard-card">
      <header>
        <div className="botiq-dashboard-card__title">
          <div>
            <Icon size={18} />
          </div>
          <section>
            <h2>{title}</h2>
            <p>{description}</p>
          </section>
        </div>

        <button type="button" onClick={onOpen}>
          Ver detalle <ArrowRight size={14} />
        </button>
      </header>

      <div
        className={`botiq-dashboard-card__body ${contentClassName}`.trim()}
      >
        {children}
      </div>
    </article>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="botiq-dashboard-tooltip">
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

function GapList({ gaps }) {
  return (
    <div className="botiq-dashboard-gap-list">
      {gaps.map((gap, index) => (
        <article key={gap.id || `${gap.question}-${index}`}>
          <div>#{index + 1}</div>
          <section>
            <h3>{gap.question || gap.query || "Consulta sin título"}</h3>
            <p>
              {gap.category || gap.module || "Sin categoría"} ·{" "}
              {gap.frequency || gap.hits || 1} ocurrencia(s)
            </p>
          </section>
          <span
            className={
              gap.resolved || gap.status === "resolved"
                ? "is-resolved"
                : "is-open"
            }
          >
            {gap.resolved || gap.status === "resolved"
              ? "Resuelta"
              : "Pendiente"}
          </span>
        </article>
      ))}
    </div>
  );
}

function FaqList({ faqs }) {
  const maxHits = Math.max(...faqs.map((faq) => Number(faq.hits || 0)), 1);

  return (
    <div className="botiq-dashboard-faq-list">
      {faqs.map((faq, index) => (
        <article key={`${faq.question}-${index}`}>
          <div>#{index + 1}</div>
          <section>
            <header>
              <div>
                <h3>{faq.question}</h3>
                <span>{faq.category || "Sin categoría"}</span>
              </div>
              <strong>{faq.hits} consultas</strong>
            </header>
            <div>
              <i
                style={{
                  width: `${Math.max(
                    6,
                    (Number(faq.hits || 0) / maxHits) * 100,
                  )}%`,
                }}
              />
            </div>
          </section>
        </article>
      ))}
    </div>
  );
}

function Shortcut({ icon: Icon, title, text, onClick }) {
  return (
    <button type="button" className="botiq-dashboard-shortcut" onClick={onClick}>
      <div>
        <Icon size={20} />
      </div>
      <section>
        <h3>{title}</h3>
        <p>{text}</p>
      </section>
      <ArrowRight size={16} />
    </button>
  );
}

function EmptyState({ text = "Sin datos para el período seleccionado." }) {
  return (
    <div className="botiq-dashboard-empty">
      <Bot size={29} />
      <h3>No hay información disponible</h3>
      <p>{text}</p>
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="botiq-dashboard-chart-skeleton">
      <span />
      <div>
        {Array.from({ length: 10 }).map((_, index) => (
          <i key={index} style={{ height: `${25 + ((index * 17) % 65)}%` }} />
        ))}
      </div>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="botiq-dashboard-list-skeleton">
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

  if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M`;
  if (number >= 1_000) return `${(number / 1_000).toFixed(1)}k`;
  return Math.round(number).toString();
}

function formatCop(value) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
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
