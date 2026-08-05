import { FileSpreadsheet, LoaderCircle } from 'lucide-react';
import { useState } from 'react';

import { downloadExcel } from '../../lib/download';

export function ExcelExportButton({
  path,
  params,
  filename,
  label = 'Excel',
  className = 'button button--secondary',
}: {
  path: string;
  params: URLSearchParams;
  filename: string;
  label?: string;
  className?: string;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="excel-export-control">
      <button
        type="button"
        className={className}
        disabled={pending}
        title={error ?? 'Exportă datele cu valori numerice native'}
        onClick={() => {
          setPending(true);
          setError(null);
          void downloadExcel(path, params, filename)
            .catch((reason: unknown) =>
              setError(reason instanceof Error ? reason.message : 'Exportul a eșuat.'),
            )
            .finally(() => setPending(false));
        }}
      >
        {pending ? <LoaderCircle className="spin" size={15} /> : <FileSpreadsheet size={15} />}
        {label}
      </button>
      {error ? <span className="excel-export-error">{error}</span> : null}
    </div>
  );
}
