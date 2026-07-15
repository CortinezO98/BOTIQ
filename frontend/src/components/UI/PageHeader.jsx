export default function PageHeader({
  icon: Icon,
  eyebrow = "BOTIQ",
  title,
  description,
  actions,
  className = "",
}) {
  return (
    <header className={`botiq-page-header ${className}`.trim()}>
      <div className="botiq-page-header__main">
        {Icon && (
          <div className="botiq-page-header__icon" aria-hidden="true">
            <Icon size={24} strokeWidth={2.1} />
          </div>
        )}

        <div className="botiq-page-header__copy">
          {eyebrow && <span className="botiq-page-header__eyebrow">{eyebrow}</span>}
          <h1 className="botiq-page-header__title">{title}</h1>
          {description && (
            <p className="botiq-page-header__description">{description}</p>
          )}
        </div>
      </div>

      {actions && <div className="botiq-page-header__actions">{actions}</div>}
    </header>
  );
}
