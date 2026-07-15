import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

const ToastContext = createContext(null);

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback(({ title, message = "", tone = "info", duration = 4500 }) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((current) => [...current, { id, title, message, tone }]);

    if (duration > 0) {
      window.setTimeout(() => dismiss(id), duration);
    }

    return id;
  }, [dismiss]);

  const value = useMemo(() => ({ notify, dismiss }), [notify, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}

      <div className="botiq-toast-viewport" aria-live="polite" aria-atomic="false">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.tone] || Info;
          return (
            <article key={toast.id} className={`botiq-toast botiq-toast--${toast.tone}`}>
              <Icon className="botiq-toast__icon" size={20} aria-hidden="true" />
              <div>
                <h3 className="botiq-toast__title">{toast.title}</h3>
                {toast.message && <p className="botiq-toast__message">{toast.message}</p>}
              </div>
              <button
                type="button"
                className="botiq-ui-button botiq-ui-button--ghost botiq-ui-button--icon"
                onClick={() => dismiss(toast.id)}
                aria-label="Cerrar notificación"
              >
                <X size={17} aria-hidden="true" />
              </button>
            </article>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast() debe usarse dentro de <ToastProvider>.");
  }
  return context;
}
