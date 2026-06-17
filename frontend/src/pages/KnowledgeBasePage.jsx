import { useEffect, useRef, useState } from "react";
import Navbar from "../components/Layout/Navbar";
import { supportAPI } from "../services/api";

const C = "#272163";

const STATUS_INFO = {
  indexed: { label: "Indexado", color: "#059669", icon: "✅" },
  pending: { label: "Pendiente", color: "#d97706", icon: "⏳" },
  failed: { label: "Error", color: "#dc2626", icon: "❌" },
  skipped: { label: "Sin cambios", color: "#6b6b8a", icon: "⏭️" },
};

const DOC_ICON = {
  pdf: "📄",
  xlsx: "📊",
  google_doc: "📝",
  google_sheet: "📊",
  text: "📃",
  docx: "📝",
};

export default function KnowledgeBasePage() {
  const [status, setStatus] = useState(null);
  const [docsData, setDocsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [reindexing, setReindexing] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const pollRef = useRef(null);

  const loadAll = async () => {
    setError("");
    try {
      const [s, d] = await Promise.all([supportAPI.status(), supportAPI.documents()]);
      setStatus(s.data);
      setDocsData(d.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error consultando la base de conocimiento");
    } finally {
      setLoading(false);
    }
  };

  // Tras lanzar sync (corre en background), refresca varias veces para ver el avance.
  const startPolling = () => {
    let count = 0;
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      count += 1;
      await loadAll();
      if (count >= 6) {
        clearInterval(pollRef.current);
        setSyncing(false);
      }
    }, 5000);
  };

  const sync = async (force) => {
    setSyncing(true);
    setError("");
    setNotice("");
    try {
      const { data } = await supportAPI.sync(force);
      setNotice(
        (data.message || "Sincronización iniciada") +
          ". Actualizando estado automáticamente durante ~30s..."
      );
      await loadAll();
      startPolling();
    } catch (err) {
      setError(err.response?.data?.detail || "Error iniciando sincronización");
      setSyncing(false);
    }
  };

  const reindex = async (fileId, fileName) => {
    setReindexing(fileId);
    setError("");
    setNotice("");
    try {
      const { data } = await supportAPI.reindexDocument(fileId);
      if (data.status === "indexed") {
        setNotice(`"${fileName}" reindexado: ${data.chunk_count} chunks.`);
      } else {
        setError(`No se pudo reindexar "${fileName}": ${data.message || data.status}`);
      }
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Error reindexando el documento");
    } finally {
      setReindexing("");
    }
  };

  useEffect(() => {
    loadAll();
    return () => clearInterval(pollRef.current);
  }, []);

  const summary = docsData?.summary;

  return (
    <div className="botiq-page botiq-admin-page">
      <Navbar currentPage="knowledge-base" />

      <main className="botiq-page-main">
        <header
          className="animate__animated animate__fadeIn"
          style={{ marginBottom: 22, display: "flex", flexWrap: "wrap", gap: 14, alignItems: "flex-end", justifyContent: "space-between" }}
        >
          <div style={{ minWidth: 0 }}>
            <h1 style={{ color: C, fontSize: "clamp(22px, 3vw, 28px)", margin: 0, letterSpacing: "-0.5px" }}>
              📚 Base de conocimiento
            </h1>
            <p style={{ color: "#6b6b8a", marginTop: 6, fontSize: 13, lineHeight: 1.6, maxWidth: 640 }}>
              Estado del RAG, Google Drive y documentos indexados en ChromaDB. La
              sincronización es incremental: solo procesa documentos nuevos o modificados.
            </p>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button onClick={() => sync(false)} disabled={syncing} style={primaryBtn}>
              {syncing ? "Sincronizando..." : "☁️ Sincronizar (incremental)"}
            </button>
            <button onClick={() => sync(true)} disabled={syncing} style={secondaryBtn} title="Reprocesa todos los documentos">
              ♻️ Reindexar todo
            </button>
            <button onClick={loadAll} style={secondaryBtn}>🔄 Actualizar</button>
          </div>
        </header>

        {notice && <div style={noticeOk}>ℹ️ {notice}</div>}
        {error && <div style={alertStyle}>⚠️ {error}</div>}

        {loading ? (
          <div className="botiq-card" style={{ padding: 18, color: "#6b6b8a" }}>Cargando estado...</div>
        ) : (
          <>
            {/* KPIs */}
            <section className="botiq-kpi-row animate__animated animate__fadeInUp">
              <Kpi label="Estado RAG" value={status?.status === "active" ? "Activo" : (status?.status || "—")} icon={status?.status === "active" ? "✅" : "⚠️"} />
              <Kpi label="Chunks indexados" value={status?.total_chunks ?? 0} icon="📦" color="#4f46e5" />
              <Kpi label="Documentos" value={summary?.total ?? 0} icon="🗂️" />
              <Kpi label="Indexados" value={summary?.indexed ?? 0} icon="✅" color="#059669" />
              <Kpi label="Con error" value={summary?.failed ?? 0} icon="❌" color={summary?.failed ? "#dc2626" : C} />
              <Kpi label="Carpetas Drive" value={status?.drive_folder_count ?? 0} icon="☁️" color={status?.drive_configured ? "#0284c7" : "#dc2626"} />
            </section>

            {!status?.drive_configured && (
              <div style={noticeStyle}>
                <strong>Google Drive no está configurado.</strong><br />
                Configura <code>GDRIVE_FOLDER_ID</code> (o <code>GDRIVE_FOLDER_IDS</code>) en
                <code> backend/.env</code>, comparte las carpetas con el service account y reinicia el backend.
              </div>
            )}

            {/* Tabla de documentos */}
            <section className="botiq-card" style={{ padding: 0, marginTop: 16 }}>
              <div style={{ padding: "14px 18px", borderBottom: "1px solid #e2e1f0", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                <h2 style={{ color: C, fontSize: 15, margin: 0 }}>Documentos indexados</h2>
                <span style={{ fontSize: 12, color: "#6b6b8a" }}>
                  {summary?.total ?? 0} documento(s) · {summary?.total_chunks ?? 0} chunks
                </span>
              </div>

              {!docsData?.documents?.length ? (
                <div style={{ padding: 28, textAlign: "center", color: "#6b6b8a" }}>
                  <div style={{ fontSize: 34, marginBottom: 8 }}>🗂️</div>
                  Aún no hay documentos registrados. Pulsa <strong>Sincronizar</strong> para indexar la carpeta de Drive.
                </div>
              ) : (
                <>
                  {/* Escritorio: tabla */}
                  <div className="botiq-table-wrap botiq-desktop-only">
                    <table className="botiq-logs-table">
                      <thead>
                        <tr>
                          <th>Documento</th>
                          <th>Tipo</th>
                          <th style={{ textAlign: "center" }}>Chunks</th>
                          <th>Estado</th>
                          <th>Última indexación</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {docsData.documents.map((doc) => {
                          const st = STATUS_INFO[doc.status] || STATUS_INFO.pending;
                          return (
                            <tr key={doc.file_id}>
                              <td style={{ maxWidth: 320 }}>
                                <span style={{ fontWeight: 650, color: "#1a1a2e", overflowWrap: "anywhere" }}>
                                  {DOC_ICON[doc.doc_type] || "📄"} {doc.file_name}
                                </span>
                                {doc.status === "failed" && doc.error_message && (
                                  <div style={{ color: "#dc2626", fontSize: 11, marginTop: 3 }}>{doc.error_message}</div>
                                )}
                              </td>
                              <td style={{ color: "#6b6b8a", fontSize: 12 }}>{doc.doc_type || "—"}</td>
                              <td style={{ textAlign: "center", fontWeight: 800, color: C }}>{doc.chunk_count}</td>
                              <td><Badge color={st.color}>{st.icon} {st.label}</Badge></td>
                              <td style={{ color: "#6b6b8a", fontSize: 12, whiteSpace: "nowrap" }}>
                                {doc.last_indexed_at ? new Date(doc.last_indexed_at).toLocaleString() : "—"}
                              </td>
                              <td>
                                <button
                                  onClick={() => reindex(doc.file_id, doc.file_name)}
                                  disabled={reindexing === doc.file_id}
                                  style={miniBtn}
                                >
                                  {reindexing === doc.file_id ? "..." : "♻️ Reindexar"}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Móvil: tarjetas */}
                  <div className="botiq-mobile-only" style={{ padding: 14, display: "grid", gap: 10 }}>
                    {docsData.documents.map((doc) => {
                      const st = STATUS_INFO[doc.status] || STATUS_INFO.pending;
                      return (
                        <div key={doc.file_id} style={{ border: "1px solid #e2e1f0", borderRadius: 12, padding: 12 }}>
                          <div style={{ fontWeight: 700, color: "#1a1a2e", fontSize: 13, overflowWrap: "anywhere", marginBottom: 6 }}>
                            {DOC_ICON[doc.doc_type] || "📄"} {doc.file_name}
                          </div>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
                            <Badge color={st.color}>{st.icon} {st.label}</Badge>
                            <span style={{ fontSize: 11, color: "#6b6b8a" }}>{doc.chunk_count} chunks</span>
                          </div>
                          {doc.status === "failed" && doc.error_message && (
                            <div style={{ color: "#dc2626", fontSize: 11, marginBottom: 8 }}>{doc.error_message}</div>
                          )}
                          <button
                            onClick={() => reindex(doc.file_id, doc.file_name)}
                            disabled={reindexing === doc.file_id}
                            style={{ ...miniBtn, width: "100%" }}
                          >
                            {reindexing === doc.file_id ? "Reindexando..." : "♻️ Reindexar"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </section>

            {/* Detalle técnico */}
            <section className="botiq-card" style={{ padding: 18, marginTop: 16 }}>
              <h2 style={{ color: C, fontSize: 14, margin: "0 0 14px" }}>Detalle técnico</h2>
              <div style={{ display: "grid", gap: 10, color: "#374151", fontSize: 13 }}>
                <Row label="Drive configurado" value={status?.drive_configured ? "Sí" : "No"} />
                <Row label="Carpetas configuradas" value={String(status?.drive_folder_count ?? 0)} />
                <Row label="Estado ChromaDB" value={status?.status || "unknown"} />
                <Row label="Total chunks" value={String(status?.total_chunks ?? 0)} />
                {status?.detail && <Row label="Detalle error" value={status.detail} danger />}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function Kpi({ label, value, icon, color = C }) {
  return (
    <article className="botiq-card" style={{ padding: "14px 16px" }}>
      <div style={{ color: "#6b6b8a", fontSize: 11, fontWeight: 750, display: "flex", alignItems: "center", gap: 6 }}>
        <span>{icon}</span> {label}
      </div>
      <div style={{ color, fontSize: 24, fontWeight: 900, marginTop: 4, overflowWrap: "anywhere" }}>{value}</div>
    </article>
  );
}

function Row({ label, value, danger = false }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 16, borderBottom: "1px solid #f0effe", paddingBottom: 8 }}>
      <span style={{ color: "#6b6b8a" }}>{label}</span>
      <span style={{ color: danger ? "#991b1b" : "#374151", fontWeight: 600, textAlign: "right", overflowWrap: "anywhere" }}>{value}</span>
    </div>
  );
}

function Badge({ children, color }) {
  return (
    <span style={{ background: `${color}14`, color, border: `1px solid ${color}30`, borderRadius: 999, padding: "4px 9px", fontSize: 10, fontWeight: 850, whiteSpace: "nowrap" }}>
      {children}
    </span>
  );
}

const primaryBtn = { background: C, color: "#fff", border: "none", borderRadius: 12, padding: "11px 16px", cursor: "pointer", fontWeight: 850, minHeight: 44 };
const secondaryBtn = { background: "#fff", color: C, border: `1px solid ${C}30`, borderRadius: 12, padding: "11px 16px", cursor: "pointer", fontWeight: 800, minHeight: 44 };
const miniBtn = { border: `1px solid ${C}25`, borderRadius: 8, background: `${C}08`, color: C, padding: "6px 12px", cursor: "pointer", fontWeight: 800, fontSize: 12 };
const alertStyle = { background: "#fef2f2", color: "#991b1b", border: "1px solid #fecaca", borderRadius: 14, padding: "12px 14px", marginBottom: 16, fontSize: 13 };
const noticeOk = { background: "#eef2ff", color: "#3730a3", border: "1px solid #c7d2fe", borderRadius: 14, padding: "12px 14px", marginBottom: 16, fontSize: 13 };
const noticeStyle = { marginTop: 16, background: "#fffbeb", border: "1px solid #fde68a", color: "#92400e", padding: 14, borderRadius: 12, lineHeight: 1.6, fontSize: 13 };
