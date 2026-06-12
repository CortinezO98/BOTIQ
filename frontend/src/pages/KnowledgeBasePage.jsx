import { useEffect, useState } from "react";
import Navbar from "../components/Layout/Navbar";
import { supportAPI } from "../services/api";

const C = "#272163";

export default function KnowledgeBasePage() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  const loadStatus = async () => {
    setLoading(true);
    setError("");

    try {
      const { data } = await supportAPI.status();
      setStatus(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error consultando estado de base de conocimiento");
    } finally {
      setLoading(false);
    }
  };

  const sync = async () => {
    setSyncing(true);
    setError("");

    try {
      const { data } = await supportAPI.sync();
      alert(data.message || "Sincronización iniciada");
      await loadStatus();
    } catch (err) {
      setError(err.response?.data?.detail || "Error iniciando sincronización");
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  return (
    <div className="botiq-page botiq-admin-page">
      <Navbar currentPage="knowledge-base" />

      <main className="botiq-page-main">
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ color: C, fontSize: 24, margin: 0 }}>Base de conocimiento</h1>
          <p style={{ color: "#6b6b8a", marginTop: 6, fontSize: 13 }}>
            Estado del RAG, Google Drive y documentos indexados en ChromaDB.
          </p>
        </header>

        {error && <div style={alertStyle}>⚠️ {error}</div>}

        {loading ? (
          <section style={cardStyle}>
            <p style={{ color: "#6b6b8a" }}>Cargando estado...</p>
          </section>
        ) : (
          <>
            <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginBottom: 22 }}>
              <Kpi
                label="Estado"
                value={status?.status || "unknown"}
                icon={status?.status === "active" ? "✅" : "⚠️"}
              />
              <Kpi
                label="Chunks indexados"
                value={status?.total_chunks ?? 0}
                icon="📦"
              />
              <Kpi
                label="Google Drive"
                value={status?.drive_configured ? "Conectado" : "No conectado"}
                icon={status?.drive_configured ? "☁️" : "🚫"}
              />
            </section>

            <section style={cardStyle}>
              <h2 style={sectionTitle}>Acciones</h2>

              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <button onClick={sync} disabled={syncing} style={primaryBtn}>
                  {syncing ? "Sincronizando..." : "☁️ Sincronizar Google Drive"}
                </button>

                <button onClick={loadStatus} style={secondaryBtn}>
                  🔄 Actualizar estado
                </button>
              </div>
            </section>

            <section style={cardStyle}>
              <h2 style={sectionTitle}>Detalle técnico</h2>

              <div style={{ display: "grid", gap: 10, color: "#374151", fontSize: 13 }}>
                <Row label="Drive configurado" value={status?.drive_configured ? "Sí" : "No"} />
                <Row label="ID carpeta Drive" value={status?.drive_folder_id || "No configurado"} />
                <Row label="Estado ChromaDB" value={status?.status || "unknown"} />
                <Row label="Total chunks" value={String(status?.total_chunks ?? 0)} />
                {status?.detail && <Row label="Detalle error" value={status.detail} danger />}
              </div>

              {!status?.drive_configured && (
                <div style={noticeStyle}>
                  <strong>Google Drive no está configurado.</strong>
                  <br />
                  Configura <code>GDRIVE_FOLDER_ID</code> en <code>backend/.env</code>, comparte la carpeta con el
                  service account y reinicia el backend.
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function Kpi({ label, value, icon }) {
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: 26, marginBottom: 10 }}>{icon}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color: C }}>{value}</div>
      <div style={{ fontSize: 12, color: "#6b6b8a", marginTop: 4 }}>{label}</div>
    </div>
  );
}

function Row({ label, value, danger = false }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 16, borderBottom: "1px solid #f0effe", paddingBottom: 8 }}>
      <span style={{ color: "#6b6b8a" }}>{label}</span>
      <span style={{ color: danger ? "#991b1b" : "#374151", fontWeight: 600, textAlign: "right" }}>
        {value}
      </span>
    </div>
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

const sectionTitle = {
  color: C,
  fontSize: 16,
  margin: "0 0 16px",
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
  padding: "10px 16px",
  cursor: "pointer",
  fontWeight: 600,
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

const noticeStyle = {
  marginTop: 18,
  background: "#fffbeb",
  border: "1px solid #fde68a",
  color: "#92400e",
  padding: 14,
  borderRadius: 10,
  lineHeight: 1.6,
};