/**
 * Skeleton loader claymorphism: superficie gris suave (sin bordes duros,
 * como pide el backlog de UX) con un shimmer sutil mientras carga.
 *
 * Uso:
 *   <Skeleton height={20} width="60%" />                 // línea de texto
 *   <SkeletonKpiRow count={4} />                          // fila de KPIs
 *   <SkeletonCard lines={3} />                             // card genérica
 */
export function Skeleton({ width = "100%", height = 16, radius = 10, style = {} }) {
  return (
    <div
      className="botiq-skeleton"
      style={{ width, height, borderRadius: radius, ...style }}
    />
  );
}

export function SkeletonKpiRow({ count = 4 }) {
  return (
    <div
      className="botiq-kpi-row"
      style={{ marginBottom: 16 }}
      aria-busy="true"
      aria-label="Cargando indicadores"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="botiq-clay-surface" style={{ padding: 16 }}>
          <Skeleton height={11} width="60%" style={{ marginBottom: 10 }} />
          <Skeleton height={24} width="40%" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="botiq-clay-surface" style={{ padding: 16 }} aria-busy="true">
      <Skeleton height={14} width="45%" style={{ marginBottom: 14 }} />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height={12} width={i === lines - 1 ? "70%" : "100%"} style={{ marginBottom: 8 }} />
      ))}
    </div>
  );
}
