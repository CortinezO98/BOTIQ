import { useEffect, useState } from "react";
import Navbar from "../components/Layout/Navbar";
import { adminAPI } from "../services/api";

const C = "#272163";
const CH = "var(--botiq-heading)"; // texto/headings: sí se adapta a modo oscuro (C se mantiene fijo por los patrones ${C}XX de alpha-transparencia)

const initialForm = {
  email: "",
  full_name: "",
  password: "",
  role: "employee",
};

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState({ full_name: "", password: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadUsers = async () => {
    setLoading(true);
    setError("");

    try {
      const { data } = await adminAPI.listUsers();
      setUsers(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error cargando usuarios");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const createUser = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      await adminAPI.createUser(form);
      setForm(initialForm);
      await loadUsers();
    } catch (err) {
      setError(err.response?.data?.detail || "Error creando usuario");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (user) => {
    setEditing(user.id);
    setEditForm({ full_name: user.full_name, password: "" });
  };

  const updateUser = async (id) => {
    setSaving(true);
    setError("");

    try {
      const payload = { full_name: editForm.full_name };
      if (editForm.password.trim()) payload.password = editForm.password;

      await adminAPI.updateUser(id, payload);
      setEditing(null);
      setEditForm({ full_name: "", password: "" });
      await loadUsers();
    } catch (err) {
      setError(err.response?.data?.detail || "Error actualizando usuario");
    } finally {
      setSaving(false);
    }
  };

  const changeRole = async (id, role) => {
    setError("");

    try {
      await adminAPI.changeRole(id, role);
      await loadUsers();
    } catch (err) {
      setError(err.response?.data?.detail || "Error cambiando rol");
    }
  };

  const toggleStatus = async (user) => {
    setError("");

    try {
      if (user.is_active) await adminAPI.disableUser(user.id);
      else await adminAPI.enableUser(user.id);

      await loadUsers();
    } catch (err) {
      setError(err.response?.data?.detail || "Error cambiando estado");
    }
  };

  return (
    <div className="botiq-page botiq-admin-page">
      <Navbar currentPage="users" />

      <main className="botiq-page-main">
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ color: CH, fontSize: 24, margin: 0 }}>Gestión de usuarios</h1>
          <p style={{ color: "var(--botiq-muted)", marginTop: 6, fontSize: 13 }}>
            Crea usuarios, cambia roles y administra accesos de BOTIQ.
          </p>
        </header>

        {error && (
          <div style={alertStyle}>
            ⚠️ {error}
          </div>
        )}

        <section style={cardStyle}>
          <h2 style={sectionTitle}>Crear usuario</h2>

          <form onSubmit={createUser} style={formGrid}>
            <Input
              label="Email"
              type="email"
              value={form.email}
              onChange={(v) => setForm({ ...form, email: v })}
              required
            />

            <Input
              label="Nombre completo"
              value={form.full_name}
              onChange={(v) => setForm({ ...form, full_name: v })}
              required
            />

            <Input
              label="Contraseña"
              type="password"
              value={form.password}
              onChange={(v) => setForm({ ...form, password: v })}
              required
            />

            <label style={labelStyle}>
              Rol
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                style={inputStyle}
              >
                <option value="employee">Empleado</option>
                <option value="support_engineer">Ing. Soporte</option>
                <option value="admin">Administrador</option>
              </select>
            </label>

            <button disabled={saving} type="submit" style={primaryBtn}>
              {saving ? "Guardando..." : "Crear usuario"}
            </button>
          </form>
        </section>

        <section style={cardStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 style={sectionTitle}>Usuarios registrados</h2>
            <button onClick={loadUsers} style={secondaryBtn}>🔄 Actualizar</button>
          </div>

          {loading ? (
            <p style={{ color: "var(--botiq-muted)" }}>Cargando usuarios...</p>
          ) : (
            <>
              {/* Escritorio: tabla */}
              <div className="botiq-desktop-only" style={{ overflowX: "auto" }}>
                <table style={tableStyle}>
                <thead>
                  <tr>
                    <Th>Nombre</Th>
                    <Th>Email</Th>
                    <Th>Rol</Th>
                    <Th>Estado</Th>
                    <Th>Creado</Th>
                    <Th>Acciones</Th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <Td>
                        {editing === user.id ? (
                          <input
                            value={editForm.full_name}
                            onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                            style={inputStyle}
                          />
                        ) : (
                          user.full_name
                        )}
                      </Td>

                      <Td>{user.email}</Td>

                      <Td>
                        <select
                          value={user.role}
                          onChange={(e) => changeRole(user.id, e.target.value)}
                          style={{ ...inputStyle, minWidth: 150 }}
                        >
                          <option value="employee">Empleado</option>
                          <option value="support_engineer">Ing. Soporte</option>
                          <option value="admin">Administrador</option>
                        </select>
                      </Td>

                      <Td>
                        <span style={{
                          ...badgeStyle,
                          background: user.is_active ? "#dcfce7" : "#fee2e2",
                          color: user.is_active ? "#166534" : "#991b1b",
                        }}>
                          {user.is_active ? "Activo" : "Inactivo"}
                        </span>
                      </Td>

                      <Td>{new Date(user.created_at).toLocaleDateString()}</Td>

                      <Td>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          {editing === user.id ? (
                            <>
                              <input
                                placeholder="Nueva contraseña opcional"
                                type="password"
                                value={editForm.password}
                                onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                                style={{ ...inputStyle, minWidth: 190 }}
                              />
                              <button onClick={() => updateUser(user.id)} style={smallPrimaryBtn}>
                                Guardar
                              </button>
                              <button onClick={() => setEditing(null)} style={smallSecondaryBtn}>
                                Cancelar
                              </button>
                            </>
                          ) : (
                            <>
                              <button onClick={() => startEdit(user)} style={smallSecondaryBtn}>
                                Editar
                              </button>
                              <button
                                onClick={() => toggleStatus(user)}
                                style={{
                                  ...smallSecondaryBtn,
                                  color: user.is_active ? "#991b1b" : "#166534",
                                }}
                              >
                                {user.is_active ? "Desactivar" : "Activar"}
                              </button>
                            </>
                          )}
                        </div>
                      </Td>
                    </tr>
                  ))}
                </tbody>
                </table>
              </div>

              {/* Móvil: tarjetas claymorphism */}
              <div className="botiq-mobile-only">
                <div style={{ display: "grid", gap: 12 }}>
                  {users.map((user) => (
                    <UserCard
                      key={user.id}
                      user={user}
                      editing={editing === user.id}
                      editForm={editForm}
                      setEditForm={setEditForm}
                      onStartEdit={() => startEdit(user)}
                      onCancelEdit={() => setEditing(null)}
                      onSave={() => updateUser(user.id)}
                      onChangeRole={(role) => changeRole(user.id, role)}
                      onToggleStatus={() => toggleStatus(user)}
                    />
                  ))}
                </div>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function UserCard({ user, editing, editForm, setEditForm, onStartEdit, onCancelEdit, onSave, onChangeRole, onToggleStatus }) {
  return (
    <article className="botiq-clay-surface" style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, marginBottom: 8 }}>
        <div style={{ minWidth: 0 }}>
          {editing ? (
            <input
              value={editForm.full_name}
              onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
              style={{ ...inputStyle, marginBottom: 4 }}
            />
          ) : (
            <h3 style={{ color: CH, fontSize: 14, margin: 0, overflowWrap: "anywhere" }}>{user.full_name}</h3>
          )}
          <p style={{ color: "var(--botiq-muted)", fontSize: 12, margin: "4px 0 0", overflowWrap: "anywhere" }}>{user.email}</p>
        </div>
        <span
          className={`botiq-clay-chip botiq-clay-chip--${user.is_active ? "success" : "danger"}`}
          style={{ flexShrink: 0 }}
        >
          {user.is_active ? "Activo" : "Inactivo"}
        </span>
      </div>

      <label style={{ ...labelStyle, marginTop: 10 }}>
        Rol
        <select value={user.role} onChange={(e) => onChangeRole(e.target.value)} style={inputStyle}>
          <option value="employee">Empleado</option>
          <option value="support_engineer">Ing. Soporte</option>
          <option value="admin">Administrador</option>
        </select>
      </label>

      <p style={{ color: "#9ca3af", fontSize: 11, marginTop: 10 }}>
        Creado el {new Date(user.created_at).toLocaleDateString()}
      </p>

      {editing && (
        <input
          placeholder="Nueva contraseña opcional"
          type="password"
          value={editForm.password}
          onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
          style={{ ...inputStyle, marginTop: 10 }}
        />
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        {editing ? (
          <>
            <button onClick={onSave} style={{ ...smallPrimaryBtn, flex: 1 }}>Guardar</button>
            <button onClick={onCancelEdit} style={{ ...smallSecondaryBtn, flex: 1 }}>Cancelar</button>
          </>
        ) : (
          <>
            <button onClick={onStartEdit} style={{ ...smallSecondaryBtn, flex: 1 }}>Editar</button>
            <button
              onClick={onToggleStatus}
              style={{ ...smallSecondaryBtn, flex: 1, color: user.is_active ? "#991b1b" : "#166534" }}
            >
              {user.is_active ? "Desactivar" : "Activar"}
            </button>
          </>
        )}
      </div>
    </article>
  );
}
function Input({ label, value, onChange, type = "text", required = false }) {
  return (
    <label style={labelStyle}>
      {label}
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle}
      />
    </label>
  );
}

function Th({ children }) {
  return <th style={thStyle}>{children}</th>;
}

function Td({ children }) {
  return <td style={tdStyle}>{children}</td>;
}

const cardStyle = {
  background: "var(--botiq-card-bg)",
  border: "1px solid var(--botiq-border)",
  borderRadius: 14,
  padding: 22,
  marginBottom: 22,
  boxShadow: "0 1px 4px rgba(39,33,99,0.06)",
};

const sectionTitle = {
  color: CH,
  fontSize: 16,
  margin: "0 0 16px",
};

const formGrid = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 14,
  alignItems: "end",
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
  border: "1px solid var(--botiq-border)",
  borderRadius: 8,
  padding: "9px 10px",
  fontSize: 13,
  outline: "none",
  background: "var(--botiq-card-bg)",
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
  background: "var(--botiq-surface)",
  color: CH,
  border: "1px solid var(--botiq-border)",
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

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
};

const thStyle = {
  textAlign: "left",
  color: CH,
  borderBottom: "1px solid var(--botiq-border)",
  padding: "10px 8px",
  whiteSpace: "nowrap",
};

const tdStyle = {
  borderBottom: "1px solid #f0effe",
  padding: "10px 8px",
  color: "#374151",
  verticalAlign: "middle",
};

const badgeStyle = {
  display: "inline-block",
  borderRadius: 999,
  padding: "3px 9px",
  fontSize: 11,
  fontWeight: 700,
};
