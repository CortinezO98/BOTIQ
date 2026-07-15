import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  BadgeCheck,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleGauge,
  Clock3,
  ExternalLink,
  Eye,
  FileQuestion,
  Filter,
  Gauge,
  MessageSquareWarning,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  ThumbsUp,
  UsersRound,
  X,
  XCircle,
} from "lucide-react";

import AppShell from "../components/Layout/AppShell";
import { adminAPI } from "../services/api";
import "../components/Governance/governance.css";

const INCIDENT_FILTERS = [
  { value: "open", label: "Abiertas" },
  { value: "acknowledged", label: "Reconocidas" },
  { value: "resolved", label: "Resueltas" },
  { value: "all", label: "Todas" },
];

const AI_FILTERS = [
  { value: "pending", label: "Pendientes" },
  { value: "approved", label: "Aprobadas" },
  { value: "rejected", label: "Rechazadas" },
];

const SEVERITY_LABELS = {
  critical: "Crítica",
  high: "Alta",
  medium: "Media",
  low: "Baja",
};

const STATUS_LABELS = {
  open: "Abierta",
  acknowledged: "Reconocida",
  resolved: "Resuelta",
  pending: "Pendiente",
  approved: "Aprobada",
  rejected: "Rechazada",
};

export default function GovernancePage() {
  const [feedback, setFeedback] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [incidentStatus, setIncidentStatus] = useState("open");
  const [aiItems, setAiItems] = useState([]);
  const [aiStatus, setAiStatus] = useState("pending");
  const [aiSearch, setAiSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState("");
  const [message, setMessage] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);

  const loadAll = async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    setMessage(null);

    try {
      const [feedbackResponse, incidentsResponse, aiResponse] = await Promise.all([
        adminAPI.feedbackSummary(10),
        adminAPI.listIncidentAlerts(incidentStatus, 50),
        adminAPI.listAiKnowledge(aiStatus, aiSearch.trim(), 100),
      ]);

      setFeedback(feedbackResponse.data || null);
      setIncidents(Array.isArray(incidentsResponse.data) ? incidentsResponse.data : []);
      setAiItems(Array.isArray(aiResponse.data) ? aiResponse.data : []);
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible cargar el panel de gobierno de IA.",
      });
    } finally {
      if (!quiet) setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const loadInitial = async () => {
      setLoading(true);
      try {
        const [feedbackResponse, incidentsResponse, aiResponse] = await Promise.all([
          adminAPI.feedbackSummary(10),
          adminAPI.listIncidentAlerts("open", 50),
          adminAPI.listAiKnowledge("pending", "", 100),
        ]);

        if (!mounted) return;
        setFeedback(feedbackResponse.data || null);
        setIncidents(Array.isArray(incidentsResponse.data) ? incidentsResponse.data : []);
        setAiItems(Array.isArray(aiResponse.data) ? aiResponse.data : []);
      } catch (error) {
        if (mounted) {
          setMessage({
            type: "error",
            text: error.response?.data?.detail || "No fue posible cargar el panel de gobierno de IA.",
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
  }, []);

  useEffect(() => {
    if (loading) return;
    const timer = window.setTimeout(() => loadAll(), aiSearch ? 350 : 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidentStatus, aiStatus, aiSearch]);

  const approvalRate = Number(feedback?.feedback?.approval_rate || 0);
  const totalUp = Number(feedback?.feedback?.total_up || 0);
  const totalDown = Number(feedback?.feedback?.total_down || 0);
  const surveys = Number(feedback?.satisfaction?.total_surveys || 0);
  const avgScore = Number(feedback?.satisfaction?.avg_score || 0);
  const resolutionRate = Number(feedback?.satisfaction?.resolution_rate || 0);
  const worstRated = Array.isArray(feedback?.worst_rated_messages)
    ? feedback.worst_rated_messages
    : [];

  const criticalIncidents = incidents.filter((item) => item.severity === "critical").length;
  const affectedUsers = incidents.reduce(
    (total, item) => total + Number(item.affected_users_count || 0),
    0,
  );
  const pendingAi = aiItems.filter((item) => item.status === "pending").length;

  const governanceScore = useMemo(() => {
    let score = 100;
    if (approvalRate && approvalRate < 75) score -= 15;
    if (resolutionRate && resolutionRate < 70) score -= 15;
    if (criticalIncidents > 0) score -= 20;
    if (pendingAi > 10) score -= 10;
    return Math.max(35, score);
  }, [approvalRate, resolutionRate, criticalIncidents, pendingAi]);

  const performAction = async () => {
    if (!confirmAction) return;
    const { type, item, notes = "" } = confirmAction;
    setActionId(item.id);
    setMessage(null);

    try {
      if (type === "acknowledge") await adminAPI.acknowledgeIncident(item.id, notes);
      if (type === "resolve") await adminAPI.resolveIncident(item.id, notes);
      if (type === "approve") await adminAPI.approveAiKnowledge(item.id);
      if (type === "reject") await adminAPI.rejectAiKnowledge(item.id, notes);

      setMessage({ type: "success", text: actionSuccessMessage(type) });
      setConfirmAction(null);
      await loadAll({ quiet: true });
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible completar la acción.",
      });
    } finally {
      setActionId("");
    }
  };

  return (
    <AppShell currentPage="governance">
      <main className="botiq-page-main botiq-governance-page">
        <header className="botiq-governance-heading">
          <div className="botiq-governance-heading__main">
            <div className="botiq-governance-heading__icon"><ShieldCheck size={27} /></div>
            <div>
              <span>Supervisión responsable</span>
              <h1>Gobierno de IA</h1>
              <p>Revisa incidentes, calidad de respuestas, satisfacción y conocimiento generado por IA antes de incorporarlo a BOTIQ.</p>
            </div>
          </div>
          <button type="button" className="botiq-governance-btn botiq-governance-btn--primary" onClick={() => loadAll()} disabled={loading}>
            <RefreshCw className={loading ? "spin" : ""} size={17} />
            {loading ? "Actualizando..." : "Recargar panel"}
          </button>
        </header>

        {message && <Alert type={message.type} text={message.text} onClose={() => setMessage(null)} />}

        <section className="botiq-governance-kpis" aria-label="Indicadores de gobierno">
          <MetricCard icon={ThumbsUp} label="Aprobación" value={`${approvalRate}%`} caption={`${totalUp} positivas · ${totalDown} negativas`} tone={approvalRate >= 75 ? "success" : "warning"} />
          <MetricCard icon={CircleGauge} label="Resolución por BOTIQ" value={`${resolutionRate}%`} caption={`${surveys} encuestas · promedio ${avgScore.toFixed(1)}`} tone={resolutionRate >= 70 ? "success" : "warning"} />
          <MetricCard icon={ShieldAlert} label="Incidentes visibles" value={incidents.length} caption={`${criticalIncidents} críticos · ${affectedUsers} usuarios`} tone={criticalIncidents ? "danger" : "info"} />
          <MetricCard icon={Sparkles} label="Conocimiento IA" value={aiItems.length} caption={`${pendingAi} pendientes de revisión`} tone={pendingAi > 10 ? "warning" : "purple"} />
        </section>

        <section className="botiq-governance-overview">
          <article className="botiq-governance-score">
            <header><div><span>Índice ejecutivo</span><h2>Madurez de gobierno</h2></div><Gauge size={22} /></header>
            <div>
              <div className="botiq-governance-score__ring" style={{ "--governance-progress": `${governanceScore * 3.6}deg` }}>
                <div><strong>{governanceScore}%</strong><span>{governanceScore >= 80 ? "Controlado" : "Atención"}</span></div>
              </div>
              <p>Indicador orientativo calculado con aprobación, resolución, incidentes críticos y volumen pendiente de revisión.</p>
            </div>
          </article>

          <article className="botiq-governance-feedback">
            <header><div><span>Percepción del usuario</span><h2>Calidad y satisfacción</h2></div><MessageSquareWarning size={22} /></header>
            <div className="botiq-governance-feedback__content">
              <FeedbackBar label="Respuestas útiles" value={approvalRate} icon={ThumbsUp} tone="success" />
              <FeedbackBar label="Resolución automática" value={resolutionRate} icon={BadgeCheck} tone="info" />
              <div className="botiq-governance-feedback__stats">
                <div><span>Encuestas</span><strong>{surveys}</strong></div>
                <div><span>Promedio</span><strong>{avgScore.toFixed(1)}</strong></div>
                <div><span>Peor calificados</span><strong>{worstRated.length}</strong></div>
              </div>
            </div>
          </article>
        </section>

        <Panel title="Alertas de incidentes masivos" eyebrow="Supervisión operativa" description="Prioriza afectaciones repetidas detectadas durante las conversaciones de soporte." tools={<FilterSelect value={incidentStatus} onChange={setIncidentStatus} options={INCIDENT_FILTERS} label="Estado de incidentes" />}>
          {loading ? <CardSkeleton count={3} /> : incidents.length === 0 ? <EmptyState icon={ShieldCheck} title="No hay incidentes para este filtro" text="La operación no registra alertas en el estado seleccionado." /> : (
            <div className="botiq-governance-incidents">
              {incidents.map((incident) => <IncidentCard key={incident.id} incident={incident} loading={actionId === incident.id} onAction={(type) => setConfirmAction({ type, item: incident, notes: "" })} />)}
            </div>
          )}
        </Panel>

        <Panel title="Conocimiento generado por IA" eyebrow="Control humano" description="Evalúa respuestas sin fuente interna antes de convertirlas en conocimiento oficial." tools={<div className="botiq-governance-ai-tools"><SearchField value={aiSearch} onChange={setAiSearch} onClear={() => setAiSearch("")} /><FilterSelect value={aiStatus} onChange={setAiStatus} options={AI_FILTERS} label="Estado del conocimiento IA" /></div>}>
          {loading ? <CardSkeleton count={3} /> : aiItems.length === 0 ? <EmptyState icon={Bot} title="No hay respuestas para revisar" text="No existen elementos que coincidan con el estado y la búsqueda." /> : (
            <div className="botiq-governance-ai-list">
              {aiItems.map((item) => <AiKnowledgeCard key={item.id} item={item} loading={actionId === item.id} onAction={(type) => setConfirmAction({ type, item, notes: "" })} />)}
            </div>
          )}
        </Panel>

        {worstRated.length > 0 && (
          <Panel title="Mensajes peor calificados" eyebrow="Seguimiento de calidad" description="Casos que requieren revisión de contenido, contexto o fuente.">
            <div className="botiq-governance-worst">
              {worstRated.map((item, index) => (
                <article key={item.message_id || index}><div>#{index + 1}</div><section><h3>Mensaje {item.message_id}</h3><p>Calificaciones negativas registradas</p></section><strong>{item.total_down || 0}</strong></article>
              ))}
            </div>
          </Panel>
        )}

        {confirmAction && <ActionModal action={confirmAction} loading={actionId === confirmAction.item.id} onChange={(notes) => setConfirmAction((current) => ({ ...current, notes }))} onCancel={() => setConfirmAction(null)} onConfirm={performAction} />}
      </main>
    </AppShell>
  );
}

function Panel({ title, eyebrow, description, tools, children }) {
  return <section className="botiq-governance-panel"><header className="botiq-governance-panel__header"><div><span>{eyebrow}</span><h2>{title}</h2><p>{description}</p></div>{tools}</header><div className="botiq-governance-panel__body">{children}</div></section>;
}

function MetricCard({ icon: Icon, label, value, caption, tone }) {
  return <article className={`botiq-governance-kpi tone-${tone}`}><div><Icon size={21} /></div><section><p>{label}</p><strong>{value}</strong><span>{caption}</span></section></article>;
}

function Alert({ type, text, onClose }) {
  const Icon = type === "success" ? CheckCircle2 : AlertCircle;
  return <div className={`botiq-governance-alert is-${type}`} role={type === "error" ? "alert" : "status"}><Icon size={18} /><p>{text}</p><button type="button" onClick={onClose} aria-label="Cerrar mensaje"><X size={16} /></button></div>;
}

function FeedbackBar({ label, value, icon: Icon, tone }) {
  return <div className="botiq-governance-feedback-bar"><header><span><Icon size={15} />{label}</span><strong>{value}%</strong></header><div><i className={`tone-${tone}`} style={{ width: `${value}%` }} /></div></div>;
}

function FilterSelect({ value, onChange, options, label }) {
  return <label className="botiq-governance-filter"><Filter size={16} /><select value={value} onChange={(event) => onChange(event.target.value)} aria-label={label}>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select><ChevronDown size={15} /></label>;
}

function SearchField({ value, onChange, onClear }) {
  return <label className="botiq-governance-search"><Search size={17} /><input type="search" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Buscar pregunta o respuesta..." aria-label="Buscar conocimiento IA" />{value && <button type="button" onClick={onClear} aria-label="Limpiar búsqueda"><X size={15} /></button>}</label>;
}

function IncidentCard({ incident, loading, onAction }) {
  const severity = incident.severity || "low";
  const status = incident.status || "open";
  return <article className={`botiq-governance-incident severity-${severity}`}>
    <header><div className="botiq-governance-incident__identity"><div><AlertTriangle size={21} /></div><section><h3>{incident.application_name || "Aplicación sin identificar"}</h3><a href={incident.app_or_url || "#"} target="_blank" rel="noreferrer">{incident.app_or_url || "Sin URL registrada"}<ExternalLink size={12} /></a></section></div><div className="botiq-governance-badges"><StatusBadge value={severity} type="severity" /><StatusBadge value={status} type="status" /></div></header>
    <div className="botiq-governance-incident__details"><InfoItem icon={UsersRound} label="Usuarios afectados" value={incident.affected_users_count || 0} /><InfoItem icon={Clock3} label="Última detección" value={formatDate(incident.last_seen_at)} /><InfoItem icon={FileQuestion} label="Categoría" value={incident.category || "Sin categoría"} /></div>
    {incident.recommendation && <div className="botiq-governance-recommendation"><ShieldAlert size={17} /><div><span>Recomendación</span><p>{incident.recommendation}</p></div></div>}
    {incident.notes && <div className="botiq-governance-note"><span>Notas administrativas</span><p>{incident.notes}</p></div>}
    <footer>{status === "open" && <button type="button" className="botiq-governance-btn botiq-governance-btn--secondary" onClick={() => onAction("acknowledge")} disabled={loading}><Eye size={16} />Reconocer</button>}{status !== "resolved" && <button type="button" className="botiq-governance-btn botiq-governance-btn--success" onClick={() => onAction("resolve")} disabled={loading}>{loading ? <RefreshCw className="spin" size={16} /> : <CheckCircle2 size={16} />}Resolver</button>}</footer>
  </article>;
}

function AiKnowledgeCard({ item, loading, onAction }) {
  const confidence = normalizeConfidence(item.confidence_score ?? item.confidence);
  return <article className="botiq-governance-ai-card">
    <header><div className="botiq-governance-ai-card__identity"><div><Sparkles size={20} /></div><section><span>Respuesta generada por IA</span><h3>{item.question}</h3></section></div><StatusBadge value={item.status || "pending"} type="status" /></header>
    <div className="botiq-governance-ai-answer"><span>Respuesta propuesta</span><p>{item.answer}</p></div>
    <div className="botiq-governance-ai-meta"><div><span>Confianza</span><strong>{Math.round(confidence * 100)}%</strong></div><div className="botiq-governance-confidence"><i style={{ width: `${confidence * 100}%` }} /></div><div><span>Usos</span><strong>{item.usage_count || 0}</strong></div><div><span>Creada</span><strong>{formatDate(item.created_at)}</strong></div></div>
    {item.status === "pending" && <footer><button type="button" className="botiq-governance-btn botiq-governance-btn--danger-ghost" onClick={() => onAction("reject")} disabled={loading}><XCircle size={16} />Rechazar</button><button type="button" className="botiq-governance-btn botiq-governance-btn--success" onClick={() => onAction("approve")} disabled={loading}>{loading ? <RefreshCw className="spin" size={16} /> : <Check size={16} />}Aprobar como FAQ</button></footer>}
  </article>;
}

function InfoItem({ icon: Icon, label, value }) { return <div><Icon size={15} /><section><span>{label}</span><strong>{value}</strong></section></div>; }
function StatusBadge({ value, type }) { const label = type === "severity" ? SEVERITY_LABELS[value] || value : STATUS_LABELS[value] || value; return <span className={`botiq-governance-badge ${type}-${value}`}><i />{label}</span>; }

function ActionModal({ action, loading, onChange, onCancel, onConfirm }) {
  const requiresNotes = action.type === "reject";
  return <div className="botiq-governance-modal-backdrop" role="presentation"><section className="botiq-governance-modal" role="dialog" aria-modal="true" aria-labelledby="governance-action-title"><header><div>{action.type === "reject" ? <XCircle size={23} /> : <ShieldCheck size={23} />}</div><section><h2 id="governance-action-title">{actionTitle(action.type)}</h2><p>{actionDescription(action.type)}</p></section><button type="button" onClick={onCancel} aria-label="Cerrar modal"><X size={17} /></button></header><label><span>{requiresNotes ? "Motivo del rechazo" : "Notas administrativas (opcional)"}</span><textarea value={action.notes} onChange={(event) => onChange(event.target.value)} placeholder={requiresNotes ? "Explica por qué esta respuesta no debe aprobarse..." : "Agrega contexto para la trazabilidad..."} rows={4} required={requiresNotes} /></label><footer><button type="button" className="botiq-governance-btn botiq-governance-btn--secondary" onClick={onCancel} disabled={loading}>Cancelar</button><button type="button" className={`botiq-governance-btn ${action.type === "reject" ? "botiq-governance-btn--danger" : "botiq-governance-btn--primary"}`} onClick={onConfirm} disabled={loading || (requiresNotes && !action.notes.trim())}>{loading ? <RefreshCw className="spin" size={16} /> : <CheckCircle2 size={16} />}{loading ? "Procesando..." : "Confirmar acción"}</button></footer></section></div>;
}

function EmptyState({ icon: Icon, title, text }) { return <div className="botiq-governance-empty"><Icon size={30} /><h3>{title}</h3><p>{text}</p></div>; }
function CardSkeleton({ count }) { return <div className="botiq-governance-skeletons">{Array.from({ length: count }).map((_, index) => <div key={index}><header><i /><section><span /><span /></section></header><p /><p /></div>)}</div>; }
function normalizeConfidence(value) { const number = Number(value || 0); return number > 1 ? Math.min(number / 100, 1) : Math.min(number, 1); }
function formatDate(value) { if (!value) return "Sin fecha"; return new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function actionTitle(type) { return { acknowledge: "Reconocer incidente", resolve: "Resolver incidente", approve: "Aprobar conocimiento", reject: "Rechazar conocimiento" }[type] || "Confirmar acción"; }
function actionDescription(type) { return { acknowledge: "La alerta quedará marcada como revisada y en seguimiento administrativo.", resolve: "La alerta dejará de aparecer entre los incidentes activos.", approve: "La respuesta será incorporada como conocimiento aprobado para BOTIQ.", reject: "La respuesta no será incorporada a la base de conocimiento." }[type] || ""; }
function actionSuccessMessage(type) { return { acknowledge: "El incidente fue reconocido correctamente.", resolve: "El incidente fue resuelto correctamente.", approve: "El conocimiento fue aprobado correctamente.", reject: "El conocimiento fue rechazado correctamente." }[type] || "La acción se completó correctamente."; }
