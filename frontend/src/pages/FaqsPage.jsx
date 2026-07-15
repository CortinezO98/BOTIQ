import { useEffect, useState } from "react";
import Navbar from "../components/Layout/Navbar";
import { adminAPI, faqAPI } from "../services/api";

const C = "#272163";

const initialForm = {
  question: "",
  answer: "",
  category: "",
  tagsText: "",
};

export default function FaqsPage() {
  const [faqs, setFaqs] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState(initialForm);
  const [editingSuggestion, setEditingSuggestion] = useState(null);
  const [suggestionForm, setSuggestionForm] = useState(initialForm);
  const [filter, setFilter] = useState("");
  const [suggestionStatus, setSuggestionStatus] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadFaqs = async () => {
    setLoading(true);
    setError("");

    try {
      const [{ data: faqsData }, { data: suggestionsData }] = await Promise.all([
        faqAPI.list(),
        adminAPI.listWebKnowledge(suggestionStatus, filter, 100),
      ]);
      setFaqs(faqsData);
      setSuggestions(suggestionsData);
    } catch (err) {
      setError(err.response?.data?.detail || "Error cargando FAQs o sugerencias web");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFaqs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestionStatus]);

  const normalizePayload = (values) => ({
    question: values.question.trim(),
    answer: values.answer.trim(),
    category: values.category.trim() || null,
    tags: values.tagsText
      ? values.tagsText.split(",").map((tag) => tag.trim()).filter(Boolean)
      : [],
  });

  const createFaq = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      await faqAPI.create(normalizePayload(form));
      setForm(initialForm);
      await loadFaqs();
    } catch (err) {
      setError(err.response?.data?.detail || "Error creando FAQ");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (faq) => {
    setEditing(faq.id);
    setEditForm({
      question: faq.question,
      answer: faq.answer,
      category: faq.category || "",
      tagsText: faq.tags?.join(", ") || "",
    });
  };

  const updateFaq = async (id) => {
    setSaving(true);
    setError("");

    try {
      await faqAPI.update(id, normalizePayload(editForm));
      setEditing(null);
      setEditForm(initialForm);
      await loadFaqs();
    } catch (err) {
      setError(err.response?.data?.detail || "Error actualizando FAQ");
    } finally {
      setSaving(false);
    }
  };

  const removeFaq = async (id) => {
    const ok = window.confirm("¿Seguro que deseas desactivar esta FAQ?");
    if (!ok) return;

    setError("");

    try {
      await faqAPI.remove(id);
      await loadFaqs();
    } catch (err) {
      setError(err.response?.data?.detail || "Error desactivando FAQ");
    }
  };

  const startEditSuggestion = (item) => {
    setEditingSuggestion(item.id);
    setSuggestionForm({
      question: item.question,
      answer: item.answer,
      category: item.category || "",
      tagsText: item.tags?.join(", ") || "",
    });
  };

  const approveSuggestion = async (item, useEdit = false) => {
    setSaving(true);
    setError("");

    try {
      const payload = useEdit ? normalizePayload(suggestionForm) : {};
      await adminAPI.approveWebKnowledge(item.id, { ...payload, create_faq: true });
      setEditingSuggestion(null);
      setSuggestionForm(initialForm);
      await loadFaqs();
    } catch (err) {
      setError(err.response?.data?.detail || "Error aprobando sugerencia");
    } finally {
      setSaving(false);
    }
  };

  const rejectSuggestion = async (item) => {
    const reason = window.prompt("Motivo del rechazo (opcional):", "No aplica como FAQ interna");
    if (reason === null) return;

    setSaving(true);
    setError("");

    try {
      await adminAPI.rejectWebKnowledge(item.id, reason);
      await loadFaqs();
    } catch (err) {
      setError(err.response?.data?.detail || "Error rechazando sugerencia");
    } finally {
      setSaving(false);
    }
  };

  const filteredFaqs = faqs.filter((faq) => {
    const q = filter.toLowerCase();
    return (
      faq.question.toLowerCase().includes(q) ||
      faq.answer.toLowerCase().includes(q) ||
      (faq.category || "").toLowerCase().includes(q) ||
      (faq.tags || []).join(" ").toLowerCase().includes(q)
    );
  });

  return (
    <div className="botiq-page botiq-admin-page">
      <Navbar currentPage="faqs" />

      <main className="botiq-page-main">
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ color: C, fontSize: 24, margin: 0 }}>Gestión de FAQs</h1>
          <p style={{ color: "var(--botiq-muted)", marginTop: 6, fontSize: 13 }}>
            Administra FAQs aprobadas y revisa conocimiento sugerido por búsquedas web de BOTIQ.
          </p>
        </header>

        {error && <div style={alertStyle}>⚠️ {error}</div>}

        <section style={cardStyle}>
          <h2 style={sectionTitle}>Crear FAQ manual</h2>

          <form onSubmit={createFaq} style={{ display: "grid", gap: 12 }}>
            <Input label="Pregunta" value={form.question} onChange={(v) => setForm({ ...form, question: v })} required />
            <TextArea label="Respuesta" value={form.answer} onChange={(v) => setForm({ ...form, answer: v })} required />

            <div style={formGrid}>
              <Input label="Categoría" value={form.category} onChange={(v) => setForm({ ...form, category: v })} />
              <Input label="Tags separados por coma" value={form.tagsText} onChange={(v) => setForm({ ...form, tagsText: v })} />
            </div>

            <button type="submit" disabled={saving} style={primaryBtn}>
              {saving ? "Guardando..." : "Crear FAQ"}
            </button>
          </form>
        </section>

        <section style={cardStyle}>
          <div style={headerRow}>
            <div>
              <h2 style={sectionTitle}>Conocimiento web sugerido</h2>
              <p style={muted}>
                BOTIQ registra aquí respuestas generadas desde internet. Deben aprobarse antes de ser FAQ oficial.
              </p>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <select value={suggestionStatus} onChange={(e) => setSuggestionStatus(e.target.value)} style={inputStyle}>
                <option value="pending">Pendientes</option>
                <option value="approved">Aprobadas</option>
                <option value="rejected">Rechazadas</option>
              </select>
              <button type="button" onClick={loadFaqs} style={secondaryBtn}>Actualizar</button>
            </div>
          </div>

          {suggestions.length === 0 ? (
            <div style={emptyStyle}>No hay sugerencias web en estado {suggestionStatus}.</div>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {suggestions.map((item) => (
                <article key={item.id} style={suggestionCard}>
                  {editingSuggestion === item.id ? (
                    <div style={{ display: "grid", gap: 10 }}>
                      <Input label="Pregunta" value={suggestionForm.question} onChange={(v) => setSuggestionForm({ ...suggestionForm, question: v })} />
                      <TextArea label="Respuesta aprobada" value={suggestionForm.answer} onChange={(v) => setSuggestionForm({ ...suggestionForm, answer: v })} rows={7} />
                      <div style={formGrid}>
                        <Input label="Categoría" value={suggestionForm.category} onChange={(v) => setSuggestionForm({ ...suggestionForm, category: v })} />
                        <Input label="Tags separados por coma" value={suggestionForm.tagsText} onChange={(v) => setSuggestionForm({ ...suggestionForm, tagsText: v })} />
                      </div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button type="button" disabled={saving} style={primaryBtn} onClick={() => approveSuggestion(item, true)}>
                          Aprobar como FAQ
                        </button>
                        <button type="button" style={secondaryBtn} onClick={() => setEditingSuggestion(null)}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div style={badgeRow}>
                        <span style={statusBadge(item.status)}>{item.status}</span>
                        <span style={muted}>{item.category || "Sin categoría"}</span>
                        <span style={muted}>Uso: {item.usage_count || 0}</span>
                      </div>
                      <h3 style={{ margin: "8px 0", color: C, fontSize: 15 }}>{item.question}</h3>
                      <p style={{ ...muted, whiteSpace: "pre-wrap", marginBottom: 10 }}>{item.answer}</p>

                      {item.sources?.length > 0 && (
                        <details style={{ marginBottom: 10 }}>
                          <summary style={{ cursor: "pointer", color: C, fontWeight: 700 }}>Fuentes públicas consultadas</summary>
                          <ul style={{ marginTop: 8 }}>
                            {item.sources.map((s, idx) => (
                              <li key={`${item.id}-${idx}`} style={{ fontSize: 12, color: "#4b4b6b" }}>
                                <strong>{s.title || "Fuente"}</strong>{" "}
                                {s.link ? <a href={s.link} target="_blank" rel="noreferrer">{s.link}</a> : null}
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}

                      {item.status === "pending" && (
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <button type="button" style={primaryBtn} disabled={saving} onClick={() => approveSuggestion(item)}>
                            Aprobar directo como FAQ
                          </button>
                          <button type="button" style={secondaryBtn} onClick={() => startEditSuggestion(item)}>
                            Editar antes de aprobar
                          </button>
                          <button type="button" style={dangerBtn} disabled={saving} onClick={() => rejectSuggestion(item)}>
                            Rechazar
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>

        <section style={cardStyle}>
          <div style={headerRow}>
            <h2 style={sectionTitle}>FAQs aprobadas</h2>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadFaqs()}
                placeholder="Filtrar FAQs y sugerencias..."
                style={inputStyle}
              />
              <button type="button" onClick={loadFaqs} style={secondaryBtn}>Buscar</button>
            </div>
          </div>

          {loading ? (
            <div style={emptyStyle}>Cargando...</div>
          ) : filteredFaqs.length === 0 ? (
            <div style={emptyStyle}>No hay FAQs registradas.</div>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {filteredFaqs.map((faq) => (
                <article key={faq.id} style={faqCard}>
                  {editing === faq.id ? (
                    <div style={{ display: "grid", gap: 10 }}>
                      <Input label="Pregunta" value={editForm.question} onChange={(v) => setEditForm({ ...editForm, question: v })} />
                      <TextArea label="Respuesta" value={editForm.answer} onChange={(v) => setEditForm({ ...editForm, answer: v })} />
                      <div style={formGrid}>
                        <Input label="Categoría" value={editForm.category} onChange={(v) => setEditForm({ ...editForm, category: v })} />
                        <Input label="Tags separados por coma" value={editForm.tagsText} onChange={(v) => setEditForm({ ...editForm, tagsText: v })} />
                      </div>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button type="button" disabled={saving} style={primaryBtn} onClick={() => updateFaq(faq.id)}>
                          Guardar
                        </button>
                        <button type="button" style={secondaryBtn} onClick={() => setEditing(null)}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div style={badgeRow}>
                        {faq.category && <span style={chipStyle}>{faq.category}</span>}
                        <span style={muted}>{faq.hit_count || 0} usos</span>
                      </div>
                      <h3 style={{ margin: "8px 0", color: C, fontSize: 16 }}>{faq.question}</h3>
                      <p style={{ color: "#4b4b6b", fontSize: 13, whiteSpace: "pre-wrap" }}>{faq.answer}</p>
                      {faq.tags?.length > 0 && (
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                          {faq.tags.map((tag) => <span key={tag} style={tagStyle}>{tag}</span>)}
                        </div>
                      )}
                      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                        <button type="button" style={secondaryBtn} onClick={() => startEdit(faq)}>
                          Editar
                        </button>
                        <button type="button" style={dangerBtn} onClick={() => removeFaq(faq.id)}>
                          Desactivar
                        </button>
                      </div>
                    </>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Input({ label, value, onChange, required = false }) {
  return (
    <label style={{ display: "grid", gap: 5, fontSize: 12, color: "#55556f", fontWeight: 700 }}>
      {label}
      <input required={required} value={value} onChange={(e) => onChange(e.target.value)} style={inputStyle} />
    </label>
  );
}

function TextArea({ label, value, onChange, required = false, rows = 5 }) {
  return (
    <label style={{ display: "grid", gap: 5, fontSize: 12, color: "#55556f", fontWeight: 700 }}>
      {label}
      <textarea required={required} value={value} onChange={(e) => onChange(e.target.value)} rows={rows} style={{ ...inputStyle, resize: "vertical" }} />
    </label>
  );
}

const cardStyle = {
  background: "var(--botiq-card-bg)",
  borderRadius: 18,
  padding: 20,
  boxShadow: "0 18px 40px rgba(39,33,99,.08)",
  border: "1px solid #ecebfa",
  marginBottom: 18,
};

const sectionTitle = { color: C, fontSize: 18, margin: 0 };
const muted = { color: "var(--botiq-muted)", fontSize: 13, margin: 0 };
const alertStyle = { background: "#fff1f1", color: "#b42318", border: "1px solid #ffcaca", padding: 12, borderRadius: 12, marginBottom: 16 };
const headerRow = { display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 14 };
const formGrid = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 };
const inputStyle = { border: "1px solid #d8d7ea", borderRadius: 10, padding: "10px 12px", outline: "none", fontSize: 13, minWidth: 180 };
const primaryBtn = { background: C, color: "#fff", border: 0, borderRadius: 10, padding: "10px 14px", fontWeight: 800, cursor: "pointer" };
const secondaryBtn = { background: "#f4f3ff", color: C, border: "1px solid #d9d6ff", borderRadius: 10, padding: "10px 14px", fontWeight: 800, cursor: "pointer" };
const dangerBtn = { background: "#fff1f1", color: "#b42318", border: "1px solid #ffcaca", borderRadius: 10, padding: "10px 14px", fontWeight: 800, cursor: "pointer" };
const emptyStyle = { padding: 18, borderRadius: 12, background: "#f7f7fc", color: "var(--botiq-muted)", fontSize: 13 };
const faqCard = { border: "1px solid #eeedf8", borderRadius: 14, padding: 14, background: "var(--botiq-card-bg)" };
const suggestionCard = { border: "1px solid #f1dfb8", borderRadius: 14, padding: 14, background: "#fffaf0" };
const badgeRow = { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" };
const chipStyle = { background: "#f4f3ff", color: C, fontWeight: 800, fontSize: 11, padding: "5px 8px", borderRadius: 999 };
const tagStyle = { background: "#f8f8fc", color: "#5c5b75", fontSize: 11, padding: "4px 8px", borderRadius: 999 };
const statusBadge = (status) => ({
  background: status === "approved" ? "#e8fff1" : status === "rejected" ? "#fff1f1" : "#fff4d6",
  color: status === "approved" ? "#067647" : status === "rejected" ? "#b42318" : "#9a6700",
  fontWeight: 900,
  fontSize: 11,
  padding: "5px 8px",
  borderRadius: 999,
});
