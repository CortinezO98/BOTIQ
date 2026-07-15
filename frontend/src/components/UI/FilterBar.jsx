export default function FilterBar({ children, className = "" }) {
  return (
    <section className={`botiq-filter-bar ${className}`.trim()} aria-label="Filtros">
      {children}
    </section>
  );
}
