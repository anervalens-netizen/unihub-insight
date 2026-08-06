import { Check, Search, X } from 'lucide-react';
import { useMemo, useState } from 'react';

export interface MultiSearchOption {
  value: string;
  label: string;
  meta?: string;
}

interface MultiSearchSelectProps {
  label: string;
  searchLabel?: string;
  options: readonly MultiSearchOption[];
  selected: readonly string[];
  onChange: (values: string[]) => void;
  disabled?: boolean;
  dataFilterKey?: string;
}

function optionText(option: MultiSearchOption): string {
  return `${option.label} ${option.value} ${option.meta ?? ''}`.toLocaleLowerCase('ro-RO');
}

export function MultiSearchSelect({
  label,
  searchLabel = label,
  options,
  selected,
  onChange,
  disabled = false,
  dataFilterKey,
}: MultiSearchSelectProps) {
  const [search, setSearch] = useState('');
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const normalizedSearch = search.trim().toLocaleLowerCase('ro-RO');
  const filteredOptions = useMemo(
    () => options.filter((option) => optionText(option).includes(normalizedSearch)),
    [normalizedSearch, options],
  );
  const selectedLabels = useMemo(
    () =>
      selected
        .map((value) => options.find((option) => option.value === value)?.label ?? value)
        .filter(Boolean),
    [options, selected],
  );
  const summary =
    selected.length === 0
      ? 'Toate'
      : selected.length === 1
        ? (selectedLabels[0] ?? '1 selectat')
        : `${selected.length} selectate`;

  return (
    <details
      className="filter-popover filter-popover--multi"
      data-filter-key={dataFilterKey}
      name="master-filter-multi"
    >
      <summary aria-label={`${label}: ${summary}`}>
        <span className="filter-summary-label">{label}</span>
        <strong title={selectedLabels.join(', ')}>{summary}</strong>
      </summary>
      <div className="filter-popover-panel multi-select-panel">
        <div className="multi-select-header">
          <span>{selected.length === 0 ? 'Toate' : `${selected.length} selectate`}</span>
          {selected.length > 0 ? (
            <button
              type="button"
              className="multi-select-clear"
              onClick={() => onChange([])}
              aria-label={`Șterge selecția ${label}`}
            >
              Șterge
            </button>
          ) : null}
        </div>
        <label className="filter-search">
          <Search size={14} aria-hidden="true" />
          <input
            value={search}
            disabled={disabled}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={`Caută ${searchLabel.toLocaleLowerCase('ro-RO')}…`}
            aria-label={`Caută ${searchLabel}`}
          />
          {search ? (
            <button
              type="button"
              onClick={() => setSearch('')}
              aria-label={`Șterge căutarea ${label}`}
            >
              <X size={13} />
            </button>
          ) : null}
        </label>
        <button
          type="button"
          className="select-all"
          disabled={disabled || selected.length === 0}
          onClick={() => onChange([])}
        >
          Toate {label.toLocaleLowerCase('ro-RO')}
          {selected.length === 0 ? <Check size={14} aria-hidden="true" /> : null}
        </button>
        <fieldset className="multi-select-options" aria-label={`Opțiuni ${label}`}>
          {filteredOptions.length > 0 ? (
            filteredOptions.map((option) => {
              const checked = selectedSet.has(option.value);
              return (
                <label key={option.value} className="multi-select-option">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() =>
                      onChange(
                        checked
                          ? selected.filter((value) => value !== option.value)
                          : [...selected, option.value],
                      )
                    }
                  />
                  <span>
                    <strong>{option.label}</strong>
                    {option.meta ? <small>{option.meta}</small> : null}
                  </span>
                  {checked ? <Check size={14} aria-hidden="true" /> : null}
                </label>
              );
            })
          ) : (
            <span className="multi-select-empty">
              {options.length === 0 ? 'Nicio opțiune disponibilă.' : 'Niciun rezultat.'}
            </span>
          )}
        </fieldset>
      </div>
    </details>
  );
}
