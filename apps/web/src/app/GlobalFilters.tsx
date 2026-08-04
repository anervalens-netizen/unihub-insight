import { useQuery } from '@tanstack/react-query';
import { Check, Filter, RotateCcw, Search, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { filterOptionsQuery } from '../features/overview/api';
import type { FilterAgent, FilterStore } from '../features/overview/schemas';
import {
  activeFilterCount,
  currentBusinessMonth,
  parseStoreSelection,
  serializeStoreSelection,
} from '../lib/search';
import { useGlobalSearch, useUpdateGlobalSearch } from './search-hooks';

function matchingStore(
  store: FilterStore,
  firm: string | undefined,
  regional: string | undefined,
  asm: string | undefined,
): boolean {
  return (
    (!firm || store.firm === firm) &&
    (!regional || store.regional === regional) &&
    (!asm || store.asm === asm)
  );
}

function matchingAgent(
  agent: FilterAgent,
  firm: string | undefined,
  regional: string | undefined,
  asm: string | undefined,
  stores: readonly string[],
): boolean {
  return (
    (!firm || agent.firm === firm) &&
    (!regional || agent.regional === regional) &&
    (!asm || agent.asm === asm) &&
    (stores.length === 0 || stores.includes(agent.site_code))
  );
}

function SelectFilter({
  label,
  value,
  options,
  onChange,
  disabled = false,
}: {
  label: string;
  value: string | undefined;
  options: readonly string[];
  onChange: (value: string | undefined) => void;
  disabled?: boolean;
}) {
  return (
    <label className="filter-field">
      <span>{label}</span>
      <select
        value={value ?? ''}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value || undefined)}
      >
        <option value="">Toate</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function StoreMultiSelect({
  stores,
  selected,
  onChange,
}: {
  stores: FilterStore[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  const [search, setSearch] = useState('');
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const normalizedSearch = search.trim().toLocaleLowerCase('ro-RO');
  const filtered = stores.filter((store) =>
    `${store.label} ${store.site_code}`
      .toLocaleLowerCase('ro-RO')
      .includes(normalizedSearch),
  );

  return (
    <details className="filter-popover">
      <summary>
        <span className="filter-summary-label">Magazin</span>
        <strong>{selected.length === 0 ? 'Toate' : `${selected.length} selectate`}</strong>
      </summary>
      <div className="filter-popover-panel">
        <label className="filter-search">
          <Search size={14} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Caută magazin…"
          />
          {search ? (
            <button type="button" onClick={() => setSearch('')} aria-label="Șterge căutarea">
              <X size={13} />
            </button>
          ) : null}
        </label>
        <button type="button" className="select-all" onClick={() => onChange([])}>
          Toate magazinele
          {selected.length === 0 ? <Check size={14} /> : null}
        </button>
        <div className="store-options">
          {filtered.map((store) => {
            const checked = selectedSet.has(store.site_code);
            return (
              <label key={store.site_code} className="store-option">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    onChange(
                      checked
                        ? selected.filter((value) => value !== store.site_code)
                        : [...selected, store.site_code],
                    )
                  }
                />
                <span>
                  <strong>{store.label}</strong>
                  <small>{store.site_code}</small>
                </span>
                {checked ? <Check size={14} /> : null}
              </label>
            );
          })}
        </div>
      </div>
    </details>
  );
}

export function GlobalFilters() {
  const search = useGlobalSearch();
  const updateSearch = useUpdateGlobalSearch();
  const requestedPeriod = search.period ?? currentBusinessMonth();
  const optionsQuery = useQuery(filterOptionsQuery(requestedPeriod));
  const options = optionsQuery.data;
  const selectedStores = parseStoreSelection(search.stores);

  useEffect(() => {
    if (!options || options.periods.length === 0) return;
    const resolved = options.periods.includes(requestedPeriod)
      ? requestedPeriod
      : options.periods[0];
    if (resolved && search.period !== resolved) updateSearch({ period: resolved }, true);
  }, [options, requestedPeriod, search.period, updateSearch]);

  const filteredStores = useMemo(
    () =>
      (options?.stores ?? []).filter((store) =>
        matchingStore(store, search.firm, search.regional, search.asm),
      ),
    [options?.stores, search.asm, search.firm, search.regional],
  );

  const regionals = useMemo(
    () =>
      [
        ...new Set(
          (options?.stores ?? [])
            .filter((store) => !search.firm || store.firm === search.firm)
            .map((store) => store.regional),
        ),
      ].sort((a, b) => a.localeCompare(b, 'ro')),
    [options?.stores, search.firm],
  );

  const asms = useMemo(
    () =>
      [
        ...new Set(
          (options?.stores ?? [])
            .filter(
              (store) =>
                (!search.firm || store.firm === search.firm) &&
                (!search.regional || store.regional === search.regional),
            )
            .map((store) => store.asm)
            .filter((value): value is string => Boolean(value)),
        ),
      ].sort((a, b) => a.localeCompare(b, 'ro')),
    [options?.stores, search.firm, search.regional],
  );

  const agents = useMemo(
    () =>
      [
        ...new Set(
          (options?.agents ?? [])
            .filter((agent) =>
              matchingAgent(agent, search.firm, search.regional, search.asm, selectedStores),
            )
            .map((agent) => agent.name),
        ),
      ].sort((a, b) => a.localeCompare(b, 'ro')),
    [options?.agents, search.asm, search.firm, search.regional, selectedStores],
  );

  const count = activeFilterCount(search);

  return (
    <div className="global-filters" aria-label="Filtre globale">
      <div className="filter-heading" title={`${count} filtre business active`}>
        <Filter size={16} />
        {count > 0 ? <span>{count}</span> : null}
      </div>

      <label className="filter-field filter-field--period">
        <span>Perioadă</span>
        <select
          value={search.period ?? requestedPeriod}
          disabled={optionsQuery.isPending}
          onChange={(event) => updateSearch({ period: event.target.value })}
        >
          {(options?.periods ?? [requestedPeriod]).map((period) => (
            <option key={period} value={period}>
              {period}
            </option>
          ))}
        </select>
      </label>

      <label className="filter-field">
        <span>Comparație</span>
        <select
          value={search.comparison}
          onChange={(event) =>
            updateSearch({
              comparison: event.target.value as 'previous-month' | 'previous-year' | 'none',
            })
          }
        >
          <option value="previous-year">Anul trecut</option>
          <option value="previous-month">Luna precedentă</option>
          <option value="none">Fără reper</option>
        </select>
      </label>

      <SelectFilter
        label="Firmă"
        value={search.firm}
        options={options?.firms ?? []}
        disabled={optionsQuery.isPending}
        onChange={(firm) =>
          updateSearch({
            firm,
            regional: undefined,
            asm: undefined,
            stores: undefined,
            agent: undefined,
          })
        }
      />
      <SelectFilter
        label="RM"
        value={search.regional}
        options={regionals}
        disabled={optionsQuery.isPending}
        onChange={(regional) =>
          updateSearch({ regional, asm: undefined, stores: undefined, agent: undefined })
        }
      />
      <SelectFilter
        label="ASM"
        value={search.asm}
        options={asms}
        disabled={optionsQuery.isPending}
        onChange={(asm) => updateSearch({ asm, stores: undefined, agent: undefined })}
      />
      <StoreMultiSelect
        stores={filteredStores}
        selected={selectedStores}
        onChange={(stores) =>
          updateSearch({ stores: serializeStoreSelection(stores), agent: undefined })
        }
      />
      <SelectFilter
        label="Agent"
        value={search.agent}
        options={agents}
        disabled={optionsQuery.isPending}
        onChange={(agent) => updateSearch({ agent })}
      />

      <button
        type="button"
        className="filter-reset"
        disabled={count === 0}
        onClick={() =>
          updateSearch(
            {
              firm: undefined,
              regional: undefined,
              asm: undefined,
              stores: undefined,
              agent: undefined,
            },
            true,
          )
        }
      >
        <RotateCcw size={14} />
        Reset
      </button>
    </div>
  );
}
