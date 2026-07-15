import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  BookOpenCheck,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Edit3,
  ExternalLink,
  FileSearch,
  Filter,
  Globe2,
  Hash,
  Layers3,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Tag,
  Trash2,
  X,
  XCircle,
} from "lucide-react";

import AppShell from "../components/Layout/AppShell";
import { adminAPI, faqAPI } from "../services/api";
import "../components/Faqs/faqs.css";

const EMPTY_FORM = {
  question: "",
  answer: "",
  category: "",
  tagsText: "",
};

const PAGE_SIZE_OPTIONS = [6, 12, 24, 48];

const SUGGESTION_STATUS = [
  { value: "pending", label: "Pendientes" },
  { value: "approved", label: "Aprobadas" },
  { value: "rejected", label: "Rechazadas" },
];

export default function FaqsPage() {
  const [faqs, setFaqs] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [message, setMessage] = useState(null);

  const [activeTab, setActiveTab] = useState("faqs");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sortBy, setSortBy] = useState("usage_desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);

  const [suggestionStatus, setSuggestionStatus] = useState("pending");
  const [suggestionSearch, setSuggestionSearch] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_FORM);

  const [editFaq, setEditFaq] = useState(null);
  const [editForm, setEditForm] = useState(EMPTY_FORM);

  const [editSuggestion, setEditSuggestion] = useState(null);
  const [suggestionForm, setSuggestionForm] = useState(EMPTY_FORM);

  const [rejectItem, setRejectItem] = useState(null);
  const [rejectReason, setRejectReason] = useState("No aplica como FAQ interna");

  const [confirmDelete, setConfirmDelete] = useState(null);
  const [openMenuId, setOpenMenuId] = useState("");

  const loadFaqs = async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    setMessage(null);

    try {
      const { data } = await faqAPI.list();
      setFaqs(Array.isArray(data) ? data : []);
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible cargar las FAQs.",
      });
    } finally {
      if (!quiet) setLoading(false);
    }
  };

  const loadSuggestions = async ({ quiet = false } = {}) => {
    if (!quiet) setLoadingSuggestions(true);
    setMessage(null);

    try {
      const { data } = await adminAPI.listWebKnowledge(
        suggestionStatus,
        suggestionSearch.trim(),
        100,
      );
      setSuggestions(Array.isArray(data) ? data : []);
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible cargar las sugerencias web.",
      });
    } finally {
      if (!quiet) setLoadingSuggestions(false);
    }
  };

  useEffect(() => {
    loadFaqs();
  }, []);

  useEffect(() => {
    loadSuggestions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestionStatus]);

  useEffect(() => {
    setPage(1);
  }, [search, categoryFilter, sortBy, pageSize]);

  useEffect(() => {
    const closeMenu = () => setOpenMenuId("");
    window.addEventListener("click", closeMenu);
    return () => window.removeEventListener("click", closeMenu);
  }, []);

  const categories = useMemo(() => {
    return [...new Set(faqs.map((faq) => faq.category).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "es"));
  }, [faqs]);

  const metrics = useMemo(() => {
    const totalHits = faqs.reduce((sum, faq) => sum + Number(faq.hit_count || 0), 0);
    const used = faqs.filter((faq) => Number(faq.hit_count || 0) > 0).length;
    const pending = suggestionStatus === "pending"
      ? suggestions.length
      : suggestions.filter((item) => item.status === "pending").length;

    return {
      total: faqs.length,
      categories: categories.length,
      totalHits,
      used,
      pending,
    };
  }, [faqs, categories, suggestions, suggestionStatus]);

  const filteredFaqs = useMemo(() => {
    const query = search.trim().toLowerCase();

    return faqs
      .filter((faq) => {
        const matchesSearch =
          !query ||
          faq.question?.toLowerCase().includes(query) ||
          faq.answer?.toLowerCase().includes(query) ||
          faq.category?.toLowerCase().includes(query) ||
          (faq.tags || []).join(" ").toLowerCase().includes(query);

        const matchesCategory =
          categoryFilter === "all" || faq.category === categoryFilter;

        return matchesSearch && matchesCategory;
      })
      .sort((a, b) => {
        if (sortBy === "usage_asc") {
          return Number(a.hit_count || 0) - Number(b.hit_count || 0);
        }
        if (sortBy === "question_asc") {
          return (a.question || "").localeCompare(b.question || "", "es");
        }
        if (sortBy === "question_desc") {
          return (b.question || "").localeCompare(a.question || "", "es");
        }
        if (sortBy === "category") {
          return (a.category || "Sin categoría").localeCompare(
            b.category || "Sin categoría",
            "es",
          );
        }
        return Number(b.hit_count || 0) - Number(a.hit_count || 0);
      });
  }, [faqs, search, categoryFilter, sortBy]);

  const totalPages = Math.max(1, Math.ceil(filteredFaqs.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * pageSize;
  const visibleFaqs = filteredFaqs.slice(start, start + pageSize);

  const normalizePayload = (values) => ({
    question: values.question.trim(),
    answer: values.answer.trim(),
    category: values.category.trim() || null,
    tags: values.tagsText
      ? values.tagsText
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean)
      : [],
  });

  const validateForm = (values) => {
    if (values.question.trim().length < 8) {
      return "La pregunta debe tener al menos 8 caracteres.";
    }

    if (values.answer.trim().length < 15) {
      return "La respuesta debe tener al menos 15 caracteres.";
    }

    return "";
  };

  const createFaq = async (event) => {
    event.preventDefault();

    const validation = validateForm(createForm);
    if (validation) {
      setMessage({ type: "error", text: validation });
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      await faqAPI.create(normalizePayload(createForm));
      setCreateForm(EMPTY_FORM);
      setCreateOpen(false);
      setMessage({ type: "success", text: "FAQ creada correctamente." });
      await loadFaqs({ quiet: true });
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible crear la FAQ.",
      });
    } finally {
      setSaving(false);
    }
  };

  const startEditFaq = (faq) => {
    setOpenMenuId("");
    setEditFaq(faq);
    setEditForm({
      question: faq.question || "",
      answer: faq.answer || "",
      category: faq.category || "",
      tagsText: faq.tags?.join(", ") || "",
    });
  };

  const updateFaq = async (event) => {
    event.preventDefault();
    if (!editFaq) return;

    const validation = validateForm(editForm);
    if (validation) {
      setMessage({ type: "error", text: validation });
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      await faqAPI.update(editFaq.id, normalizePayload(editForm));
      setEditFaq(null);
      setEditForm(EMPTY_FORM);
      setMessage({ type: "success", text: "FAQ actualizada correctamente." });
      await loadFaqs({ quiet: true });
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible actualizar la FAQ.",
      });
    } finally {
      setSaving(false);
    }
  };

  const deactivateFaq = async () => {
    if (!confirmDelete) return;

    setBusyId(confirmDelete.id);
    setMessage(null);

    try {
      await faqAPI.remove(confirmDelete.id);
      setConfirmDelete(null);
      setMessage({ type: "success", text: "FAQ desactivada correctamente." });
      await loadFaqs({ quiet: true });
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible desactivar la FAQ.",
      });
    } finally {
      setBusyId("");
    }
  };

  const startSuggestionEdit = (item) => {
    setEditSuggestion(item);
    setSuggestionForm({
      question: item.question || "",
      answer: item.answer || "",
      category: item.category || "",
      tagsText: item.tags?.join(", ") || "",
    });
  };

  const approveSuggestion = async (item, useEditedValues = false) => {
    const values = useEditedValues ? suggestionForm : {
      question: item.question || "",
      answer: item.answer || "",
      category: item.category || "",
      tagsText: item.tags?.join(", ") || "",
    };

    const validation = validateForm(values);
    if (validation) {
      setMessage({ type: "error", text: validation });
      return;
    }

    setBusyId(item.id);
    setMessage(null);

    try {
      const payload = useEditedValues ? normalizePayload(values) : {};
      await adminAPI.approveWebKnowledge(item.id, {
        ...payload,
        create_faq: true,
      });

      setEditSuggestion(null);
      setSuggestionForm(EMPTY_FORM);
      setMessage({
        type: "success",
        text: "Sugerencia aprobada y registrada como FAQ oficial.",
      });

      await Promise.all([
        loadFaqs({ quiet: true }),
        loadSuggestions({ quiet: true }),
      ]);
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible aprobar la sugerencia.",
      });
    } finally {
      setBusyId("");
    }
  };

  const rejectSuggestion = async () => {
    if (!rejectItem) return;

    setBusyId(rejectItem.id);
    setMessage(null);

    try {
      await adminAPI.rejectWebKnowledge(rejectItem.id, rejectReason.trim());
      setRejectItem(null);
      setRejectReason("No aplica como FAQ interna");
      setMessage({ type: "success", text: "Sugerencia rechazada correctamente." });
      await loadSuggestions({ quiet: true });
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No fue posible rechazar la sugerencia.",
      });
    } finally {
      setBusyId("");
    }
  };

  const hasFaqFilters =
    search || categoryFilter !== "all" || sortBy !== "usage_desc";

  const clearFaqFilters = () => {
    setSearch("");
    setCategoryFilter("all");
    setSortBy("usage_desc");
  };

  return (
    <AppShell currentPage="faqs">
      <main className="botiq-page-main botiq-faqs-page">
        <PageHeading
          onCreate={() => {
            setCreateForm(EMPTY_FORM);
            setCreateOpen(true);
          }}
          onRefresh={() =>
            activeTab === "faqs" ? loadFaqs() : loadSuggestions()
          }
          refreshing={loading || loadingSuggestions}
        />

        {message && (
          <Alert
            type={message.type}
            text={message.text}
            onClose={() => setMessage(null)}
          />
        )}

        <section className="botiq-faqs-kpis" aria-label="Resumen de conocimiento">
          <MetricCard
            icon={BookOpenCheck}
            label="FAQs activas"
            value={metrics.total}
            caption={`${metrics.used} con consultas`}
            tone="primary"
          />
          <MetricCard
            icon={Layers3}
            label="Categorías"
            value={metrics.categories}
            caption="Clasificación disponible"
            tone="purple"
          />
          <MetricCard
            icon={BarChart3}
            label="Consultas resueltas"
            value={metrics.totalHits}
            caption="Uso acumulado de FAQs"
            tone="success"
          />
          <MetricCard
            icon={Globe2}
            label="Sugerencias visibles"
            value={suggestions.length}
            caption={`Estado: ${statusLabel(suggestionStatus)}`}
            tone="warning"
          />
        </section>

        <section className="botiq-faqs-tabs" aria-label="Secciones de conocimiento">
          <button
            type="button"
            className={activeTab === "faqs" ? "is-active" : ""}
            onClick={() => setActiveTab("faqs")}
          >
            <BookOpenCheck size={18} />
            FAQs oficiales
            <span>{faqs.length}</span>
          </button>

          <button
            type="button"
            className={activeTab === "suggestions" ? "is-active" : ""}
            onClick={() => setActiveTab("suggestions")}
          >
            <Sparkles size={18} />
            Sugerencias web
            <span>{suggestions.length}</span>
          </button>
        </section>

        {activeTab === "faqs" ? (
          <>
            <section className="botiq-faqs-toolbar" aria-label="Filtros de FAQs">
              <div className="botiq-faqs-search">
                <Search size={18} aria-hidden="true" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Buscar pregunta, respuesta, categoría o etiqueta..."
                  aria-label="Buscar FAQs"
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
                icon={Filter}
                value={categoryFilter}
                onChange={setCategoryFilter}
                options={[
                  { value: "all", label: "Todas las categorías" },
                  ...categories.map((category) => ({
                    value: category,
                    label: category,
                  })),
                ]}
              />

              <SelectFilter
                icon={BarChart3}
                value={sortBy}
                onChange={setSortBy}
                options={[
                  { value: "usage_desc", label: "Más utilizadas" },
                  { value: "usage_asc", label: "Menos utilizadas" },
                  { value: "question_asc", label: "Pregunta A–Z" },
                  { value: "question_desc", label: "Pregunta Z–A" },
                  { value: "category", label: "Por categoría" },
                ]}
              />

              {hasFaqFilters && (
                <button
                  type="button"
                  className="botiq-faqs-clear"
                  onClick={clearFaqFilters}
                >
                  <X size={16} />
                  Limpiar
                </button>
              )}
            </section>

            <section className="botiq-faqs-panel">
              <header className="botiq-faqs-panel__header">
                <div>
                  <h2>Biblioteca oficial de FAQs</h2>
                  <p>
                    Mostrando {visibleFaqs.length} de {filteredFaqs.length} resultados.
                  </p>
                </div>

                <label className="botiq-faqs-page-size">
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
                <FaqSkeleton />
              ) : filteredFaqs.length === 0 ? (
                <EmptyState
                  filtered={Boolean(hasFaqFilters)}
                  onClear={clearFaqFilters}
                  onCreate={() => setCreateOpen(true)}
                />
              ) : (
                <>
                  <div className="botiq-faqs-grid">
                    {visibleFaqs.map((faq) => (
                      <FaqCard
                        key={faq.id}
                        faq={faq}
                        busy={busyId === faq.id}
                        menuOpen={openMenuId === faq.id}
                        onToggleMenu={(event) => {
                          event.stopPropagation();
                          setOpenMenuId((current) =>
                            current === faq.id ? "" : faq.id,
                          );
                        }}
                        onEdit={() => startEditFaq(faq)}
                        onDeactivate={() => {
                          setOpenMenuId("");
                          setConfirmDelete(faq);
                        }}
                      />
                    ))}
                  </div>

                  <Pagination
                    page={safePage}
                    totalPages={totalPages}
                    totalItems={filteredFaqs.length}
                    pageSize={pageSize}
                    onPage={setPage}
                  />
                </>
              )}
            </section>
          </>
        ) : (
          <>
            <section className="botiq-faqs-toolbar" aria-label="Filtros de sugerencias">
              <div className="botiq-faqs-search">
                <Search size={18} aria-hidden="true" />
                <input
                  value={suggestionSearch}
                  onChange={(event) => setSuggestionSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") loadSuggestions();
                  }}
                  placeholder="Buscar sugerencias web..."
                  aria-label="Buscar sugerencias web"
                />
                {suggestionSearch && (
                  <button
                    type="button"
                    onClick={() => setSuggestionSearch("")}
                    aria-label="Limpiar búsqueda"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>

              <SelectFilter
                icon={ShieldCheck}
                value={suggestionStatus}
                onChange={setSuggestionStatus}
                options={SUGGESTION_STATUS}
              />

              <button
                type="button"
                className="botiq-faqs-btn botiq-faqs-btn--secondary"
                onClick={() => loadSuggestions()}
                disabled={loadingSuggestions}
              >
                <RefreshCw
                  className={loadingSuggestions ? "spin" : ""}
                  size={17}
                />
                Buscar
              </button>
            </section>

            <section className="botiq-faqs-panel">
              <header className="botiq-faqs-panel__header">
                <div>
                  <h2>Conocimiento sugerido por búsquedas web</h2>
                  <p>
                    Revisa la calidad, las fuentes y el alcance antes de convertir una
                    respuesta en conocimiento oficial.
                  </p>
                </div>

                <StatusBadge status={suggestionStatus} />
              </header>

              {loadingSuggestions ? (
                <FaqSkeleton count={4} />
              ) : suggestions.length === 0 ? (
                <SuggestionEmpty status={suggestionStatus} />
              ) : (
                <div className="botiq-faqs-suggestions">
                  {suggestions.map((item) => (
                    <SuggestionCard
                      key={item.id}
                      item={item}
                      busy={busyId === item.id}
                      onApprove={() => approveSuggestion(item)}
                      onEdit={() => startSuggestionEdit(item)}
                      onReject={() => {
                        setRejectItem(item);
                        setRejectReason("No aplica como FAQ interna");
                      }}
                    />
                  ))}
                </div>
              )}
            </section>
          </>
        )}

        <FaqModal
          open={createOpen}
          title="Crear nueva FAQ"
          description="Agrega conocimiento validado a la biblioteca oficial de BOTIQ."
          onClose={() => !saving && setCreateOpen(false)}
        >
          <FaqForm
            values={createForm}
            onChange={setCreateForm}
            onSubmit={createFaq}
            saving={saving}
            submitLabel="Crear FAQ"
            onCancel={() => setCreateOpen(false)}
          />
        </FaqModal>

        <FaqModal
          open={Boolean(editFaq)}
          title="Editar FAQ"
          description="Actualiza la pregunta, respuesta y clasificación."
          onClose={() => !saving && setEditFaq(null)}
        >
          <FaqForm
            values={editForm}
            onChange={setEditForm}
            onSubmit={updateFaq}
            saving={saving}
            submitLabel="Guardar cambios"
            onCancel={() => setEditFaq(null)}
          />
        </FaqModal>

        <FaqModal
          open={Boolean(editSuggestion)}
          title="Editar antes de aprobar"
          description="Ajusta la redacción y clasificación antes de convertirla en FAQ oficial."
          onClose={() => !busyId && setEditSuggestion(null)}
        >
          <FaqForm
            values={suggestionForm}
            onChange={setSuggestionForm}
            onSubmit={(event) => {
              event.preventDefault();
              approveSuggestion(editSuggestion, true);
            }}
            saving={Boolean(busyId)}
            submitLabel="Aprobar como FAQ"
            onCancel={() => setEditSuggestion(null)}
            submitIcon={ShieldCheck}
          />
        </FaqModal>

        <FaqModal
          open={Boolean(rejectItem)}
          title="Rechazar sugerencia"
          description="Registra el motivo para mantener trazabilidad de la decisión."
          onClose={() => !busyId && setRejectItem(null)}
          compact
        >
          <form
            className="botiq-faqs-form"
            onSubmit={(event) => {
              event.preventDefault();
              rejectSuggestion();
            }}
          >
            <label className="botiq-faqs-field">
              <span>Motivo del rechazo</span>
              <textarea
                value={rejectReason}
                onChange={(event) => setRejectReason(event.target.value)}
                rows={5}
                maxLength={500}
                autoFocus
              />
              <small>{rejectReason.length}/500 caracteres</small>
            </label>

            <div className="botiq-faqs-modal-actions">
              <button
                type="button"
                className="botiq-faqs-btn botiq-faqs-btn--secondary"
                onClick={() => setRejectItem(null)}
                disabled={Boolean(busyId)}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="botiq-faqs-btn botiq-faqs-btn--danger"
                disabled={Boolean(busyId)}
              >
                {busyId ? (
                  <RefreshCw className="spin" size={17} />
                ) : (
                  <XCircle size={17} />
                )}
                {busyId ? "Rechazando..." : "Rechazar sugerencia"}
              </button>
            </div>
          </form>
        </FaqModal>

        <FaqModal
          open={Boolean(confirmDelete)}
          title="Desactivar FAQ"
          description="La FAQ dejará de estar disponible para responder consultas."
          onClose={() => !busyId && setConfirmDelete(null)}
          compact
        >
          <div className="botiq-faqs-confirm">
            <div className="botiq-faqs-confirm__icon">
              <Trash2 size={27} />
            </div>

            <div>
              <strong>{confirmDelete?.question}</strong>
              <p>
                Esta acción no elimina físicamente el registro. La FAQ quedará
                desactivada de acuerdo con la funcionalidad actual del backend.
              </p>
            </div>

            <div className="botiq-faqs-modal-actions">
              <button
                type="button"
                className="botiq-faqs-btn botiq-faqs-btn--secondary"
                onClick={() => setConfirmDelete(null)}
                disabled={Boolean(busyId)}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="botiq-faqs-btn botiq-faqs-btn--danger"
                onClick={deactivateFaq}
                disabled={Boolean(busyId)}
              >
                {busyId ? (
                  <RefreshCw className="spin" size={17} />
                ) : (
                  <Trash2 size={17} />
                )}
                {busyId ? "Desactivando..." : "Desactivar FAQ"}
              </button>
            </div>
          </div>
        </FaqModal>
      </main>
    </AppShell>
  );
}

function PageHeading({ onCreate, onRefresh, refreshing }) {
  return (
    <header className="botiq-faqs-heading">
      <div className="botiq-faqs-heading__main">
        <div className="botiq-faqs-heading__icon" aria-hidden="true">
          <CircleHelp size={27} />
        </div>

        <div>
          <span className="botiq-faqs-heading__eyebrow">Conocimiento</span>
          <h1>Gestión de FAQs</h1>
          <p>
            Administra conocimiento oficial y valida respuestas sugeridas por
            búsquedas web antes de publicarlas.
          </p>
        </div>
      </div>

      <div className="botiq-faqs-heading__actions">
        <button
          type="button"
          className="botiq-faqs-btn botiq-faqs-btn--secondary"
          onClick={onRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={refreshing ? "spin" : ""} size={17} />
          Actualizar
        </button>

        <button
          type="button"
          className="botiq-faqs-btn botiq-faqs-btn--primary"
          onClick={onCreate}
        >
          <Plus size={17} />
          Nueva FAQ
        </button>
      </div>
    </header>
  );
}

function MetricCard({ icon: Icon, label, value, caption, tone }) {
  return (
    <article className={`botiq-faqs-kpi botiq-faqs-kpi--${tone}`}>
      <div className="botiq-faqs-kpi__icon">
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
  return (
    <div
      className={`botiq-faqs-alert botiq-faqs-alert--${type}`}
      role={type === "error" ? "alert" : "status"}
    >
      <span>{type === "success" ? <Check size={16} /> : "!"}</span>
      <p>{text}</p>
      <button type="button" onClick={onClose} aria-label="Cerrar mensaje">
        <X size={16} />
      </button>
    </div>
  );
}

function SelectFilter({ icon: Icon, value, onChange, options }) {
  return (
    <label className="botiq-faqs-select">
      <Icon size={16} aria-hidden="true" />
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

function FaqCard({
  faq,
  busy,
  menuOpen,
  onToggleMenu,
  onEdit,
  onDeactivate,
}) {
  const tags = faq.tags || [];

  return (
    <article className="botiq-faq-card">
      <header>
        <div className="botiq-faq-card__badges">
          <span className="botiq-faq-category">
            <Layers3 size={13} />
            {faq.category || "Sin categoría"}
          </span>
          <span className="botiq-faq-usage">
            <BarChart3 size={13} />
            {faq.hit_count || 0} usos
          </span>
        </div>

        <div className="botiq-faqs-menu-wrap">
          <button
            type="button"
            className="botiq-faqs-icon-btn"
            onClick={onToggleMenu}
            aria-label={`Acciones para ${faq.question}`}
            aria-expanded={menuOpen}
            disabled={busy}
          >
            <MoreHorizontal size={18} />
          </button>

          {menuOpen && (
            <div
              className="botiq-faqs-menu"
              onClick={(event) => event.stopPropagation()}
            >
              <button type="button" onClick={onEdit}>
                <Edit3 size={16} />
                Editar FAQ
              </button>
              <button type="button" className="is-danger" onClick={onDeactivate}>
                <Trash2 size={16} />
                Desactivar
              </button>
            </div>
          )}
        </div>
      </header>

      <div className="botiq-faq-card__content">
        <h3>{faq.question}</h3>
        <p>{faq.answer}</p>
      </div>

      <footer>
        <div className="botiq-faq-tags">
          {tags.length > 0 ? (
            tags.slice(0, 5).map((tag) => (
              <span key={tag}>
                <Hash size={11} />
                {tag}
              </span>
            ))
          ) : (
            <span className="is-empty">
              <Tag size={12} />
              Sin etiquetas
            </span>
          )}

          {tags.length > 5 && <span>+{tags.length - 5}</span>}
        </div>

        <button type="button" className="botiq-faq-card__edit" onClick={onEdit}>
          <Edit3 size={14} />
          Editar
        </button>
      </footer>
    </article>
  );
}

function SuggestionCard({ item, busy, onApprove, onEdit, onReject }) {
  return (
    <article className="botiq-suggestion-card">
      <header>
        <div className="botiq-suggestion-card__meta">
          <StatusBadge status={item.status} />
          <span>
            <Layers3 size={13} />
            {item.category || "Sin categoría"}
          </span>
          <span>
            <BarChart3 size={13} />
            {item.usage_count || 0} usos
          </span>
        </div>

        {item.confidence != null && (
          <span className="botiq-suggestion-confidence">
            Confianza {Math.round(Number(item.confidence) * 100)}%
          </span>
        )}
      </header>

      <div className="botiq-suggestion-card__content">
        <h3>{item.question}</h3>
        <p>{item.answer}</p>
      </div>

      {item.sources?.length > 0 && (
        <details className="botiq-suggestion-sources">
          <summary>
            <Globe2 size={15} />
            Fuentes públicas consultadas
            <span>{item.sources.length}</span>
          </summary>

          <ul>
            {item.sources.map((source, index) => (
              <li key={`${item.id}-${index}`}>
                <div>
                  <strong>{source.title || "Fuente pública"}</strong>
                  {source.snippet && <p>{source.snippet}</p>}
                </div>
                {source.link && (
                  <a
                    href={source.link}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`Abrir ${source.title || "fuente pública"}`}
                  >
                    <ExternalLink size={15} />
                  </a>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}

      {item.status === "pending" && (
        <footer>
          <button
            type="button"
            className="botiq-faqs-btn botiq-faqs-btn--primary"
            onClick={onApprove}
            disabled={busy}
          >
            {busy ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <ShieldCheck size={16} />
            )}
            Aprobar como FAQ
          </button>

          <button
            type="button"
            className="botiq-faqs-btn botiq-faqs-btn--secondary"
            onClick={onEdit}
            disabled={busy}
          >
            <Edit3 size={16} />
            Editar primero
          </button>

          <button
            type="button"
            className="botiq-faqs-btn botiq-faqs-btn--danger-soft"
            onClick={onReject}
            disabled={busy}
          >
            <XCircle size={16} />
            Rechazar
          </button>
        </footer>
      )}
    </article>
  );
}

function FaqForm({
  values,
  onChange,
  onSubmit,
  saving,
  submitLabel,
  onCancel,
  submitIcon: SubmitIcon = Check,
}) {
  const tags = values.tagsText
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);

  return (
    <form className="botiq-faqs-form" onSubmit={onSubmit}>
      <Field
        label="Pregunta"
        required
        hint={`${values.question.length}/500 caracteres`}
      >
        <input
          value={values.question}
          onChange={(event) =>
            onChange({ ...values, question: event.target.value })
          }
          placeholder="Ej. ¿Cómo puedo restablecer mi contraseña?"
          minLength={8}
          maxLength={500}
          autoFocus
          required
        />
      </Field>

      <Field
        label="Respuesta"
        required
        hint={`${values.answer.length} caracteres`}
      >
        <textarea
          value={values.answer}
          onChange={(event) =>
            onChange({ ...values, answer: event.target.value })
          }
          placeholder="Escribe una respuesta clara, precisa y verificable..."
          rows={8}
          minLength={15}
          required
        />
      </Field>

      <div className="botiq-faqs-form-grid">
        <Field label="Categoría">
          <input
            value={values.category}
            onChange={(event) =>
              onChange({ ...values, category: event.target.value })
            }
            placeholder="Ej. Accesos"
            maxLength={100}
          />
        </Field>

        <Field label="Etiquetas" hint="Sepáralas con comas">
          <input
            value={values.tagsText}
            onChange={(event) =>
              onChange({ ...values, tagsText: event.target.value })
            }
            placeholder="contraseña, acceso, seguridad"
          />
        </Field>
      </div>

      {tags.length > 0 && (
        <div className="botiq-faqs-tag-preview">
          <span>Vista previa:</span>
          <div>
            {tags.slice(0, 8).map((tag) => (
              <i key={tag}>
                <Hash size={11} />
                {tag}
              </i>
            ))}
          </div>
        </div>
      )}

      <div className="botiq-faqs-form-quality">
        <QualityCheck
          ok={values.question.trim().length >= 8}
          label="Pregunta suficientemente descriptiva"
        />
        <QualityCheck
          ok={values.answer.trim().length >= 15}
          label="Respuesta con contenido mínimo"
        />
        <QualityCheck
          ok={Boolean(values.category.trim())}
          label="Categoría asignada"
          optional
        />
      </div>

      <div className="botiq-faqs-modal-actions">
        <button
          type="button"
          className="botiq-faqs-btn botiq-faqs-btn--secondary"
          onClick={onCancel}
          disabled={saving}
        >
          Cancelar
        </button>

        <button
          type="submit"
          className="botiq-faqs-btn botiq-faqs-btn--primary"
          disabled={saving}
        >
          {saving ? (
            <RefreshCw className="spin" size={17} />
          ) : (
            <SubmitIcon size={17} />
          )}
          {saving ? "Guardando..." : submitLabel}
        </button>
      </div>
    </form>
  );
}

function Field({ label, hint, required, children }) {
  return (
    <label className="botiq-faqs-field">
      <span>
        {label}
        {required && <b aria-hidden="true"> *</b>}
      </span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

function QualityCheck({ ok, label, optional = false }) {
  return (
    <span className={ok ? "is-ok" : optional ? "is-optional" : ""}>
      {ok ? <Check size={13} /> : optional ? "○" : "•"}
      {label}
      {optional && !ok && <em>Opcional</em>}
    </span>
  );
}

function StatusBadge({ status }) {
  return (
    <span className={`botiq-suggestion-status status-${status}`}>
      <i />
      {statusLabel(status)}
    </span>
  );
}

function statusLabel(status) {
  return (
    SUGGESTION_STATUS.find((item) => item.value === status)?.label ||
    status ||
    "Sin estado"
  );
}

function Pagination({ page, totalPages, totalItems, pageSize, onPage }) {
  const from = totalItems === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, totalItems);

  return (
    <footer className="botiq-faqs-pagination">
      <p>
        Mostrando {from}–{to} de {totalItems}
      </p>

      <div>
        <button
          type="button"
          className="botiq-faqs-icon-btn"
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
          className="botiq-faqs-icon-btn"
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

function EmptyState({ filtered, onClear, onCreate }) {
  return (
    <div className="botiq-faqs-empty">
      <div>
        <FileSearch size={31} />
      </div>
      <h3>
        {filtered ? "No encontramos coincidencias" : "No hay FAQs registradas"}
      </h3>
      <p>
        {filtered
          ? "Ajusta la búsqueda o limpia los filtros para consultar toda la biblioteca."
          : "Crea la primera FAQ para comenzar a construir la base de conocimiento oficial."}
      </p>
      <button
        type="button"
        className="botiq-faqs-btn botiq-faqs-btn--primary"
        onClick={filtered ? onClear : onCreate}
      >
        {filtered ? <X size={17} /> : <Plus size={17} />}
        {filtered ? "Limpiar filtros" : "Crear FAQ"}
      </button>
    </div>
  );
}

function SuggestionEmpty({ status }) {
  return (
    <div className="botiq-faqs-empty">
      <div>
        <Sparkles size={31} />
      </div>
      <h3>No hay sugerencias {statusLabel(status).toLowerCase()}</h3>
      <p>
        Las respuestas obtenidas mediante búsqueda web aparecerán aquí para que
        un administrador pueda revisarlas.
      </p>
    </div>
  );
}

function FaqSkeleton({ count = 6 }) {
  return (
    <div className="botiq-faqs-skeleton" aria-label="Cargando contenido">
      {Array.from({ length: count }).map((_, index) => (
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

function FaqModal({
  open,
  title,
  description,
  children,
  onClose,
  compact = false,
}) {
  useEffect(() => {
    if (!open) return undefined;

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
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="botiq-faqs-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      role="presentation"
    >
      <section
        className={`botiq-faqs-modal${compact ? " is-compact" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="botiq-faqs-modal-title"
      >
        <header>
          <div>
            <h2 id="botiq-faqs-modal-title">{title}</h2>
            {description && <p>{description}</p>}
          </div>

          <button
            type="button"
            className="botiq-faqs-icon-btn"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <X size={19} />
          </button>
        </header>

        <div className="botiq-faqs-modal__body">{children}</div>
      </section>
    </div>
  );
}
