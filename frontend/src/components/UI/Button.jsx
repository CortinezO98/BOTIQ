import { LoaderCircle } from "lucide-react";

export default function Button({
  children,
  variant = "secondary",
  icon: Icon,
  loading = false,
  disabled = false,
  className = "",
  type = "button",
  ...props
}) {
  const iconOnly = !children;

  return (
    <button
      type={type}
      className={[
        "botiq-ui-button",
        `botiq-ui-button--${variant}`,
        iconOnly ? "botiq-ui-button--icon" : "",
        className,
      ].filter(Boolean).join(" ")}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading
        ? <LoaderCircle className="botiq-ui-button__spinner" size={18} aria-hidden="true" />
        : Icon
          ? <Icon size={18} aria-hidden="true" />
          : null}
      {children && <span>{children}</span>}
    </button>
  );
}
