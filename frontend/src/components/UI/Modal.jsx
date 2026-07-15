import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import Button from "./Button";

export default function Modal({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  closeLabel = "Cerrar",
}) {
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    const previous = document.activeElement;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose?.();
    };

    document.addEventListener("keydown", onKeyDown);
    requestAnimationFrame(() => dialogRef.current?.focus());

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previous?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="botiq-ui-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <section
        ref={dialogRef}
        className="botiq-ui-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="botiq-modal-title"
        tabIndex={-1}
      >
        <header className="botiq-ui-modal__header">
          <div>
            <h2 id="botiq-modal-title">{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <Button
            variant="ghost"
            icon={X}
            onClick={onClose}
            aria-label={closeLabel}
            title={closeLabel}
          />
        </header>

        <div className="botiq-ui-modal__body">{children}</div>
        {footer && <footer className="botiq-ui-modal__footer">{footer}</footer>}
      </section>
    </div>
  );
}
