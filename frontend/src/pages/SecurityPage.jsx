import { useMemo, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronRight,
  Clipboard,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  MailCheck,
  RefreshCw,
  Shield,
  ShieldCheck,
  ShieldOff,
  Smartphone,
  Sparkles,
  UserRoundCheck,
  X,
} from "lucide-react";

import AppShell from "../components/Layout/AppShell";
import { authAPI } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import "../components/Security/security.css";

export default function SecurityPage() {
  const { user, syncUser } = useAuth();

  const [setupData, setSetupData] = useState(null);
  const [confirmCode, setConfirmCode] = useState("");
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [showDisableForm, setShowDisableForm] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loadingAction, setLoadingAction] = useState("");
  const [message, setMessage] = useState(null);
  const [copied, setCopied] = useState(false);

  const mfaEnabled = Boolean(user?.mfa_enabled);
  const securityScore = useMemo(() => {
    let score = 45;
    if (mfaEnabled) score += 45;
    if (user?.is_active !== false) score += 10;
    return Math.min(score, 100);
  }, [mfaEnabled, user?.is_active]);

  const startSetup = async () => {
    setLoadingAction("setup");
    setMessage(null);

    try {
      const { data } = await authAPI.mfaSetup();
      setSetupData(data);
      setConfirmCode("");
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No se pudo iniciar la configuración de MFA.",
      });
    } finally {
      setLoadingAction("");
    }
  };

  const cancelSetup = () => {
    setSetupData(null);
    setConfirmCode("");
    setCopied(false);
    setMessage(null);
  };

  const confirmSetup = async (event) => {
    event.preventDefault();

    if (confirmCode.length !== 6) return;

    setLoadingAction("confirm");
    setMessage(null);

    try {
      await authAPI.mfaConfirm(confirmCode.trim());
      setSetupData(null);
      setConfirmCode("");
      setCopied(false);
      setMessage({
        type: "success",
        text:
          "MFA fue activado correctamente. En tu próximo inicio de sesión se solicitará un código temporal.",
      });
      await syncUser();
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "El código no es válido. Verifica la hora del dispositivo e inténtalo nuevamente.",
      });
    } finally {
      setLoadingAction("");
    }
  };

  const disableMfa = async (event) => {
    event.preventDefault();

    if (!disablePassword || disableCode.length !== 6) return;

    setLoadingAction("disable");
    setMessage(null);

    try {
      await authAPI.mfaDisable(disablePassword, disableCode.trim());
      setShowDisableForm(false);
      setDisablePassword("");
      setDisableCode("");
      setShowPassword(false);
      setMessage({
        type: "success",
        text:
          "MFA fue desactivado. Tu cuenta volverá a depender únicamente de la contraseña.",
      });
      await syncUser();
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error.response?.data?.detail ||
          "No se pudo desactivar MFA. Verifica la contraseña y el código temporal.",
      });
    } finally {
      setLoadingAction("");
    }
  };

  const cancelDisable = () => {
    setShowDisableForm(false);
    setDisablePassword("");
    setDisableCode("");
    setShowPassword(false);
    setMessage(null);
  };

  const copySecret = async () => {
    if (!setupData?.secret) return;

    try {
      await navigator.clipboard.writeText(setupData.secret);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setMessage({
        type: "error",
        text: "No fue posible copiar la clave. Selecciónala manualmente.",
      });
    }
  };

  return (
    <AppShell currentPage="security">
      <main className="botiq-page-main botiq-security-page">
        <PageHeading mfaEnabled={mfaEnabled} />

        {message && (
          <Alert
            type={message.type}
            text={message.text}
            onClose={() => setMessage(null)}
          />
        )}

        <section className="botiq-security-kpis" aria-label="Resumen de seguridad">
          <MetricCard
            icon={ShieldCheck}
            label="Nivel de protección"
            value={`${securityScore}%`}
            caption={
              mfaEnabled
                ? "Cuenta reforzada con MFA"
                : "Activa MFA para mejorar la protección"
            }
            tone={mfaEnabled ? "success" : "warning"}
          />

          <MetricCard
            icon={Smartphone}
            label="Segundo factor"
            value={mfaEnabled ? "Activo" : "Inactivo"}
            caption="Aplicación de autenticación TOTP"
            tone={mfaEnabled ? "success" : "neutral"}
          />

          <MetricCard
            icon={UserRoundCheck}
            label="Cuenta"
            value={user?.is_active === false ? "Inactiva" : "Activa"}
            caption={user?.email || "Administrador"}
            tone={user?.is_active === false ? "danger" : "info"}
          />
        </section>

        <section className="botiq-security-layout">
          <article className="botiq-security-main-card">
            <header className="botiq-security-main-card__header">
              <div className="botiq-security-main-card__title">
                <div
                  className={`botiq-security-main-card__icon ${
                    mfaEnabled ? "is-enabled" : "is-disabled"
                  }`}
                >
                  {mfaEnabled ? (
                    <ShieldCheck size={25} />
                  ) : (
                    <ShieldOff size={25} />
                  )}
                </div>

                <div>
                  <span>Autenticación reforzada</span>
                  <h2>Verificación en dos pasos</h2>
                  <p>
                    Protege tu cuenta con un código temporal generado desde una
                    aplicación como Google Authenticator, Microsoft
                    Authenticator o Authy.
                  </p>
                </div>
              </div>

              <StatusBadge enabled={mfaEnabled} />
            </header>

            {!mfaEnabled && !setupData && (
              <InactiveState
                loading={loadingAction === "setup"}
                onStart={startSetup}
              />
            )}

            {!mfaEnabled && setupData && (
              <EnrollmentPanel
                setupData={setupData}
                confirmCode={confirmCode}
                setConfirmCode={setConfirmCode}
                loading={loadingAction === "confirm"}
                copied={copied}
                onCopy={copySecret}
                onSubmit={confirmSetup}
                onCancel={cancelSetup}
              />
            )}

            {mfaEnabled && !showDisableForm && (
              <ActiveState onDisable={() => setShowDisableForm(true)} />
            )}

            {mfaEnabled && showDisableForm && (
              <DisablePanel
                password={disablePassword}
                setPassword={setDisablePassword}
                code={disableCode}
                setCode={setDisableCode}
                showPassword={showPassword}
                setShowPassword={setShowPassword}
                loading={loadingAction === "disable"}
                onSubmit={disableMfa}
                onCancel={cancelDisable}
              />
            )}
          </article>

          <aside className="botiq-security-side">
            <SecurityScoreCard score={securityScore} mfaEnabled={mfaEnabled} />
            <SecurityChecklist mfaEnabled={mfaEnabled} />
          </aside>
        </section>

        <section className="botiq-security-info">
          <header>
            <div>
              <span>Buenas prácticas</span>
              <h2>Protección recomendada</h2>
            </div>
            <Sparkles size={22} />
          </header>

          <div className="botiq-security-info__grid">
            <SecurityTip
              icon={KeyRound}
              title="Contraseña exclusiva"
              text="Usa una contraseña larga y diferente a la de otros servicios."
            />
            <SecurityTip
              icon={Smartphone}
              title="Aplicación protegida"
              text="Configura biometría o PIN en tu aplicación de autenticación."
            />
            <SecurityTip
              icon={MailCheck}
              title="Correo corporativo"
              text="Mantén actualizado y protegido el correo asociado a tu cuenta."
            />
          </div>
        </section>
      </main>
    </AppShell>
  );
}

function PageHeading({ mfaEnabled }) {
  return (
    <header className="botiq-security-heading">
      <div className="botiq-security-heading__main">
        <div className="botiq-security-heading__icon" aria-hidden="true">
          <Shield size={27} />
        </div>

        <div>
          <span className="botiq-security-heading__eyebrow">
            Protección de cuenta
          </span>
          <h1>Seguridad</h1>
          <p>
            Administra la autenticación multifactor y revisa el nivel de
            protección de tu cuenta administrativa.
          </p>
        </div>
      </div>

      <div
        className={`botiq-security-heading__status ${
          mfaEnabled ? "is-enabled" : "is-disabled"
        }`}
      >
        <i />
        {mfaEnabled ? "MFA habilitado" : "MFA pendiente"}
      </div>
    </header>
  );
}

function MetricCard({ icon: Icon, label, value, caption, tone }) {
  return (
    <article className={`botiq-security-kpi botiq-security-kpi--${tone}`}>
      <div className="botiq-security-kpi__icon">
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
      className={`botiq-security-alert botiq-security-alert--${type}`}
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

function StatusBadge({ enabled }) {
  return (
    <span
      className={`botiq-security-status ${
        enabled ? "is-enabled" : "is-disabled"
      }`}
    >
      <i />
      {enabled ? "Activo" : "Inactivo"}
    </span>
  );
}

function InactiveState({ loading, onStart }) {
  return (
    <div className="botiq-security-state">
      <div className="botiq-security-state__visual is-warning">
        <LockKeyhole size={31} />
      </div>

      <div>
        <h3>Tu cuenta aún no utiliza un segundo factor</h3>
        <p>
          Después de activarlo necesitarás tu contraseña y un código de seis
          dígitos para iniciar sesión. Esto reduce significativamente el riesgo
          ante credenciales comprometidas.
        </p>
      </div>

      <button
        type="button"
        className="botiq-security-btn botiq-security-btn--primary"
        onClick={onStart}
        disabled={loading}
      >
        {loading ? (
          <RefreshCw className="spin" size={17} />
        ) : (
          <ShieldCheck size={17} />
        )}
        {loading ? "Preparando configuración..." : "Activar MFA"}
      </button>
    </div>
  );
}

function ActiveState({ onDisable }) {
  return (
    <div className="botiq-security-state">
      <div className="botiq-security-state__visual is-success">
        <ShieldCheck size={31} />
      </div>

      <div>
        <h3>Tu cuenta está protegida con MFA</h3>
        <p>
          Cada inicio de sesión requiere un código temporal adicional. Mantén
          acceso a tu aplicación de autenticación y evita compartir sus
          códigos.
        </p>
      </div>

      <div className="botiq-security-active-actions">
        <div className="botiq-security-active-note">
          <CheckCircle2 size={17} />
          Protección adicional habilitada
        </div>

        <button
          type="button"
          className="botiq-security-btn botiq-security-btn--danger-ghost"
          onClick={onDisable}
        >
          <ShieldOff size={17} />
          Desactivar MFA
        </button>
      </div>
    </div>
  );
}

function EnrollmentPanel({
  setupData,
  confirmCode,
  setConfirmCode,
  loading,
  copied,
  onCopy,
  onSubmit,
  onCancel,
}) {
  return (
    <div className="botiq-security-enrollment">
      <header>
        <div className="botiq-security-step-number">1</div>
        <div>
          <h3>Escanea el código QR</h3>
          <p>
            Abre tu aplicación de autenticación, agrega una nueva cuenta y
            escanea este código.
          </p>
        </div>
      </header>

      <div className="botiq-security-enrollment__grid">
        <div className="botiq-security-qr">
          <div>
            <img
              src={`data:image/png;base64,${setupData.qr_code_base64}`}
              alt="Código QR para configurar MFA"
              width={190}
              height={190}
            />
          </div>
          <span>BOTIQ · Cuenta administrativa</span>
        </div>

        <div className="botiq-security-enrollment__content">
          <section className="botiq-security-manual-key">
            <header>
              <div>
                <span>Alternativa manual</span>
                <h4>Clave de configuración</h4>
              </div>

              <button
                type="button"
                onClick={onCopy}
                aria-label="Copiar clave de configuración"
              >
                {copied ? <Check size={16} /> : <Clipboard size={16} />}
                {copied ? "Copiada" : "Copiar"}
              </button>
            </header>

            <code>{setupData.secret}</code>

            <p>
              Usa esta clave únicamente cuando no puedas escanear el código QR.
              No la compartas ni la guardes en lugares públicos.
            </p>
          </section>

          <form onSubmit={onSubmit} className="botiq-security-confirm-form">
            <header>
              <div className="botiq-security-step-number">2</div>
              <div>
                <h3>Confirma la activación</h3>
                <p>
                  Ingresa el código actual generado por la aplicación para
                  comprobar que quedó configurada correctamente.
                </p>
              </div>
            </header>

            <OtpInput
              value={confirmCode}
              onChange={setConfirmCode}
              label="Código de verificación"
              autoFocus
            />

            <div className="botiq-security-form-actions">
              <button
                type="submit"
                className="botiq-security-btn botiq-security-btn--primary"
                disabled={loading || confirmCode.length !== 6}
              >
                {loading ? (
                  <RefreshCw className="spin" size={17} />
                ) : (
                  <ShieldCheck size={17} />
                )}
                {loading ? "Verificando..." : "Confirmar y activar"}
              </button>

              <button
                type="button"
                className="botiq-security-btn botiq-security-btn--secondary"
                onClick={onCancel}
                disabled={loading}
              >
                Cancelar
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function DisablePanel({
  password,
  setPassword,
  code,
  setCode,
  showPassword,
  setShowPassword,
  loading,
  onSubmit,
  onCancel,
}) {
  return (
    <form onSubmit={onSubmit} className="botiq-security-disable-panel">
      <header>
        <div className="botiq-security-disable-panel__icon">
          <AlertCircle size={24} />
        </div>
        <div>
          <h3>Confirmar desactivación de MFA</h3>
          <p>
            Esta acción reduce la protección de tu cuenta. Para continuar,
            confirma tu identidad con la contraseña y un código vigente.
          </p>
        </div>
      </header>

      <div className="botiq-security-disable-panel__fields">
        <label className="botiq-security-field">
          <span>Contraseña actual</span>
          <div className="botiq-security-input">
            <KeyRound size={17} />
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Ingresa tu contraseña"
              autoComplete="current-password"
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={
                showPassword ? "Ocultar contraseña" : "Mostrar contraseña"
              }
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </label>

        <OtpInput
          value={code}
          onChange={setCode}
          label="Código de verificación"
        />
      </div>

      <div className="botiq-security-form-actions">
        <button
          type="submit"
          className="botiq-security-btn botiq-security-btn--danger"
          disabled={loading || !password || code.length !== 6}
        >
          {loading ? (
            <RefreshCw className="spin" size={17} />
          ) : (
            <ShieldOff size={17} />
          )}
          {loading ? "Desactivando..." : "Confirmar desactivación"}
        </button>

        <button
          type="button"
          className="botiq-security-btn botiq-security-btn--secondary"
          onClick={onCancel}
          disabled={loading}
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}

function OtpInput({ value, onChange, label, autoFocus = false }) {
  return (
    <label className="botiq-security-field">
      <span>{label}</span>
      <div className="botiq-security-input botiq-security-input--otp">
        <Smartphone size={17} />
        <input
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={value}
          onChange={(event) => onChange(event.target.value.replace(/\D/g, ""))}
          placeholder="000000"
          autoFocus={autoFocus}
          aria-label={label}
          required
        />
        <small>{value.length}/6</small>
      </div>
    </label>
  );
}

function SecurityScoreCard({ score, mfaEnabled }) {
  return (
    <article className="botiq-security-score-card">
      <header>
        <div>
          <span>Evaluación actual</span>
          <h2>Nivel de seguridad</h2>
        </div>
        <ShieldCheck size={22} />
      </header>

      <div className="botiq-security-score-card__body">
        <div
          className="botiq-security-score-ring"
          style={{ "--security-progress": `${score * 3.6}deg` }}
        >
          <div>
            <strong>{score}%</strong>
            <span>{mfaEnabled ? "Protegida" : "Mejorable"}</span>
          </div>
        </div>

        <p>
          {mfaEnabled
            ? "Tu cuenta cumple la recomendación principal de seguridad para administradores."
            : "Activa MFA para elevar significativamente la protección de la cuenta."}
        </p>
      </div>
    </article>
  );
}

function SecurityChecklist({ mfaEnabled }) {
  const items = [
    {
      label: "Cuenta administrativa activa",
      completed: true,
    },
    {
      label: "Contraseña obligatoria",
      completed: true,
    },
    {
      label: "Segundo factor TOTP",
      completed: mfaEnabled,
    },
  ];

  return (
    <article className="botiq-security-checklist">
      <header>
        <div>
          <span>Estado de controles</span>
          <h2>Lista de protección</h2>
        </div>
      </header>

      <div>
        {items.map((item) => (
          <div key={item.label}>
            <span
              className={
                item.completed ? "is-completed" : "is-pending"
              }
            >
              {item.completed ? <Check size={15} /> : <ChevronRight size={15} />}
            </span>
            <p>{item.label}</p>
            <strong>{item.completed ? "Cumplido" : "Pendiente"}</strong>
          </div>
        ))}
      </div>
    </article>
  );
}

function SecurityTip({ icon: Icon, title, text }) {
  return (
    <article className="botiq-security-tip">
      <div>
        <Icon size={19} />
      </div>
      <section>
        <h3>{title}</h3>
        <p>{text}</p>
      </section>
    </article>
  );
}
