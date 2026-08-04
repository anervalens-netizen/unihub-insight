const currency = new Intl.NumberFormat('ro-RO', {
  style: 'currency',
  currency: 'RON',
  maximumFractionDigits: 0,
});

const compactCurrency = new Intl.NumberFormat('ro-RO', {
  style: 'currency',
  currency: 'RON',
  notation: 'compact',
  maximumFractionDigits: 1,
});

const integer = new Intl.NumberFormat('ro-RO', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('ro-RO', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 2,
});

export function formatCurrency(value: number, compact = false): string {
  return (compact ? compactCurrency : currency).format(value);
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return `${value.toLocaleString('ro-RO', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`;
}

export function formatInteger(value: number): string {
  return integer.format(value);
}

export function formatDecimal(value: number): string {
  return decimal.format(value);
}

export function formatDate(value: string | null): string {
  if (!value) return 'Fără cutoff';
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return value;
  return new Intl.DateTimeFormat('ro-RO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(year, month - 1, day));
}

export function formatMonth(value: string): string {
  const [year, month] = value.split('-').map(Number);
  if (!year || !month) return value;
  return new Intl.DateTimeFormat('ro-RO', {
    month: 'long',
    year: 'numeric',
  }).format(new Date(year, month - 1, 1));
}
