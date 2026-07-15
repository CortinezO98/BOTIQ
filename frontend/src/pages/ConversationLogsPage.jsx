import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Bot,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleUserRound,
  Clock3,
  Download,
  ExternalLink,
  FileSearch,
  Filter,
  MessageCircleMore,
  Network,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  TicketCheck,
  UserRoundCog,
  X,
} from "lucide-react";

import AppShell from "../components/Layout/AppShell";
import BotiqAvatar from "../components/Brand/BotiqAvatar";
import { chatAPI, downloadBlob } from "../services/api";
import "../components/ConversationLogs/conversation-logs.css";

const STATUS_OPTIONS = [
  { value: "", label: "Todos los estados" },
  { value: "active", label: "Activas" },
  { value: "ended", label: "Finalizadas" },
  { value: "blocked", label: "Bloqueadas" },
];

const PROFILE_OPTIONS = [
  { value: "", label: "Todos los perfiles" },
  { value: "employee", label: "Empleado" },
  { value: "support_engineer", label: "Ing. Soporte" },
];

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export default function ConversationLogsPage() {
  const [logs, setLogs] = useState([]);
  const [q, setQ] = useState("");
  const [profile, setProfile] = useState("");
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState(null);
  const [selected, setSelected] = useState(null);

  const [sortBy, setSortBy] = useState("recent");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const buildParams = (limit = 200) => {
    const params = { limit };
    if (q.trim()) params.q = q.trim();
    if (profile) params.selected_profile = profile;
    if (status) params.session_status = status;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    return params;
  };

  const load = async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    setMessage(null);

    try {
      const { data } = await chatAPI.adminConversationLogs(buildParams(500));
      setLogs(Array.isArray(data) ? data : []);
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible cargar los logs de conversaciones.",
      });
    } finally {
      if (!quiet) setLoading(false);
    }
  };

  const exportCsv = async () => {
    setExporting(true);
    setMessage(null);

    try {
      const { data } = await chatAPI.adminConversationLogsExport(
        buildParams(1000),
      );
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      downloadBlob(data, `botiq_logs_${stamp}.csv`);
      setMessage({
        type: "success",
        text: "El archivo CSV fue generado correctamente.",
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

  useEffect(() => {
    let mounted = true;

    const loadInitialLogs = async () => {
      setLoading(true);
      setMessage(null);

      try {
        const { data } = await chatAPI.adminConversationLogs({ limit: 500 });

        if (mounted) {
          setLogs(Array.isArray(data) ? data : []);
        }
      } catch (error) {
        if (mounted) {
          setMessage({
            type: "error",
            text:
              error.response?.data?.detail ||
              "No fue posible cargar los logs de conversaciones.",
          });
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadInitialLogs();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    setPage(1);
  }, [q, profile, status, dateFrom, dateTo, sortBy, pageSize]);

  const stats = useMemo(() => {
    const total = logs.length;
    const active = logs.filter((item) => item.session_status === "active").length;
    const ended = logs.filter((item) => item.session_status === "ended").length;
    const blocked = logs.filter((item) => item.session_status === "blocked").length;
    const escalated = logs.filter(
      (item) => item.escalated_to_aranda || item.aranda_ticket_id,
    ).length;
    const questions = logs.reduce(
      (sum, item) => sum + Number(item.question_count || 0),
      0,
    );

    return { total, active, ended, blocked, escalated, questions };
  }, [logs]);

  const sortedLogs = useMemo(() => {
    return [...logs].sort((a, b) => {
      if (sortBy === "oldest") {
        return new Date(a.created_at || 0) - new Date(b.created_at || 0);
      }

      if (sortBy === "questions_desc") {
        return Number(b.question_count || 0) - Number(a.question_count || 0);
      }

      if (sortBy === "user_asc") {
        return (a.user_full_name || a.user_email || "").localeCompare(
          b.user_full_name || b.user_email || "",
          "es",
        );
      }

      if (sortBy === "status") {
        return (a.session_status || "").localeCompare(
          b.session_status || "",
          "es",
        );
      }

      return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    });
  }, [logs, sortBy]);

  const totalPages = Math.max(1, Math.ceil(sortedLogs.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * pageSize;
  const visibleLogs = sortedLogs.slice(start, start + pageSize);

  const hasFilters =
    Boolean(q) ||
    Boolean(profile) ||
    Boolean(status) ||
    Boolean(dateFrom) ||
    Boolean(dateTo) ||
    sortBy !== "recent";

  const clearFilters = () => {
    setQ("");
    setProfile("");
    setStatus("");
    setDateFrom("");
    setDateTo("");
    setSortBy("recent");
  };

  return (
    <AppShell currentPage="conversation-logs">
      <main className="botiq-page-main botiq-logs-page">
        <PageHeading
          loading={loading}
          exporting={exporting}
          onRefresh={() => load()}
          onExport={exportCsv}
        />

        {message && (
          <Alert
            type={message.type}
            text={message.text}
            onClose={() => setMessage(null)}
          />
        )}

        <section className="botiq-logs-kpis" aria-label="Resumen de conversaciones">
          <MetricCard
            icon={MessageCircleMore}
            label="Conversaciones"
            value={stats.total}
            caption={`${stats.questions} preguntas registradas`}
            tone="primary"
          />
          <MetricCard
            icon={CheckCircle2}
            label="Finalizadas"
            value={stats.ended}
            caption={`${stats.active} todavía activas`}
            tone="success"
          />
          <MetricCard
            icon={ShieldAlert}
            label="Bloqueadas"
            value={stats.blocked}
            caption="Sesiones fuera de política"
            tone="danger"
          />
          <MetricCard
            icon={TicketCheck}
            label="Escaladas a Aranda"
            value={stats.escalated}
            caption="Tickets o escalaciones"
            tone="warning"
          />
        </section>

        <section className="botiq-logs-toolbar" aria-label="Filtros de logs">
          <div className="botiq-logs-search">
            <Search size={18} aria-hidden="true" />
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") load();
              }}
              placeholder="Buscar usuario, correo, URL, IP, ticket o consulta..."
              aria-label="Buscar logs"
            />
            {q && (
              <button
                type="button"
                onClick={() => setQ("")}
                aria-label="Limpiar búsqueda"
              >
                <X size={16} />
              </button>
            )}
          </div>

          <SelectFilter
            icon={CircleUserRound}
            value={profile}
            onChange={setProfile}
            options={PROFILE_OPTIONS}
          />

          <SelectFilter
            icon={Filter}
            value={status}
            onChange={setStatus}
            options={STATUS_OPTIONS}
          />

          <DateFilter
            label="Desde"
            value={dateFrom}
            onChange={setDateFrom}
          />

          <DateFilter
            label="Hasta"
            value={dateTo}
            onChange={setDateTo}
          />

          <button
            type="button"
            className="botiq-logs-btn botiq-logs-btn--primary"
            onClick={() => load()}
            disabled={loading}
          >
            <Search size={17} />
            {loading ? "Consultando..." : "Aplicar filtros"}
          </button>

          {hasFilters && (
            <button
              type="button"
              className="botiq-logs-clear"
              onClick={clearFilters}
            >
              <X size={16} />
              Limpiar
            </button>
          )}
        </section>

        <section className="botiq-logs-panel">
          <header className="botiq-logs-panel__header">
            <div>
              <h2>Historial de conversaciones</h2>
              <p>
                Mostrando {visibleLogs.length} de {sortedLogs.length} conversaciones.
              </p>
            </div>

            <div className="botiq-logs-panel__controls">
              <label className="botiq-logs-sort">
                <span>Ordenar</span>
                <select
                  value={sortBy}
                  onChange={(event) => setSortBy(event.target.value)}
                >
                  <option value="recent">Más recientes</option>
                  <option value="oldest">Más antiguas</option>
                  <option value="questions_desc">Más preguntas</option>
                  <option value="user_asc">Usuario A–Z</option>
                  <option value="status">Por estado</option>
                </select>
              </label>

              <label className="botiq-logs-page-size">
                Mostrar
                <select
                  value={pageSize}
                  onChange={(event) => setPageSize(Number(event.target.value))}
                >
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </header>

          {loading ? (
            <LogsSkeleton />
          ) : sortedLogs.length === 0 ? (
            <EmptyLogs
              filtered={hasFilters}
              onClear={clearFilters}
              onRefresh={() => load()}
            />
          ) : (
            <>
              <div className="botiq-desktop-only botiq-logs-table-wrap">
                <table className="botiq-logs-table-pro">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Usuario</th>
                      <th>Perfil</th>
                      <th>Estado</th>
                      <th>Preguntas</th>
                      <th>Última consulta</th>
                      <th>URL / IP</th>
                      <th>Ticket</th>
                      <th><span className="sr-only">Acciones</span></th>
                    </tr>
                  </thead>

                  <tbody>
                    {visibleLogs.map((item) => (
                      <LogRow
                        key={item.id}
                        item={item}
                        onOpen={() => setSelected(item)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="botiq-mobile-only">
                <div className="botiq-logs-mobile-grid">
                  {visibleLogs.map((item) => (
                    <LogCard
                      key={item.id}
                      item={item}
                      onOpen={() => setSelected(item)}
                    />
                  ))}
                </div>
              </div>

              <Pagination
                page={safePage}
                totalPages={totalPages}
                totalItems={sortedLogs.length}
                pageSize={pageSize}
                onPage={setPage}
              />
            </>
          )}
        </section>

        {selected && (
          <ConversationModal
            item={selected}
            onClose={() => setSelected(null)}
          />
        )}
      </main>
    </AppShell>
  );
}

function PageHeading({ loading, exporting, onRefresh, onExport }) {
  return (
    <header className="botiq-logs-heading">
      <div className="botiq-logs-heading__main">
        <div className="botiq-logs-heading__icon" aria-hidden="true">
          <MessageCircleMore size={27} />
        </div>

        <div>
          <span className="botiq-logs-heading__eyebrow">Trazabilidad</span>
          <h1>Logs de conversaciones</h1>
          <p>
            Consulta sesiones, perfiles, preguntas, URLs, IP, bloqueos,
            elegibilidad de tickets y escalaciones a Aranda.
          </p>
        </div>
      </div>

      <div className="botiq-logs-heading__actions">
        <button
          type="button"
          className="botiq-logs-btn botiq-logs-btn--secondary"
          onClick={onRefresh}
          disabled={loading}
        >
          <RefreshCw className={loading ? "spin" : ""} size={17} />
          Actualizar
        </button>

        <button
          type="button"
          className="botiq-logs-btn botiq-logs-btn--primary"
          onClick={onExport}
          disabled={exporting || loading}
        >
          {exporting ? (
            <RefreshCw className="spin" size={17} />
          ) : (
            <Download size={17} />
          )}
          {exporting ? "Exportando..." : "Exportar CSV"}
        </button>
      </div>
    </header>
  );
}

function MetricCard({ icon: Icon, label, value, caption, tone }) {
  return (
    <article className={`botiq-logs-kpi botiq-logs-kpi--${tone}`}>
      <div className="botiq-logs-kpi__icon">
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
      className={`botiq-logs-alert botiq-logs-alert--${type}`}
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

function SelectFilter({ icon: Icon, value, onChange, options }) {
  return (
    <label className="botiq-logs-select">
      <Icon size={16} aria-hidden="true" />
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value || "all"} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown size={15} aria-hidden="true" />
    </label>
  );
}

function DateFilter({ label, value, onChange }) {
  return (
    <label className="botiq-logs-date">
      <CalendarDays size={16} aria-hidden="true" />
      <span>{label}</span>
      <input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function LogRow({ item, onOpen }) {
  const profile = getProfileInfo(item.selected_profile);
  const statusInfo = getStatusInfo(item.session_status);

  return (
    <tr onClick={onOpen}>
      <td>
        <span className="botiq-logs-date-text">
          {formatDateTime(item.created_at)}
        </span>
      </td>

      <td>
        <UserIdentity item={item} />
      </td>

      <td>
        <span className={`botiq-log-profile profile-${item.selected_profile || "employee"}`}>
          {profile.label}
        </span>
      </td>

      <td>
        <span className={`botiq-log-status status-${item.session_status || "active"}`}>
          <i />
          {statusInfo.label}
        </span>
      </td>

      <td>
        <strong className="botiq-log-question-count">
          {item.question_count ?? 0}
        </strong>
      </td>

      <td>
        <span className="botiq-log-last-message" title={item.last_message}>
          {item.last_message || "Sin mensaje registrado"}
        </span>
      </td>

      <td>
        <span className="botiq-log-network" title={item.detected_url || item.detected_ip || ""}>
          {item.detected_url || item.detected_ip || "—"}
        </span>
      </td>

      <td>
        <TicketBadge item={item} />
      </td>

      <td>
        <button
          type="button"
          className="botiq-logs-icon-btn"
          onClick={(event) => {
            event.stopPropagation();
            onOpen();
          }}
          aria-label={`Ver conversación de ${item.user_full_name || item.user_email || "usuario"}`}
        >
          <ExternalLink size={17} />
        </button>
      </td>
    </tr>
  );
}

function LogCard({ item, onOpen }) {
  const profile = getProfileInfo(item.selected_profile);
  const statusInfo = getStatusInfo(item.session_status);

  return (
    <article className="botiq-log-mobile-card">
      <header>
        <UserIdentity item={item} />
        <span className={`botiq-log-status status-${item.session_status || "active"}`}>
          <i />
          {statusInfo.label}
        </span>
      </header>

      <div className="botiq-log-mobile-card__badges">
        <span className={`botiq-log-profile profile-${item.selected_profile || "employee"}`}>
          {profile.label}
        </span>
        <TicketBadge item={item} />
      </div>

      <p className="botiq-log-mobile-card__message">
        {item.last_message || "Sin mensaje registrado."}
      </p>

      {(item.detected_url || item.detected_ip) && (
        <div className="botiq-log-mobile-card__network">
          <Network size={14} />
          <span>{item.detected_url || item.detected_ip}</span>
        </div>
      )}

      <div className="botiq-log-mobile-card__meta">
        <span>
          <MessageCircleMore size={14} />
          {item.question_count ?? 0} preguntas
        </span>
        <span>
          <Clock3 size={14} />
          {formatDateTime(item.created_at)}
        </span>
      </div>

      <button
        type="button"
        className="botiq-logs-btn botiq-logs-btn--primary"
        onClick={onOpen}
      >
        <ExternalLink size={16} />
        Ver conversación completa
      </button>
    </article>
  );
}

function UserIdentity({ item }) {
  const initials = getInitials(item.user_full_name || item.user_email || "U");

  return (
    <div className="botiq-log-user">
      <div className="botiq-log-user__avatar">{initials}</div>
      <div>
        <strong>{item.user_full_name || "Usuario"}</strong>
        <span>{item.user_email || "Sin correo"}</span>
      </div>
    </div>
  );
}

function TicketBadge({ item }) {
  if (item.aranda_ticket_id) {
    return (
      <span className="botiq-log-ticket is-created">
        <TicketCheck size={13} />
        {item.aranda_ticket_id}
      </span>
    );
  }

  if (item.ticket_eligible) {
    return (
      <span className="botiq-log-ticket is-eligible">
        <Sparkles size={13} />
        Elegible
      </span>
    );
  }

  return <span className="botiq-log-ticket is-empty">Sin ticket</span>;
}

function ConversationModal({ item, onClose }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  useEffect(() => {
    let mounted = true;

    chatAPI
      .adminConversationMessages(item.id)
      .then(({ data }) => {
        if (mounted) setMessages(Array.isArray(data) ? data : []);
      })
      .catch((apiError) => {
        if (mounted) {
          setError(
            apiError.response?.data?.detail ||
              "No fue posible cargar la conversación.",
          );
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [item.id]);

  const summary = useMemo(() => buildSummary(item, messages), [item, messages]);

  return (
    <div
      className="botiq-log-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="botiq-log-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="botiq-log-modal-title"
      >
        <header className="botiq-log-modal__header">
          <div className="botiq-log-modal__identity">
            <BotiqAvatar size={42} color="#272163" />
            <div>
              <h2 id="botiq-log-modal-title">
                {item.user_full_name || "Usuario"}
              </h2>
              <p>{item.user_email || "Sin correo"}</p>
            </div>
          </div>

          <button
            type="button"
            className="botiq-log-modal__close"
            onClick={onClose}
            aria-label="Cerrar conversación"
          >
            <X size={19} />
          </button>
        </header>

        <div className="botiq-log-modal__body">
          <ConversationSummary item={item} summary={summary} />

          <section className="botiq-log-transcript">
            <header>
              <div>
                <span>Transcripción</span>
                <h3>Conversación completa</h3>
              </div>
              <strong>{messages.length} mensajes</strong>
            </header>

            {loading ? (
              <TranscriptSkeleton />
            ) : error ? (
              <Alert type="error" text={error} onClose={() => setError("")} />
            ) : messages.length === 0 ? (
              <div className="botiq-log-transcript-empty">
                <MessageCircleMore size={28} />
                <p>Esta conversación no tiene mensajes registrados.</p>
              </div>
            ) : (
              <div className="botiq-log-transcript__messages">
                {messages.map((message) => (
                  <TranscriptBubble key={message.id} message={message} />
                ))}
              </div>
            )}
          </section>
        </div>
      </section>
    </div>
  );
}

function ConversationSummary({ item, summary }) {
  return (
    <section className="botiq-log-summary">
      <div className="botiq-log-summary__badges">
        <span className={`botiq-log-status status-${item.session_status || "active"}`}>
          <i />
          {getStatusInfo(item.session_status).label}
        </span>

        <span className={`botiq-log-profile profile-${item.selected_profile || "employee"}`}>
          {getProfileInfo(item.selected_profile).label}
        </span>

        {item.support_network_username && (
          <span
            className={`botiq-log-network-user ${
              item.support_network_validated ? "is-valid" : "is-invalid"
            }`}
          >
            <UserRoundCog size={13} />
            {item.support_network_username}
          </span>
        )}

        <TicketBadge item={item} />
      </div>

      <div className="botiq-log-summary__text">
        <Bot size={18} />
        <p>
          <strong>Resumen automático:</strong> {summary}
        </p>
      </div>

      <div className="botiq-log-summary__stats">
        <SummaryStat label="Inicio" value={formatDateTime(item.created_at)} />
        <SummaryStat
          label="Fin"
          value={item.ended_at ? formatDateTime(item.ended_at) : "En curso"}
        />
        <SummaryStat label="Preguntas" value={item.question_count ?? 0} />
        <SummaryStat
          label="Fuera de alcance"
          value={item.out_of_scope_count ?? 0}
        />
        <SummaryStat
          label="Intentos de solución"
          value={item.resolution_attempts ?? 0}
        />
        <SummaryStat
          label="URL / IP"
          value={item.detected_url || item.detected_ip || "—"}
        />
      </div>
    </section>
  );
}

function SummaryStat({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TranscriptBubble({ message }) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <div
      className={`botiq-log-message ${
        isUser ? "is-user" : isSystem ? "is-system" : "is-assistant"
      }`}
    >
      <div className="botiq-log-message__avatar">
        {isUser ? <CircleUserRound size={17} /> : <Bot size={17} />}
      </div>

      <div className="botiq-log-message__content">
        <div className="botiq-log-message__bubble">
          {message.content}
        </div>

        <div className="botiq-log-message__meta">
          <span>{formatDateTime(message.created_at)}</span>
          {isSystem && <span>Sistema</span>}
          {message.tokens_used != null && (
            <span>{Math.round(message.tokens_used)} tokens</span>
          )}
          {message.has_image && <span>Imagen adjunta</span>}
        </div>
      </div>
    </div>
  );
}

function Pagination({ page, totalPages, totalItems, pageSize, onPage }) {
  const from = totalItems === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, totalItems);

  return (
    <footer className="botiq-logs-pagination">
      <p>
        Mostrando {from}–{to} de {totalItems}
      </p>

      <div>
        <button
          type="button"
          className="botiq-logs-icon-btn"
          onClick={() => onPage(Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="Página anterior"
        >
          <ChevronLeft size={18} />
        </button>

        <span>
          Página {page} de {totalPages}
        </span>

        <button
          type="button"
          className="botiq-logs-icon-btn"
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          aria-label="Página siguiente"
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </footer>
  );
}

function EmptyLogs({ filtered, onClear, onRefresh }) {
  return (
    <div className="botiq-logs-empty">
      <div>
        <FileSearch size={31} />
      </div>
      <h3>
        {filtered
          ? "No encontramos conversaciones"
          : "No hay conversaciones registradas"}
      </h3>
      <p>
        {filtered
          ? "Ajusta los filtros o limpia la búsqueda para consultar todo el historial."
          : "Actualiza la información cuando existan nuevas sesiones en BOTIQ."}
      </p>
      <button
        type="button"
        className="botiq-logs-btn botiq-logs-btn--primary"
        onClick={filtered ? onClear : onRefresh}
      >
        {filtered ? <X size={17} /> : <RefreshCw size={17} />}
        {filtered ? "Limpiar filtros" : "Actualizar"}
      </button>
    </div>
  );
}

function LogsSkeleton() {
  return (
    <div className="botiq-logs-skeleton" aria-label="Cargando conversaciones">
      {Array.from({ length: 7 }).map((_, index) => (
        <div key={index}>
          <span />
          <span />
          <span />
          <span />
          <span />
        </div>
      ))}
    </div>
  );
}

function TranscriptSkeleton() {
  return (
    <div className="botiq-log-transcript-skeleton">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className={index % 2 === 0 ? "left" : "right"}>
          <span />
        </div>
      ))}
    </div>
  );
}

function getStatusInfo(status) {
  const map = {
    active: { label: "Activa" },
    ended: { label: "Finalizada" },
    blocked: { label: "Bloqueada" },
  };

  return map[status] || { label: status || "Activa" };
}

function getProfileInfo(profile) {
  const map = {
    employee: { label: "Empleado" },
    support_engineer: { label: "Ing. Soporte" },
  };

  return map[profile] || { label: "Empleado" };
}

function buildSummary(item, messages) {
  const profile =
    item.selected_profile === "support_engineer"
      ? "ingeniero de soporte"
      : "empleado";

  const userMessages = messages.filter((message) => message.role === "user");
  const firstMessage = userMessages[0]?.content?.slice(0, 160);

  const parts = [
    `Sesión de ${profile} con ${
      item.question_count ?? userMessages.length
    } pregunta(s)`,
  ];

  if (firstMessage) {
    parts.push(
      `iniciada con la consulta “${firstMessage}${
        userMessages[0].content.length > 160 ? "…" : ""
      }”`,
    );
  }

  if (item.detected_url) parts.push(`se detectó la URL ${item.detected_url}`);
  else if (item.detected_ip) parts.push(`se detectó la IP ${item.detected_ip}`);

  if (item.out_of_scope_count > 0) {
    parts.push(`${item.out_of_scope_count} consulta(s) fuera de alcance`);
  }

  if (item.resolution_attempts > 0) {
    parts.push(`${item.resolution_attempts} intento(s) de solución guiada`);
  }

  if (item.aranda_ticket_id) {
    parts.push(`finalizó con ticket Aranda ${item.aranda_ticket_id}`);
  } else if (item.escalated_to_aranda) {
    parts.push("fue escalada a Aranda");
  } else if (item.ticket_eligible) {
    parts.push("quedó elegible para ticket como última instancia");
  }

  if (item.session_status === "blocked") {
    parts.push(
      `la sesión fue bloqueada${
        item.ended_reason ? ` (${item.ended_reason})` : ""
      }`,
    );
  } else if (item.session_status === "ended") {
    parts.push(
      `la sesión finalizó${
        item.ended_reason ? ` (${item.ended_reason})` : ""
      }`,
    );
  } else {
    parts.push("la sesión sigue activa");
  }

  return `${parts.join("; ")}.`;
}

function getInitials(value = "") {
  return (
    value
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "U"
  );
}

function formatDateTime(value) {
  if (!value) return "Sin fecha";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Sin fecha";

  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
