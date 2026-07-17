import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  BookOpenCheck,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Cloud,
  Database,
  File,
  FileSpreadsheet,
  FileText,
  FolderSync,
  HardDrive,
  Layers3,
  RefreshCw,
  Search,
  ServerCog,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  X,
} from "lucide-react";

import AppShell from "../components/Layout/AppShell";
import { supportAPI } from "../services/api";
import "../components/KnowledgeBase/knowledge-base.css";

const STATUS_OPTIONS = [
  { value: "all", label: "Todos los estados" },
  { value: "indexed", label: "Indexados" },
  { value: "pending", label: "Pendientes" },
  { value: "failed", label: "Con error" },
  { value: "skipped", label: "Sin cambios" },
];

const TYPE_OPTIONS = [
  { value: "all", label: "Todos los tipos" },
  { value: "pdf", label: "PDF" },
  { value: "google_doc", label: "Google Docs" },
  { value: "google_sheet", label: "Google Sheets" },
  { value: "xlsx", label: "Excel" },
  { value: "docx", label: "Word" },
  { value: "text", label: "Texto" },
];

const PAGE_SIZE_OPTIONS = [8, 12, 24, 48];

export default function KnowledgeBasePage() {
  const [status, setStatus] = useState(null);
  const [docsData, setDocsData] = useState({ summary: null, documents: [] });
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [reindexing, setReindexing] = useState("");
  const [message, setMessage] = useState(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sortBy, setSortBy] = useState("name_asc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);

  const [confirmSync, setConfirmSync] = useState(null);
  const pollRef = useRef(null);

  const loadAll = async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);

    try {
      const [statusResponse, documentsResponse] = await Promise.all([
        supportAPI.status(),
        supportAPI.documents(),
      ]);

      setStatus(statusResponse.data);
      setDocsData({
        summary: documentsResponse.data?.summary || null,
        documents: Array.isArray(documentsResponse.data?.documents)
          ? documentsResponse.data.documents
          : [],
      });
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible consultar la base de conocimiento.",
      });
    } finally {
      if (!quiet) setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    setPage(1);
  }, [search, statusFilter, typeFilter, sortBy, pageSize]);

  const startPolling = () => {
    let attempts = 0;
    // 480 x 5s = 40 minutos. Es una salvaguarda, no el criterio real de
    // parada -- el criterio real es sync_in_progress volviendo a false.
    // Documentos grandes (cientos de fragmentos) generan un embedding por
    // fragmento, uno por uno, y eso puede tardar bastante en un force=true
    // sobre toda la base.
    const MAX_ATTEMPTS = 480;

    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      attempts += 1;

      let statusResponse;
      try {
        const [statusRes, documentsRes] = await Promise.all([
          supportAPI.status(),
          supportAPI.documents(),
        ]);
        statusResponse = statusRes;

        setStatus(statusRes.data);
        setDocsData({
          summary: documentsRes.data?.summary || null,
          documents: Array.isArray(documentsRes.data?.documents)
            ? documentsRes.data.documents
            : [],
        });
      } catch (error) {
        // Un fallo puntual de red no debe cortar el seguimiento; seguimos
        // intentando hasta el límite de intentos.
        return;
      }

      const stillRunning = Boolean(statusResponse.data?.sync_in_progress);
      const timedOut = attempts >= MAX_ATTEMPTS;

      if (!stillRunning || timedOut) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setSyncing(false);

        const lastError = statusResponse.data?.last_sync_error;
        const lastResult = statusResponse.data?.last_sync_result;

        if (timedOut && stillRunning) {
          setMessage({
            type: "error",
            text:
              "La sincronización lleva mucho tiempo corriendo. Se detuvo el seguimiento automático, pero puede seguir en curso en el backend -- revisa los logs o refresca en unos minutos.",
          });
        } else if (lastError) {
          setMessage({
            type: "error",
            text: `La sincronización falló: ${lastError}`,
          });
        } else if (lastResult) {
          const failedCount = Number(lastResult.errors || 0);
          setMessage({
            type: failedCount > 0 ? "error" : "success",
            text:
              failedCount > 0
                ? `Sincronización finalizada con ${failedCount} documento(s) con error. Revisa las tarjetas marcadas en rojo abajo.`
                : `Sincronización finalizada. ${lastResult.indexed_new || 0} nuevos, ${lastResult.reindexed || 0} reindexados, ${lastResult.skipped_unchanged || 0} sin cambios.`,
          });
        } else {
          setMessage({
            type: "success",
            text: "Sincronización finalizada. La información fue actualizada.",
          });
        }
      }
    }, 5000);
  };

  const runSync = async (force) => {
    setConfirmSync(null);
    setSyncing(true);
    setMessage(null);

    try {
      const { data } = await supportAPI.sync(force);

      if (data.already_running) {
        setMessage({
          type: "info",
          text: data.message || "Ya hay una sincronización en curso.",
        });
        // Seguimos el progreso de la que ya está corriendo, no lanzamos otra.
        startPolling();
        return;
      }

      setMessage({
        type: "info",
        text:
          data.message ||
          (force
            ? "Reindexación completa iniciada."
            : "Sincronización incremental iniciada."),
      });

      await loadAll({ quiet: true });
      startPolling();
    } catch (error) {
      setSyncing(false);
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible iniciar la sincronización.",
      });
    }
  };

  const reindexDocument = async (document) => {
    setReindexing(document.file_id);
    setMessage(null);

    try {
      const { data } = await supportAPI.reindexDocument(document.file_id);

      if (data.status === "indexed") {
        setMessage({
          type: "success",
          text: `"${document.file_name}" fue reindexado con ${data.chunk_count || 0} fragmentos.`,
        });
      } else {
        setMessage({
          type: "error",
          text:
            data.message ||
            `No fue posible reindexar "${document.file_name}".`,
        });
      }

      await loadAll({ quiet: true });
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          `No fue posible reindexar "${document.file_name}".`,
      });
    } finally {
      setReindexing("");
    }
  };

  const documents = docsData.documents;
  const summary = docsData.summary || {
    total: documents.length,
    indexed: documents.filter((item) => item.status === "indexed").length,
    failed: documents.filter((item) => item.status === "failed").length,
    total_chunks: documents.reduce(
      (total, item) => total + Number(item.chunk_count || 0),
      0,
    ),
  };

  const metrics = {
    total: Number(summary.total || 0),
    indexed: Number(summary.indexed || 0),
    failed: Number(summary.failed || 0),
    totalChunks: Number(summary.total_chunks || status?.total_chunks || 0),
    folders: Number(status?.drive_folder_count || 0),
  };

  const healthPercent =
    metrics.total > 0
      ? Math.round((metrics.indexed / metrics.total) * 100)
      : status?.status === "active"
        ? 100
        : 0;

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();

    return documents
      .filter((document) => {
        const matchesSearch =
          !query ||
          document.file_name?.toLowerCase().includes(query) ||
          document.doc_type?.toLowerCase().includes(query) ||
          document.error_message?.toLowerCase().includes(query);

        const matchesStatus =
          statusFilter === "all" || document.status === statusFilter;

        const matchesType =
          typeFilter === "all" || document.doc_type === typeFilter;

        return matchesSearch && matchesStatus && matchesType;
      })
      .sort((a, b) => {
        if (sortBy === "name_desc") {
          return (b.file_name || "").localeCompare(a.file_name || "", "es");
        }

        if (sortBy === "chunks_desc") {
          return Number(b.chunk_count || 0) - Number(a.chunk_count || 0);
        }

        if (sortBy === "recent") {
          return (
            new Date(b.last_indexed_at || b.drive_modified_at || 0) -
            new Date(a.last_indexed_at || a.drive_modified_at || 0)
          );
        }

        if (sortBy === "status") {
          return (a.status || "").localeCompare(b.status || "", "es");
        }

        return (a.file_name || "").localeCompare(b.file_name || "", "es");
      });
  }, [documents, search, statusFilter, typeFilter, sortBy]);

  const totalPages = Math.max(
    1,
    Math.ceil(filteredDocuments.length / pageSize),
  );
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * pageSize;
  const visibleDocuments = filteredDocuments.slice(start, start + pageSize);

  const hasFilters =
    Boolean(search) ||
    statusFilter !== "all" ||
    typeFilter !== "all" ||
    sortBy !== "name_asc";

  const clearFilters = () => {
    setSearch("");
    setStatusFilter("all");
    setTypeFilter("all");
    setSortBy("name_asc");
  };

  return (
    <AppShell currentPage="knowledge-base">
      <main className="botiq-page-main botiq-kb-page">
        <PageHeading
          syncing={syncing}
          onRefresh={() => loadAll()}
          onIncremental={() => setConfirmSync("incremental")}
          onFull={() => setConfirmSync("full")}
        />

        {message && (
          <Alert
            type={message.type}
            text={message.text}
            onClose={() => setMessage(null)}
          />
        )}

        {!loading && !status?.drive_configured && (
          <DriveWarning folderIds={status?.drive_folder_ids || []} />
        )}

        <section className="botiq-kb-kpis" aria-label="Estado de la base de conocimiento">
          <MetricCard
            icon={FileText}
            label="Documentos registrados"
            value={metrics.total}
            caption={`${metrics.indexed} indexados`}
            tone="primary"
          />
          <MetricCard
            icon={Layers3}
            label="Fragmentos RAG"
            value={metrics.totalChunks}
            caption="Contenido disponible para recuperación"
            tone="purple"
          />
          <MetricCard
            icon={FolderSync}
            label="Carpetas conectadas"
            value={metrics.folders}
            caption={status?.drive_configured ? "Google Drive activo" : "Sin conexión"}
            tone={status?.drive_configured ? "success" : "warning"}
          />
          <MetricCard
            icon={ShieldCheck}
            label="Salud de indexación"
            value={`${healthPercent}%`}
            caption={`${metrics.failed} documentos con error`}
            tone={metrics.failed > 0 ? "warning" : "info"}
          />
        </section>

        <section className="botiq-kb-overview">
          <article className="botiq-kb-health-card">
            <header>
              <div>
                <span>Estado del motor RAG</span>
                <h2>
                  {status?.status === "active"
                    ? "Base de conocimiento operativa"
                    : "Base de conocimiento con novedades"}
                </h2>
              </div>
              <EngineBadge status={status?.status} />
            </header>

            <div className="botiq-kb-health-card__content">
              <div className="botiq-kb-ring" style={{ "--progress": `${healthPercent * 3.6}deg` }}>
                <div>
                  <strong>{healthPercent}%</strong>
                  <span>indexado</span>
                </div>
              </div>

              <dl>
                <div>
                  <dt>Documentos indexados</dt>
                  <dd>{metrics.indexed}</dd>
                </div>
                <div>
                  <dt>Documentos fallidos</dt>
                  <dd>{metrics.failed}</dd>
                </div>
                <div>
                  <dt>Fragmentos en ChromaDB</dt>
                  <dd>{status?.total_chunks ?? metrics.totalChunks}</dd>
                </div>
                <div>
                  <dt>Conexión Google Drive</dt>
                  <dd>{status?.drive_configured ? "Disponible" : "No configurada"}</dd>
                </div>
              </dl>
            </div>
          </article>

          <article className="botiq-kb-source-card">
            <header>
              <div className="botiq-kb-source-card__icon">
                <Cloud size={22} />
              </div>
              <div>
                <span>Fuente de conocimiento</span>
                <h2>Google Drive corporativo</h2>
              </div>
            </header>

            <div className="botiq-kb-source-card__body">
              <div className="botiq-kb-source-row">
                <span>Estado</span>
                <strong className={status?.drive_configured ? "is-success" : "is-warning"}>
                  {status?.drive_configured ? "Conectado" : "No configurado"}
                </strong>
              </div>
              <div className="botiq-kb-source-row">
                <span>Carpetas raíz</span>
                <strong>{metrics.folders}</strong>
              </div>
              <div className="botiq-kb-source-row">
                <span>Modo recomendado</span>
                <strong>Sincronización incremental</strong>
              </div>

              {status?.drive_folder_ids?.length > 0 && (
                <details className="botiq-kb-folders">
                  <summary>
                    <HardDrive size={15} />
                    Ver identificadores configurados
                    <ChevronDown size={15} />
                  </summary>
                  <ul>
                    {status.drive_folder_ids.map((folderId) => (
                      <li key={folderId}>{folderId}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          </article>
        </section>

        <section className="botiq-kb-toolbar" aria-label="Filtros de documentos">
          <div className="botiq-kb-search">
            <Search size={18} aria-hidden="true" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar documento, tipo o detalle del error..."
              aria-label="Buscar documentos"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                aria-label="Limpiar búsqueda"
              >
                <X size={16} />
              </button>
            )}
          </div>

          <SelectFilter
            value={statusFilter}
            onChange={setStatusFilter}
            options={STATUS_OPTIONS}
          />

          <SelectFilter
            value={typeFilter}
            onChange={setTypeFilter}
            options={TYPE_OPTIONS}
          />

          <SelectFilter
            value={sortBy}
            onChange={setSortBy}
            options={[
              { value: "name_asc", label: "Nombre A–Z" },
              { value: "name_desc", label: "Nombre Z–A" },
              { value: "chunks_desc", label: "Más fragmentos" },
              { value: "recent", label: "Más recientes" },
              { value: "status", label: "Por estado" },
            ]}
          />

          {hasFilters && (
            <button type="button" className="botiq-kb-clear" onClick={clearFilters}>
              <X size={16} />
              Limpiar
            </button>
          )}
        </section>

        <section className="botiq-kb-panel">
          <header className="botiq-kb-panel__header">
            <div>
              <h2>Documentos indexados</h2>
              <p>
                Mostrando {visibleDocuments.length} de {filteredDocuments.length} documentos.
              </p>
            </div>

            <label className="botiq-kb-page-size">
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
          </header>

          {loading ? (
            <DocumentSkeleton />
          ) : filteredDocuments.length === 0 ? (
            <EmptyDocuments
              filtered={hasFilters}
              driveConfigured={Boolean(status?.drive_configured)}
              onClear={clearFilters}
              onSync={() => setConfirmSync("incremental")}
            />
          ) : (
            <>
              <div className="botiq-kb-grid">
                {visibleDocuments.map((document) => (
                  <DocumentCard
                    key={document.file_id}
                    document={document}
                    reindexing={reindexing === document.file_id}
                    onReindex={() => reindexDocument(document)}
                  />
                ))}
              </div>

              <Pagination
                page={safePage}
                totalPages={totalPages}
                totalItems={filteredDocuments.length}
                pageSize={pageSize}
                onPage={setPage}
              />
            </>
          )}
        </section>

        <ConfirmSyncModal
          mode={confirmSync}
          onClose={() => !syncing && setConfirmSync(null)}
          onConfirm={() => runSync(confirmSync === "full")}
          syncing={syncing}
        />
      </main>
    </AppShell>
  );
}

function PageHeading({ syncing, onRefresh, onIncremental, onFull }) {
  return (
    <header className="botiq-kb-heading">
      <div className="botiq-kb-heading__main">
        <div className="botiq-kb-heading__icon" aria-hidden="true">
          <Database size={27} />
        </div>

        <div>
          <span className="botiq-kb-heading__eyebrow">RAG corporativo</span>
          <h1>Base de conocimiento</h1>
          <p>
            Supervisa documentos, sincronización con Google Drive y estado de
            indexación del conocimiento utilizado por BOTIQ.
          </p>
        </div>
      </div>

      <div className="botiq-kb-heading__actions">
        <button
          type="button"
          className="botiq-kb-btn botiq-kb-btn--secondary"
          onClick={onRefresh}
          disabled={syncing}
        >
          <RefreshCw className={syncing ? "spin" : ""} size={17} />
          Actualizar
        </button>

        <button
          type="button"
          className="botiq-kb-btn botiq-kb-btn--secondary"
          onClick={onFull}
          disabled={syncing}
        >
          <ServerCog size={17} />
          Reindexar todo
        </button>

        <button
          type="button"
          className="botiq-kb-btn botiq-kb-btn--primary"
          onClick={onIncremental}
          disabled={syncing}
        >
          {syncing ? (
            <RefreshCw className="spin" size={17} />
          ) : (
            <FolderSync size={17} />
          )}
          {syncing ? "Sincronizando..." : "Sincronizar cambios"}
        </button>
      </div>
    </header>
  );
}

function MetricCard({ icon: Icon, label, value, caption, tone }) {
  return (
    <article className={`botiq-kb-kpi botiq-kb-kpi--${tone}`}>
      <div className="botiq-kb-kpi__icon">
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
  const Icon =
    type === "success"
      ? CheckCircle2
      : type === "info"
        ? Sparkles
        : AlertCircle;

  return (
    <div className={`botiq-kb-alert botiq-kb-alert--${type}`} role={type === "error" ? "alert" : "status"}>
      <Icon size={18} />
      <p>{text}</p>
      <button type="button" onClick={onClose} aria-label="Cerrar mensaje">
        <X size={16} />
      </button>
    </div>
  );
}

function DriveWarning({ folderIds }) {
  return (
    <section className="botiq-kb-drive-warning">
      <div className="botiq-kb-drive-warning__icon">
        <TriangleAlert size={23} />
      </div>
      <div>
        <h2>Google Drive no está configurado</h2>
        <p>
          Configura las carpetas raíz y comparte su acceso con la cuenta de
          servicio para habilitar sincronización e indexación.
        </p>
        {folderIds.length > 0 && (
          <small>Configuración detectada: {folderIds.join(", ")}</small>
        )}
      </div>
    </section>
  );
}

function EngineBadge({ status }) {
  const active = status === "active";

  return (
    <span className={`botiq-kb-engine-badge ${active ? "is-active" : "is-error"}`}>
      <i />
      {active ? "Operativo" : "Revisar"}
    </span>
  );
}

function SelectFilter({ value, onChange, options }) {
  return (
    <label className="botiq-kb-select">
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown size={15} aria-hidden="true" />
    </label>
  );
}

function DocumentCard({ document, reindexing, onReindex }) {
  const Icon = documentIcon(document.doc_type);
  const statusInfo = getStatusInfo(document.status);

  return (
    <article className={`botiq-kb-document status-${document.status || "pending"}`}>
      <header>
        <div className={`botiq-kb-document__icon type-${document.doc_type || "file"}`}>
          <Icon size={23} />
        </div>

        <div className="botiq-kb-document__title">
          <span>{typeLabel(document.doc_type)}</span>
          <h3 title={document.file_name}>{document.file_name}</h3>
        </div>

        <span className={`botiq-kb-status status-${document.status || "pending"}`}>
          <i />
          {statusInfo.label}
        </span>
      </header>

      <div className="botiq-kb-document__stats">
        <div>
          <span>Fragmentos</span>
          <strong>{document.chunk_count || 0}</strong>
        </div>
        <div>
          <span>Modificado en Drive</span>
          <strong>{formatDate(document.drive_modified_at)}</strong>
        </div>
        <div>
          <span>Última indexación</span>
          <strong>{formatDateTime(document.last_indexed_at)}</strong>
        </div>
      </div>

      {document.error_message && (
        <div className="botiq-kb-document__error">
          <AlertCircle size={15} />
          <p>{document.error_message}</p>
        </div>
      )}

      <footer>
        <span className="botiq-kb-file-id" title={document.file_id}>
          ID: {shortId(document.file_id)}
        </span>

        <button
          type="button"
          className="botiq-kb-btn botiq-kb-btn--secondary botiq-kb-btn--small"
          onClick={onReindex}
          disabled={reindexing}
        >
          <RefreshCw className={reindexing ? "spin" : ""} size={15} />
          {reindexing ? "Reindexando..." : "Reindexar"}
        </button>
      </footer>
    </article>
  );
}

function EmptyDocuments({ filtered, driveConfigured, onClear, onSync }) {
  return (
    <div className="botiq-kb-empty">
      <div>
        <BookOpenCheck size={32} />
      </div>
      <h3>
        {filtered
          ? "No encontramos documentos"
          : "La base de conocimiento todavía está vacía"}
      </h3>
      <p>
        {filtered
          ? "Ajusta la búsqueda o limpia los filtros para consultar todos los documentos."
          : driveConfigured
            ? "Inicia una sincronización incremental para importar e indexar los documentos disponibles."
            : "Conecta Google Drive para comenzar a construir la base de conocimiento corporativa."}
      </p>

      {filtered ? (
        <button type="button" className="botiq-kb-btn botiq-kb-btn--primary" onClick={onClear}>
          <X size={17} />
          Limpiar filtros
        </button>
      ) : driveConfigured ? (
        <button type="button" className="botiq-kb-btn botiq-kb-btn--primary" onClick={onSync}>
          <FolderSync size={17} />
          Sincronizar documentos
        </button>
      ) : null}
    </div>
  );
}

function DocumentSkeleton() {
  return (
    <div className="botiq-kb-skeleton" aria-label="Cargando documentos">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index}>
          <span />
          <span />
          <span />
          <span />
        </div>
      ))}
    </div>
  );
}

function Pagination({ page, totalPages, totalItems, pageSize, onPage }) {
  const from = totalItems === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, totalItems);

  return (
    <footer className="botiq-kb-pagination">
      <p>
        Mostrando {from}–{to} de {totalItems}
      </p>

      <div>
        <button
          type="button"
          className="botiq-kb-icon-btn"
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
          className="botiq-kb-icon-btn"
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

function ConfirmSyncModal({ mode, onClose, onConfirm, syncing }) {
  useEffect(() => {
    if (!mode) return undefined;

    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [mode, onClose]);

  if (!mode) return null;

  const full = mode === "full";

  return (
    <div className="botiq-kb-modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="botiq-kb-modal" role="dialog" aria-modal="true" aria-labelledby="botiq-kb-sync-title">
        <header>
          <div>
            <h2 id="botiq-kb-sync-title">
              {full ? "Reindexar toda la base" : "Sincronizar cambios"}
            </h2>
            <p>
              {full
                ? "Todos los documentos serán procesados nuevamente."
                : "Solo se procesarán documentos nuevos o modificados."}
            </p>
          </div>
          <button type="button" className="botiq-kb-icon-btn" onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </header>

        <div className="botiq-kb-modal__body">
          <div className={`botiq-kb-confirm-icon ${full ? "is-warning" : "is-primary"}`}>
            {full ? <ServerCog size={28} /> : <FolderSync size={28} />}
          </div>

          <h3>{full ? "Esta operación puede tardar varios minutos" : "Sincronización incremental recomendada"}</h3>
          <p>
            {full
              ? "Utilízala cuando cambie la estrategia de fragmentación, embeddings o cuando necesites reconstruir completamente el índice."
              : "BOTIQ comparará cambios en Google Drive y mantendrá intactos los documentos que no fueron modificados."}
          </p>
        </div>

        <footer>
          <button type="button" className="botiq-kb-btn botiq-kb-btn--secondary" onClick={onClose} disabled={syncing}>
            Cancelar
          </button>
          <button type="button" className={`botiq-kb-btn ${full ? "botiq-kb-btn--warning" : "botiq-kb-btn--primary"}`} onClick={onConfirm} disabled={syncing}>
            {syncing ? <RefreshCw className="spin" size={17} /> : full ? <ServerCog size={17} /> : <FolderSync size={17} />}
            {syncing ? "Iniciando..." : full ? "Reindexar todo" : "Sincronizar"}
          </button>
        </footer>
      </section>
    </div>
  );
}

function documentIcon(type) {
  const icons = {
    pdf: FileText,
    google_doc: FileText,
    google_sheet: FileSpreadsheet,
    xlsx: FileSpreadsheet,
    docx: FileText,
    text: File,
  };

  return icons[type] || File;
}

function typeLabel(type) {
  const labels = {
    pdf: "Documento PDF",
    google_doc: "Google Docs",
    google_sheet: "Google Sheets",
    xlsx: "Archivo Excel",
    docx: "Documento Word",
    text: "Archivo de texto",
  };

  return labels[type] || "Documento";
}

function getStatusInfo(status) {
  const info = {
    indexed: { label: "Indexado" },
    pending: { label: "Pendiente" },
    failed: { label: "Error" },
    skipped: { label: "Sin cambios" },
  };

  return info[status] || { label: status || "Pendiente" };
}

function formatDate(value) {
  if (!value) return "Sin fecha";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Sin fecha";

  return new Intl.DateTimeFormat("es-CO", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function formatDateTime(value) {
  if (!value) return "No indexado";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No indexado";

  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function shortId(value = "") {
  if (value.length <= 18) return value || "Sin identificador";
  return `${value.slice(0, 9)}…${value.slice(-6)}`;
}
