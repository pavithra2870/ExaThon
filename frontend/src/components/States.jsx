export function Skeleton({ height = 16, width = "100%", label = "Loading" }) {
  return <div className="skeleton" style={{ height, width }} role="status" aria-label={label} />;
}

export function SkeletonBlock({ lines = 3 }) {
  return (
    <div className="skeleton-block" role="status" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton" style={{ height: 14, width: `${90 - i * 15}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <p className="state-title">{error?.message ?? "Something went wrong."}</p>
      {error?.hint && <p className="state-hint">{error.hint}</p>}
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="state">
      <p className="state-title">{title}</p>
      {children && <div className="state-hint">{children}</div>}
    </div>
  );
}

export function NotReady({ ds }) {
  return (
    <EmptyState title={`${ds?.name ?? "This dataset"} has not been processed yet.`}>
      <p>
        From <code>backend/</code>, run <code>python -m pipeline.all --dataset {ds?.id ?? "<id>"}</code>, then reload
        this page.
      </p>
    </EmptyState>
  );
}
