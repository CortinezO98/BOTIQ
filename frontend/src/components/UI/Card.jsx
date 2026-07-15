export default function Card({
  title,
  description,
  actions,
  children,
  className = "",
  bodyClassName = "",
}) {
  return (
    <article className={`botiq-ui-card ${className}`.trim()}>
      {(title || description || actions) && (
        <header className="botiq-ui-card__header">
          <div>
            {title && <h3 className="botiq-ui-card__title">{title}</h3>}
            {description && <p className="botiq-ui-card__description">{description}</p>}
          </div>
          {actions && <div>{actions}</div>}
        </header>
      )}

      <div className={`botiq-ui-card__body ${bodyClassName}`.trim()}>
        {children}
      </div>
    </article>
  );
}
