import { useEffect, useState } from "react";
import Navbar from "../components/Layout/Navbar";
import { faqAPI } from "../services/api";

const C = "#272163";

const initialForm = {
  question: "",
  answer: "",
  category: "",
  tagsText: "",
};

export default function FaqsPage() {
  const [faqs, setFaqs] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState(initialForm);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadFaqs = async () => {
    setLoading(true);
    setError("");

    try {
      const { data } = await faqAPI.list();
      setFaqs(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error cargando FAQs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFaqs();
  }, []);

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
          <p style={{ color: "#6b6b8a", marginTop: 6, fontSize: 13 }}>
            Administra las respuestas frecuentes que BOTIQ usa para empleados.
          </p>
        </header>

        {error && <div style={alertStyle}>⚠️ {error}</div>}

        <section style={cardStyle}>
          <h2 style={sectionTitle}>Crear FAQ</h2>

          <form onSubmit={createFaq} style={{ display: "grid", gap: 12 }}>
            <Input
              label="Pregunta"
              value={form.question}
              onChange={(v) => setForm({ ...form, question: v })}
              required
            />

            <TextArea
              label="Respuesta"
              value={form.answer}
              onChange={(v) => setForm({ ...form, answer: v })}
              required
            />

            <div style={formGrid}>
              <Input
                label="Categoría"
                value={form.category}
                onChange={(v) => setForm({ ...form, category: v })}
              />

              <Input
                label="Tags separados por coma"
                value={form.tagsText}
                onChange={(v) => setForm({ ...form, tagsText: v })}
                placeholder="login, portal, contraseña"
              />
            </div>

            <div>
              <button disabled={saving} type="submit" style={primaryBtn}>
                {saving ? "Guardando..." : "Crear FAQ"}
              </button>
            </div>
          </form>
        </section>

        <section style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", marginBottom: 16 }}>
            <h2 style={sectionTitle}>FAQs registradas</h2>

            <div style={{ display: "flex", gap: 8 }}>
              <input
                placeholder="Buscar por pregunta, categoría o tag..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                style={{ ...inputStyle, minWidth: 280 }}
              />
              <button onClick={loadFaqs} style={secondaryBtn}>🔄 Actualizar</button>
            </div>
          </div>

          {loading ? (
            <p style={{ color: "#6b6b8a" }}>Cargando FAQs...</p>
          ) : filteredFaqs.length === 0 ? (
            <p style={{ color: "#6b6b8a" }}>No hay FAQs para mostrar.</p>
          ) : (
            <div style={{ display: "grid", gap: 14 }}>
              {filteredFaqs.map((faq) => (
                <article key={faq.id} style={faqCardStyle}>
                  {editing === faq.id ? (
                    <div style={{ display: "grid", gap: 10 }}>
                      <Input
                        label="Pregunta"
                        value={editForm.question}
                        onChange={(v) => setEditForm({ ...editForm, question: v })}
                      />
                      <TextArea
                        label="Respuesta"
                        value={editForm.answer}
                        onChange={(v) => setEditForm({ ...editForm, answer: v })}
                      />
                      <div style={formGrid}>
                        <Input
                          label="Categoría"
                          value={editForm.category}
                          onChange={(v) => setEditForm({ ...editForm, category: v })}
                        />
                        <Input
                          label="Tags"
                          value={editForm.tagsText}
                          onChange={(v) => setEditForm({ ...editForm, tagsText: v })}
                        />
                      </div>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button onClick={() => updateFaq(faq.id)} style={smallPrimaryBtn}>
                          Guardar
                        </button>
                        <button onClick={() => setEditing(null)} style={smallSecondaryBtn}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                        <div>
                          <h3 style={{ margin: "0 0 8px", color: C, fontSize: 15 }}>
                            {faq.question}
                          </h3>
                          <p style={{ margin: 0, color: "#374151", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                            {faq.answer}
                          </p>
                        </div>

                        <div style={{ display: "flex", gap: 8, alignItems: "start" }}>
                          <button onClick={() => startEdit(faq)} style={smallSecondaryBtn}>
                            Editar
                          </button>
                          <button onClick={() => removeFaq(faq.id)} style={{ ...smallSecondaryBtn, color: "#991b1b" }}>
                            Desactivar
                          </button>
                        </div>
                      </div>

                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                        {faq.category && <Badge>📁 {faq.category}</Badge>}
                        <Badge>👁️ {faq.hit_count} usos</Badge>
                        {(faq.tags || []).map((tag) => (
                          <Badge key={tag}>#{tag}</Badge>
                        ))}
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

function Input({ label, value, onChange, required = false, placeholder = "", type = "text" }) {
  return (
    <label style={labelStyle}>
      {label}
      <input
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle}
      />
    </label>
  );
}

function TextArea({ label, value, onChange, required = false }) {
  return (
    <label style={labelStyle}>
      {label}
      <textarea
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        rows={4}
        style={{ ...inputStyle, resize: "vertical", lineHeight: 1.5 }}
      />
    </label>
  );
}

function Badge({ children }) {
  return (
    <span style={{
      background: "#f5f5fa",
      color: C,
      border: "1px solid #e2e1f0",
      padding: "3px 9px",
      borderRadius: 999,
      fontSize: 11,
      fontWeight: 600,
    }}>
      {children}
    </span>
  );
}

const cardStyle = {
  background: "#fff",
  border: "1px solid #e2e1f0",
  borderRadius: 14,
  padding: 22,
  marginBottom: 22,
  boxShadow: "0 1px 4px rgba(39,33,99,0.06)",
};

const faqCardStyle = {
  border: "1px solid #e2e1f0",
  borderRadius: 12,
  padding: 16,
  background: "#fff",
};

const sectionTitle = {
  color: C,
  fontSize: 16,
  margin: "0 0 16px",
};

const formGrid = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 12,
};

const labelStyle = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
  fontSize: 12,
  fontWeight: 600,
  color: "#374151",
};

const inputStyle = {
  border: "1px solid #e2e1f0",
  borderRadius: 8,
  padding: "9px 10px",
  fontSize: 13,
  outline: "none",
  background: "#fff",
};

const primaryBtn = {
  background: C,
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "10px 16px",
  cursor: "pointer",
  fontWeight: 600,
};

const secondaryBtn = {
  background: "#f5f5fa",
  color: C,
  border: "1px solid #e2e1f0",
  borderRadius: 8,
  padding: "8px 12px",
  cursor: "pointer",
  fontWeight: 600,
};

const smallPrimaryBtn = {
  ...primaryBtn,
  padding: "7px 10px",
  fontSize: 12,
};

const smallSecondaryBtn = {
  ...secondaryBtn,
  padding: "7px 10px",
  fontSize: 12,
};

const alertStyle = {
  background: "#fef2f2",
  color: "#991b1b",
  border: "1px solid #fecaca",
  borderRadius: 10,
  padding: "12px 14px",
  marginBottom: 18,
  fontSize: 13,
};

