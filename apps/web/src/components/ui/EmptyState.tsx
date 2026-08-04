import { DatabaseZap } from 'lucide-react';

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="empty-state">
      <DatabaseZap size={20} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
