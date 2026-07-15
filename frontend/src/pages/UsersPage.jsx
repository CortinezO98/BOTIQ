import { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Edit3,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UserCheck,
  UserCog,
  UserRound,
  UserRoundX,
  Users,
  X,
} from "lucide-react";

import AppShell from "../components/Layout/AppShell";
import { adminAPI, downloadCsvFromRows } from "../services/api";
import "../components/Users/users.css";

const ROLE_OPTIONS = [
  { value: "employee", label: "Empleado", short: "EMP" },
  { value: "support_engineer", label: "Ing. Soporte", short: "SOP" },
  { value: "admin", label: "Administrador", short: "ADM" },
];

const EMPTY_CREATE_FORM = {
  email: "",
  full_name: "",
  password: "",
  role: "employee",
};

const EMPTY_EDIT_FORM = {
  full_name: "",
  password: "",
};

const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyUserId, setBusyUserId] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [mfaFilter, setMfaFilter] = useState("all");
  const [sortBy, setSortBy] = useState("newest");
  const [pageSize, setPageSize] = useState(10);
  const [page, setPage] = useState(1);

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_CREATE_FORM);
  const [showCreatePassword, setShowCreatePassword] = useState(false);

  const [editUser, setEditUser] = useState(null);
  const [editForm, setEditForm] = useState(EMPTY_EDIT_FORM);
  const [showEditPassword, setShowEditPassword] = useState(false);

  const [detailUser, setDetailUser] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);
  const [openMenuId, setOpenMenuId] = useState("");

  const loadUsers = async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    setMessage(null);

    try {
      const { data } = await adminAPI.listUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible cargar los usuarios.",
      });
    } finally {
      if (!quiet) setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  useEffect(() => {
    setPage(1);
  }, [query, roleFilter, statusFilter, mfaFilter, sortBy, pageSize]);

  useEffect(() => {
    const closeMenu = () => setOpenMenuId("");
    window.addEventListener("click", closeMenu);
    return () => window.removeEventListener("click", closeMenu);
  }, []);

  const metrics = useMemo(() => {
    const active = users.filter((user) => user.is_active).length;
    const inactive = users.length - active;
    const admins = users.filter((user) => user.role === "admin").length;
    const support = users.filter((user) => user.role === "support_engineer").length;
    const mfa = users.filter((user) => user.mfa_enabled).length;

    return {
      total: users.length,
      active,
      inactive,
      admins,
      support,
      mfa,
    };
  }, [users]);

  const filteredUsers = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    const result = users.filter((user) => {
      const matchesQuery =
        !normalizedQuery ||
        user.full_name?.toLowerCase().includes(normalizedQuery) ||
        user.email?.toLowerCase().includes(normalizedQuery);

      const matchesRole = roleFilter === "all" || user.role === roleFilter;
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && user.is_active) ||
        (statusFilter === "inactive" && !user.is_active);

      const matchesMfa =
        mfaFilter === "all" ||
        (mfaFilter === "enabled" && user.mfa_enabled) ||
        (mfaFilter === "disabled" && !user.mfa_enabled);

      return matchesQuery && matchesRole && matchesStatus && matchesMfa;
    });

    return [...result].sort((a, b) => {
      if (sortBy === "name_asc") {
        return (a.full_name || "").localeCompare(b.full_name || "", "es");
      }
      if (sortBy === "name_desc") {
        return (b.full_name || "").localeCompare(a.full_name || "", "es");
      }
      if (sortBy === "oldest") {
        return new Date(a.created_at || 0) - new Date(b.created_at || 0);
      }
      if (sortBy === "role") {
        return roleLabel(a.role).localeCompare(roleLabel(b.role), "es");
      }
      return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    });
  }, [users, query, roleFilter, statusFilter, mfaFilter, sortBy]);

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * pageSize;
  const pageUsers = filteredUsers.slice(pageStart, pageStart + pageSize);

  const hasFilters =
    query ||
    roleFilter !== "all" ||
    statusFilter !== "all" ||
    mfaFilter !== "all" ||
    sortBy !== "newest";

  const clearFilters = () => {
    setQuery("");
    setRoleFilter("all");
    setStatusFilter("all");
    setMfaFilter("all");
    setSortBy("newest");
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setMessage(null);

    if (passwordScore(createForm.password) < 3) {
      setMessage({
        type: "error",
        text: "La contraseña debe tener al menos 8 caracteres e incluir letras, números y un carácter especial.",
      });
      return;
    }

    setSaving(true);

    try {
      await adminAPI.createUser({
        ...createForm,
        email: createForm.email.trim().toLowerCase(),
        full_name: createForm.full_name.trim(),
      });
      setCreateForm(EMPTY_CREATE_FORM);
      setCreateOpen(false);
      setMessage({ type: "success", text: "Usuario creado correctamente." });
      await loadUsers({ quiet: true });
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible crear el usuario.",
      });
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (user) => {
    setOpenMenuId("");
    setEditUser(user);
    setEditForm({ full_name: user.full_name || "", password: "" });
    setShowEditPassword(false);
  };

  const handleEdit = async (event) => {
    event.preventDefault();
    if (!editUser) return;

    const payload = { full_name: editForm.full_name.trim() };

    if (editForm.password.trim()) {
      if (passwordScore(editForm.password) < 3) {
        setMessage({
          type: "error",
          text: "La nueva contraseña no cumple el nivel mínimo de seguridad.",
        });
        return;
      }
      payload.password = editForm.password;
    }

    setSaving(true);
    setMessage(null);

    try {
      await adminAPI.updateUser(editUser.id, payload);
      setEditUser(null);
      setEditForm(EMPTY_EDIT_FORM);
      setMessage({ type: "success", text: "Datos del usuario actualizados." });
      await loadUsers({ quiet: true });
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible actualizar el usuario.",
      });
    } finally {
      setSaving(false);
    }
  };

  const requestRoleChange = (user, nextRole) => {
    if (nextRole === user.role) return;

    setConfirmAction({
      type: "role",
      user,
      nextRole,
      title: "Confirmar cambio de rol",
      description: `Se cambiará el rol de ${user.full_name} de ${roleLabel(user.role)} a ${roleLabel(nextRole)}.`,
      confirmLabel: "Cambiar rol",
    });
  };

  const requestStatusChange = (user) => {
    setOpenMenuId("");
    setConfirmAction({
      type: "status",
      user,
      title: user.is_active ? "Desactivar usuario" : "Activar usuario",
      description: user.is_active
        ? `${user.full_name} no podrá iniciar sesión hasta que la cuenta sea activada nuevamente.`
        : `${user.full_name} recuperará el acceso a BOTIQ.`,
      confirmLabel: user.is_active ? "Desactivar" : "Activar",
      danger: user.is_active,
    });
  };

  const executeConfirmedAction = async () => {
    if (!confirmAction) return;

    const { type, user, nextRole } = confirmAction;
    setBusyUserId(user.id);
    setMessage(null);

    try {
      if (type === "role") {
        await adminAPI.changeRole(user.id, nextRole);
        setMessage({ type: "success", text: "Rol actualizado correctamente." });
      }

      if (type === "status") {
        if (user.is_active) await adminAPI.disableUser(user.id);
        else await adminAPI.enableUser(user.id);

        setMessage({
          type: "success",
          text: user.is_active
            ? "Usuario desactivado correctamente."
            : "Usuario activado correctamente.",
        });
      }

      setConfirmAction(null);
      await loadUsers({ quiet: true });
    } catch (error) {
      setMessage({
        type: "error",
        text: error.response?.data?.detail || "No fue posible completar la operación.",
      });
    } finally {
      setBusyUserId("");
    }
  };

  const exportUsers = () => {
    const rows = filteredUsers.map((user) => ({
      Nombre: user.full_name,
      Email: user.email,
      Rol: roleLabel(user.role),
      Estado: user.is_active ? "Activo" : "Inactivo",
      MFA: user.mfa_enabled ? "Activo" : "No configurado",
      Creado: formatDate(user.created_at),
    }));

    if (!rows.length) {
      setMessage({ type: "error", text: "No hay usuarios para exportar." });
      return;
    }

    downloadCsvFromRows(
      rows,
      `usuarios_botiq_${new Date().toISOString().slice(0, 10)}.csv`,
    );
  };

  return (
    <AppShell currentPage="users">
      <main className="botiq-page-main botiq-users-page">
        <PageHeading
          onCreate={() => {
            setMessage(null);
            setCreateForm(EMPTY_CREATE_FORM);
            setCreateOpen(true);
          }}
          onRefresh={() => loadUsers()}
          onExport={exportUsers}
          loading={loading}
        />

        {message && (
          <div
            className={`botiq-users-alert botiq-users-alert--${message.type}`}
            role={message.type === "error" ? "alert" : "status"}
          >
            <span>{message.type === "success" ? "✓" : "!"}</span>
            <p>{message.text}</p>
            <button type="button" onClick={() => setMessage(null)} aria-label="Cerrar mensaje">
              <X size={16} />
            </button>
          </div>
        )}

        <section className="botiq-users-kpis" aria-label="Resumen de usuarios">
          <MetricCard
            icon={Users}
            label="Usuarios totales"
            value={metrics.total}
            caption="Cuentas registradas"
            tone="primary"
          />
          <MetricCard
            icon={UserCheck}
            label="Usuarios activos"
            value={metrics.active}
            caption={`${metrics.inactive} inactivos`}
            tone="success"
          />
          <MetricCard
            icon={UserCog}
            label="Administradores"
            value={metrics.admins}
            caption={`${metrics.support} de soporte`}
            tone="purple"
          />
          <MetricCard
            icon={ShieldCheck}
            label="MFA activo"
            value={metrics.mfa}
            caption={`${Math.round((metrics.mfa / Math.max(metrics.total, 1)) * 100)}% de cobertura`}
            tone="info"
          />
        </section>

        <section className="botiq-users-toolbar" aria-label="Filtros de usuarios">
          <div className="botiq-users-search">
            <Search size={18} aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar por nombre o correo..."
              aria-label="Buscar usuarios"
            />
            {query && (
              <button type="button" onClick={() => setQuery("")} aria-label="Limpiar búsqueda">
                <X size={16} />
              </button>
            )}
          </div>

          <SelectFilter
            icon={Users}
            label="Rol"
            value={roleFilter}
            onChange={setRoleFilter}
            options={[
              { value: "all", label: "Todos los roles" },
              ...ROLE_OPTIONS,
            ]}
          />

          <SelectFilter
            icon={UserCheck}
            label="Estado"
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: "all", label: "Todos los estados" },
              { value: "active", label: "Activos" },
              { value: "inactive", label: "Inactivos" },
            ]}
          />

          <SelectFilter
            icon={LockKeyhole}
            label="MFA"
            value={mfaFilter}
            onChange={setMfaFilter}
            options={[
              { value: "all", label: "Cualquier MFA" },
              { value: "enabled", label: "MFA activo" },
              { value: "disabled", label: "Sin MFA" },
            ]}
          />

          <SelectFilter
            icon={SlidersHorizontal}
            label="Orden"
            value={sortBy}
            onChange={setSortBy}
            options={[
              { value: "newest", label: "Más recientes" },
              { value: "oldest", label: "Más antiguos" },
              { value: "name_asc", label: "Nombre A–Z" },
              { value: "name_desc", label: "Nombre Z–A" },
              { value: "role", label: "Por rol" },
            ]}
          />

          {hasFilters && (
            <button type="button" className="botiq-users-clear" onClick={clearFilters}>
              <X size={16} />
              Limpiar
            </button>
          )}
        </section>

        <section className="botiq-users-panel">
          <header className="botiq-users-panel__header">
            <div>
              <h2>Directorio de usuarios</h2>
              <p>
                Mostrando {pageUsers.length} de {filteredUsers.length} usuarios encontrados.
              </p>
            </div>

            <label className="botiq-users-page-size">
              Mostrar
              <select
                value={pageSize}
                onChange={(event) => setPageSize(Number(event.target.value))}
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>{size}</option>
                ))}
              </select>
            </label>
          </header>

          {loading ? (
            <UsersSkeleton />
          ) : filteredUsers.length === 0 ? (
            <EmptyUsers
              filtered={Boolean(hasFilters)}
              onClear={clearFilters}
              onCreate={() => setCreateOpen(true)}
            />
          ) : (
            <>
              <div className="botiq-desktop-only botiq-users-table-wrap">
                <table className="botiq-users-table">
                  <thead>
                    <tr>
                      <th>Usuario</th>
                      <th>Rol</th>
                      <th>Estado</th>
                      <th>MFA</th>
                      <th>Fecha de creación</th>
                      <th><span className="sr-only">Acciones</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageUsers.map((user) => (
                      <UserTableRow
                        key={user.id}
                        user={user}
                        busy={busyUserId === user.id}
                        menuOpen={openMenuId === user.id}
                        onToggleMenu={(event) => {
                          event.stopPropagation();
                          setOpenMenuId((current) => current === user.id ? "" : user.id);
                        }}
                        onDetail={() => {
                          setOpenMenuId("");
                          setDetailUser(user);
                        }}
                        onEdit={() => openEdit(user)}
                        onRoleChange={(role) => requestRoleChange(user, role)}
                        onStatusChange={() => requestStatusChange(user)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="botiq-mobile-only">
                <div className="botiq-users-mobile-grid">
                  {pageUsers.map((user) => (
                    <UserMobileCard
                      key={user.id}
                      user={user}
                      busy={busyUserId === user.id}
                      onDetail={() => setDetailUser(user)}
                      onEdit={() => openEdit(user)}
                      onRoleChange={(role) => requestRoleChange(user, role)}
                      onStatusChange={() => requestStatusChange(user)}
                    />
                  ))}
                </div>
              </div>

              <Pagination
                page={safePage}
                totalPages={totalPages}
                totalItems={filteredUsers.length}
                pageSize={pageSize}
                onPage={setPage}
              />
            </>
          )}
        </section>

        <UserModal
          open={createOpen}
          title="Crear nuevo usuario"
          description="Registra una cuenta y asigna los permisos iniciales."
          onClose={() => !saving && setCreateOpen(false)}
        >
          <form onSubmit={handleCreate} className="botiq-users-form">
            <Field label="Nombre completo" required>
              <input
                value={createForm.full_name}
                onChange={(event) => setCreateForm({ ...createForm, full_name: event.target.value })}
                placeholder="Ej. Ana Torres"
                minLength={2}
                maxLength={255}
                autoFocus
                required
              />
            </Field>

            <Field label="Correo corporativo" required>
              <input
                type="email"
                value={createForm.email}
                onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })}
                placeholder="usuario@iq-online.com"
                required
              />
            </Field>

            <Field label="Rol inicial" required>
              <select
                value={createForm.role}
                onChange={(event) => setCreateForm({ ...createForm, role: event.target.value })}
              >
                {ROLE_OPTIONS.map((role) => (
                  <option key={role.value} value={role.value}>{role.label}</option>
                ))}
              </select>
            </Field>

            <Field
              label="Contraseña temporal"
              required
              hint="Mínimo 8 caracteres, con letras, números y un carácter especial."
            >
              <PasswordControl
                value={createForm.password}
                onChange={(password) => setCreateForm({ ...createForm, password })}
                visible={showCreatePassword}
                onToggle={() => setShowCreatePassword((value) => !value)}
                onGenerate={() => {
                  const password = generateSecurePassword();
                  setCreateForm({ ...createForm, password });
                  setShowCreatePassword(true);
                }}
                required
              />
              <PasswordStrength password={createForm.password} />
            </Field>

            <div className="botiq-users-modal-actions">
              <button
                type="button"
                className="botiq-users-btn botiq-users-btn--secondary"
                onClick={() => setCreateOpen(false)}
                disabled={saving}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="botiq-users-btn botiq-users-btn--primary"
                disabled={saving}
              >
                {saving ? <RefreshCw className="spin" size={17} /> : <Plus size={17} />}
                {saving ? "Creando..." : "Crear usuario"}
              </button>
            </div>
          </form>
        </UserModal>

        <UserModal
          open={Boolean(editUser)}
          title="Editar usuario"
          description={editUser ? `Actualiza los datos de ${editUser.full_name}.` : ""}
          onClose={() => !saving && setEditUser(null)}
        >
          <form onSubmit={handleEdit} className="botiq-users-form">
            <Field label="Nombre completo" required>
              <input
                value={editForm.full_name}
                onChange={(event) => setEditForm({ ...editForm, full_name: event.target.value })}
                minLength={2}
                maxLength={255}
                required
                autoFocus
              />
            </Field>

            <Field label="Correo">
              <input value={editUser?.email || ""} disabled />
            </Field>

            <Field
              label="Nueva contraseña"
              hint="Déjala vacía para conservar la contraseña actual."
            >
              <PasswordControl
                value={editForm.password}
                onChange={(password) => setEditForm({ ...editForm, password })}
                visible={showEditPassword}
                onToggle={() => setShowEditPassword((value) => !value)}
                onGenerate={() => {
                  const password = generateSecurePassword();
                  setEditForm({ ...editForm, password });
                  setShowEditPassword(true);
                }}
              />
              {editForm.password && <PasswordStrength password={editForm.password} />}
            </Field>

            <div className="botiq-users-modal-actions">
              <button
                type="button"
                className="botiq-users-btn botiq-users-btn--secondary"
                onClick={() => setEditUser(null)}
                disabled={saving}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="botiq-users-btn botiq-users-btn--primary"
                disabled={saving}
              >
                {saving ? <RefreshCw className="spin" size={17} /> : <Check size={17} />}
                {saving ? "Guardando..." : "Guardar cambios"}
              </button>
            </div>
          </form>
        </UserModal>

        <UserModal
          open={Boolean(detailUser)}
          title="Detalle del usuario"
          description="Información general y estado de seguridad."
          onClose={() => setDetailUser(null)}
          compact
        >
          {detailUser && <UserDetail user={detailUser} />}
        </UserModal>

        <UserModal
          open={Boolean(confirmAction)}
          title={confirmAction?.title || "Confirmar operación"}
          description={confirmAction?.description || ""}
          onClose={() => !busyUserId && setConfirmAction(null)}
          compact
        >
          <div className="botiq-users-confirm">
            <div className={`botiq-users-confirm__icon${confirmAction?.danger ? " is-danger" : ""}`}>
              {confirmAction?.danger ? <UserRoundX size={26} /> : <ShieldCheck size={26} />}
            </div>

            <p>Esta operación quedará registrada en la auditoría de BOTIQ.</p>

            <div className="botiq-users-modal-actions">
              <button
                type="button"
                className="botiq-users-btn botiq-users-btn--secondary"
                onClick={() => setConfirmAction(null)}
                disabled={Boolean(busyUserId)}
              >
                Cancelar
              </button>
              <button
                type="button"
                className={`botiq-users-btn ${confirmAction?.danger ? "botiq-users-btn--danger" : "botiq-users-btn--primary"}`}
                onClick={executeConfirmedAction}
                disabled={Boolean(busyUserId)}
              >
                {busyUserId && <RefreshCw className="spin" size={17} />}
                {busyUserId ? "Procesando..." : confirmAction?.confirmLabel}
              </button>
            </div>
          </div>
        </UserModal>
      </main>
    </AppShell>
  );
}

function PageHeading({ onCreate, onRefresh, onExport, loading }) {
  return (
    <header className="botiq-users-heading">
      <div className="botiq-users-heading__main">
        <div className="botiq-users-heading__icon" aria-hidden="true">
          <Users size={26} />
        </div>
        <div>
          <span className="botiq-users-heading__eyebrow">Administración</span>
          <h1>Gestión de usuarios</h1>
          <p>Administra cuentas, permisos, estado de acceso y seguridad de BOTIQ.</p>
        </div>
      </div>

      <div className="botiq-users-heading__actions">
        <button type="button" className="botiq-users-btn botiq-users-btn--secondary" onClick={onExport}>
          <Download size={17} />
          Exportar
        </button>
        <button type="button" className="botiq-users-btn botiq-users-btn--secondary" onClick={onRefresh} disabled={loading}>
          <RefreshCw className={loading ? "spin" : ""} size={17} />
          Actualizar
        </button>
        <button type="button" className="botiq-users-btn botiq-users-btn--primary" onClick={onCreate}>
          <Plus size={17} />
          Nuevo usuario
        </button>
      </div>
    </header>
  );
}

function MetricCard({ icon: Icon, label, value, caption, tone }) {
  return (
    <article className={`botiq-users-kpi botiq-users-kpi--${tone}`}>
      <div className="botiq-users-kpi__icon"><Icon size={21} /></div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <span>{caption}</span>
      </div>
    </article>
  );
}

function SelectFilter({ icon: Icon, label, value, onChange, options }) {
  return (
    <label className="botiq-users-select-filter">
      <Icon size={16} aria-hidden="true" />
      <span className="sr-only">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      <ChevronDown size={15} aria-hidden="true" />
    </label>
  );
}

function UserTableRow({
  user,
  busy,
  menuOpen,
  onToggleMenu,
  onDetail,
  onEdit,
  onRoleChange,
  onStatusChange,
}) {
  return (
    <tr className={!user.is_active ? "is-inactive" : ""}>
      <td>
        <UserIdentity user={user} />
      </td>
      <td>
        <select
          className={`botiq-users-role-select role-${user.role}`}
          value={user.role}
          onChange={(event) => onRoleChange(event.target.value)}
          disabled={busy}
          aria-label={`Cambiar rol de ${user.full_name}`}
        >
          {ROLE_OPTIONS.map((role) => (
            <option key={role.value} value={role.value}>{role.label}</option>
          ))}
        </select>
      </td>
      <td><StatusBadge active={user.is_active} /></td>
      <td><MfaBadge enabled={user.mfa_enabled} /></td>
      <td>
        <span className="botiq-users-date">{formatDate(user.created_at)}</span>
      </td>
      <td>
        <div className="botiq-users-menu-wrap">
          <button
            type="button"
            className="botiq-users-icon-btn"
            onClick={onToggleMenu}
            aria-label={`Acciones para ${user.full_name}`}
            aria-expanded={menuOpen}
          >
            <MoreHorizontal size={19} />
          </button>

          {menuOpen && (
            <div className="botiq-users-menu" onClick={(event) => event.stopPropagation()}>
              <button type="button" onClick={onDetail}>
                <Eye size={16} /> Ver detalle
              </button>
              <button type="button" onClick={onEdit}>
                <Edit3 size={16} /> Editar datos
              </button>
              <button
                type="button"
                className={user.is_active ? "is-danger" : "is-success"}
                onClick={onStatusChange}
              >
                {user.is_active ? <UserRoundX size={16} /> : <UserCheck size={16} />}
                {user.is_active ? "Desactivar" : "Activar"}
              </button>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

function UserMobileCard({ user, busy, onDetail, onEdit, onRoleChange, onStatusChange }) {
  return (
    <article className={`botiq-users-mobile-card${!user.is_active ? " is-inactive" : ""}`}>
      <header>
        <UserIdentity user={user} />
        <StatusBadge active={user.is_active} />
      </header>

      <div className="botiq-users-mobile-card__meta">
        <div>
          <span>Rol</span>
          <select
            className={`botiq-users-role-select role-${user.role}`}
            value={user.role}
            onChange={(event) => onRoleChange(event.target.value)}
            disabled={busy}
          >
            {ROLE_OPTIONS.map((role) => (
              <option key={role.value} value={role.value}>{role.label}</option>
            ))}
          </select>
        </div>
        <div>
          <span>Seguridad</span>
          <MfaBadge enabled={user.mfa_enabled} />
        </div>
        <div>
          <span>Creado</span>
          <strong>{formatDate(user.created_at)}</strong>
        </div>
      </div>

      <footer>
        <button type="button" className="botiq-users-btn botiq-users-btn--secondary" onClick={onDetail}>
          <Eye size={16} /> Detalle
        </button>
        <button type="button" className="botiq-users-btn botiq-users-btn--secondary" onClick={onEdit}>
          <Edit3 size={16} /> Editar
        </button>
        <button
          type="button"
          className={`botiq-users-btn ${user.is_active ? "botiq-users-btn--danger-soft" : "botiq-users-btn--success-soft"}`}
          onClick={onStatusChange}
        >
          {user.is_active ? <UserRoundX size={16} /> : <UserCheck size={16} />}
          {user.is_active ? "Desactivar" : "Activar"}
        </button>
      </footer>
    </article>
  );
}

function UserIdentity({ user }) {
  return (
    <div className="botiq-users-identity">
      <div className={`botiq-users-avatar role-${user.role}`} aria-hidden="true">
        {initials(user.full_name || user.email)}
      </div>
      <div>
        <strong>{user.full_name}</strong>
        <span>{user.email}</span>
      </div>
    </div>
  );
}

function StatusBadge({ active }) {
  return (
    <span className={`botiq-users-badge ${active ? "is-active" : "is-inactive"}`}>
      <i />
      {active ? "Activo" : "Inactivo"}
    </span>
  );
}

function MfaBadge({ enabled }) {
  return (
    <span className={`botiq-users-badge ${enabled ? "is-mfa" : "is-muted"}`}>
      {enabled ? <ShieldCheck size={14} /> : <KeyRound size={14} />}
      {enabled ? "MFA activo" : "Sin MFA"}
    </span>
  );
}

function Pagination({ page, totalPages, totalItems, pageSize, onPage }) {
  const from = totalItems === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, totalItems);

  return (
    <footer className="botiq-users-pagination">
      <p>Mostrando {from}–{to} de {totalItems}</p>
      <div>
        <button
          type="button"
          className="botiq-users-icon-btn"
          onClick={() => onPage(Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="Página anterior"
        >
          <ChevronLeft size={18} />
        </button>

        <span>Página {page} de {totalPages}</span>

        <button
          type="button"
          className="botiq-users-icon-btn"
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

function EmptyUsers({ filtered, onClear, onCreate }) {
  return (
    <div className="botiq-users-empty">
      <div><UserRound size={31} /></div>
      <h3>{filtered ? "No encontramos coincidencias" : "No hay usuarios registrados"}</h3>
      <p>
        {filtered
          ? "Ajusta los filtros o limpia la búsqueda para consultar todo el directorio."
          : "Crea la primera cuenta para comenzar a administrar los accesos."}
      </p>
      <button
        type="button"
        className="botiq-users-btn botiq-users-btn--primary"
        onClick={filtered ? onClear : onCreate}
      >
        {filtered ? <X size={17} /> : <Plus size={17} />}
        {filtered ? "Limpiar filtros" : "Crear usuario"}
      </button>
    </div>
  );
}

function UsersSkeleton() {
  return (
    <div className="botiq-users-skeleton" aria-label="Cargando usuarios">
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

function UserModal({ open, title, description, children, onClose, compact = false }) {
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
      className="botiq-users-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      role="presentation"
    >
      <section
        className={`botiq-users-modal${compact ? " is-compact" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="botiq-users-modal-title"
      >
        <header>
          <div>
            <h2 id="botiq-users-modal-title">{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button type="button" className="botiq-users-icon-btn" onClick={onClose} aria-label="Cerrar">
            <X size={19} />
          </button>
        </header>

        <div className="botiq-users-modal__body">{children}</div>
      </section>
    </div>
  );
}

function Field({ label, hint, required, children }) {
  return (
    <label className="botiq-users-field">
      <span>{label}{required && <b aria-hidden="true"> *</b>}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

function PasswordControl({
  value,
  onChange,
  visible,
  onToggle,
  onGenerate,
  required = false,
}) {
  return (
    <div className="botiq-users-password">
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        minLength={required ? 8 : undefined}
        required={required}
        autoComplete="new-password"
      />
      <button type="button" onClick={onToggle} aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}>
        {visible ? <EyeOff size={17} /> : <Eye size={17} />}
      </button>
      <button type="button" onClick={onGenerate}>Generar</button>
    </div>
  );
}

function PasswordStrength({ password }) {
  const score = passwordScore(password);
  const labels = ["Muy débil", "Débil", "Aceptable", "Buena", "Fuerte"];

  return (
    <div className="botiq-users-strength" data-score={score}>
      <div>
        {Array.from({ length: 4 }).map((_, index) => <i key={index} className={index < score ? "is-filled" : ""} />)}
      </div>
      <span>{password ? labels[score] : "Sin contraseña"}</span>
    </div>
  );
}

function UserDetail({ user }) {
  return (
    <div className="botiq-users-detail">
      <div className="botiq-users-detail__hero">
        <div className={`botiq-users-avatar role-${user.role}`}>
          {initials(user.full_name || user.email)}
        </div>
        <div>
          <h3>{user.full_name}</h3>
          <p>{user.email}</p>
        </div>
      </div>

      <dl>
        <div><dt>Rol</dt><dd>{roleLabel(user.role)}</dd></div>
        <div><dt>Estado</dt><dd><StatusBadge active={user.is_active} /></dd></div>
        <div><dt>Autenticación</dt><dd><MfaBadge enabled={user.mfa_enabled} /></dd></div>
        <div><dt>Fecha de creación</dt><dd>{formatDateTime(user.created_at)}</dd></div>
        <div><dt>Identificador</dt><dd className="is-code">{user.id}</dd></div>
      </dl>

      <div className="botiq-users-detail__notice">
        <LockKeyhole size={18} />
        <p>
          BOTIQ no expone contraseñas ni secretos MFA. Las acciones administrativas
          quedan registradas en auditoría.
        </p>
      </div>
    </div>
  );
}

function roleLabel(role) {
  return ROLE_OPTIONS.find((item) => item.value === role)?.label || role || "Sin rol";
}

function initials(value = "") {
  return value
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "U";
}

function formatDate(value) {
  if (!value) return "Sin fecha";
  return new Intl.DateTimeFormat("es-CO", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function formatDateTime(value) {
  if (!value) return "Sin fecha";
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(value));
}

function passwordScore(password = "") {
  if (!password) return 0;

  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;
  return score;
}

function generateSecurePassword() {
  const lower = "abcdefghijkmnopqrstuvwxyz";
  const upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
  const digits = "23456789";
  const symbols = "!@#$%&*_-+";
  const all = lower + upper + digits + symbols;

  const randomChar = (source) => {
    const array = new Uint32Array(1);
    window.crypto.getRandomValues(array);
    return source[array[0] % source.length];
  };

  const required = [
    randomChar(lower),
    randomChar(upper),
    randomChar(digits),
    randomChar(symbols),
  ];

  while (required.length < 14) required.push(randomChar(all));

  for (let index = required.length - 1; index > 0; index -= 1) {
    const array = new Uint32Array(1);
    window.crypto.getRandomValues(array);
    const swapIndex = array[0] % (index + 1);
    [required[index], required[swapIndex]] = [required[swapIndex], required[index]];
  }

  return required.join("");
}
