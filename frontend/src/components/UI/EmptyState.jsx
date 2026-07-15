import { Inbox } from "lucide-react";

export default function EmptyState({
  icon: Icon = Inbox,
  title = "No hay datos disponibles",
  description = "Todavía no hay información para mostrar con los filtros seleccionados.",
  action,
  className = "",
}) {
  return (
    <div className={`botiq-empty-state ${className}`.trim()} role="status">
      <div className="botiq-empty-state__content">
        <div className="botiq-empty-state__icon" aria-hidden="true">
          <Icon size={28} strokeWidth={1.9} />
        </div>
        <h3 className="botiq-empty-state__title">{title}</h3>
        <p className="botiq-empty-state__description">{description}</p>
        {action && <div className="botiq-empty-state__action">{action}</div>}
      </div>
    </div>
  );
}
