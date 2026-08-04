import { AlertTriangle, RefreshCw } from 'lucide-react';

export function ErrorState({
  title = 'Analiza nu a putut fi încărcată',
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="page-state page-state--error" role="alert">
      <AlertTriangle size={22} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <span>{message}</span>
      </div>
      {onRetry ? (
        <button type="button" className="button button--secondary" onClick={onRetry}>
          <RefreshCw size={15} />
          Reîncearcă
        </button>
      ) : null}
    </div>
  );
}
