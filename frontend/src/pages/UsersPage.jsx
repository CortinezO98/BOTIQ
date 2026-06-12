import { useEffect, useState } from "react";
import Navbar from "../components/Layout/Navbar";
import { adminAPI } from "../services/api";

const C = "#272163";

const ROLE_LABELS = {
  admin: "Administrador",
  support_engineer: "Ing. Soporte",
  employee: "Empleado",
};

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
          <h1 style={{ color: C, fontSize: 24, margin: 0 }}>Gestión de usuarios</h1>
          <p style={{ color: "#6b6b8a", marginTop: 6, fontSize: 13 }}>
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
            <p style={{ color: "#6b6b8a" }}>Cargando usuarios...</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
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
          )}
        </section>
      </main>
    </div>
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

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
};

const thStyle = {
  textAlign: "left",
  color: C,
  borderBottom: "1px solid #e2e1f0",
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

