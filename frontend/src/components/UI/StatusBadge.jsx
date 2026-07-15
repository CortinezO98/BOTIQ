export default function StatusBadge({
  children,
  tone = "neutral",
  dot = true,
  className = "",
}) {
  return (
    <span className={`botiq-status-badge botiq-status-badge--${tone} ${className}`.trim()}>
      {dot && <span className="botiq-status-badge__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}
