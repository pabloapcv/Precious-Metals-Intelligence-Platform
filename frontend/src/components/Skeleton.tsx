export function DashboardSkeleton() {
  return (
    <div className="app skeleton-app" aria-busy="true" aria-label="Loading dashboard">
      <div className="skeleton-header">
        <div className="skeleton-block lg" />
        <div className="skeleton-block sm" />
      </div>
      <div className="skeleton-nav" />
      <div className="skeleton-hero" />
      <div className="grid grid-3">
        {[1, 2, 3].map((i) => <div key={i} className="skeleton-card" />)}
      </div>
      <div className="grid grid-2" style={{ marginTop: '1.25rem' }}>
        {[1, 2].map((i) => <div key={i} className="skeleton-card tall" />)}
      </div>
    </div>
  )
}
