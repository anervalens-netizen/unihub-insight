export function LoadingState({ label = 'Se încarcă analiza…' }: { label?: string }) {
  return (
    <div className="page-state" role="status" aria-live="polite">
      <div className="loading-orbit" aria-hidden="true" />
      <div>
        <strong>{label}</strong>
        <span>Datele sunt încărcate într-un singur contract coerent.</span>
      </div>
    </div>
  );
}
