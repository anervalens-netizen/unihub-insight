import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BookmarkPlus, Check, Filter, RotateCcw, Save, Search, Trash2, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  createFilterPreset,
  deleteFilterPreset,
  filterPresetsQuery,
  updateFilterPreset,
} from '../features/dashboards/api';
import { useIdentity } from '../features/identity/context';
import { filterOptionsQuery } from '../features/overview/api';
import type { FilterAgent, FilterStore } from '../features/overview/schemas';
import {
  activeFilterCount,
  analyticalComparisons,
  currentBusinessMonth,
  globalSearchSchema,
  parseComparisons,
  parseDrillPath,
  parseStoreSelection,
  type rangePresets,
  serializeComparisons,
  serializeDrillPath,
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
    `${store.label} ${store.site_code}`.toLocaleLowerCase('ro-RO').includes(normalizedSearch),
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

const comparisonLabels: Record<(typeof analyticalComparisons)[number], string> = {
  target: 'Target',
  forecast: 'Forecast',
  'previous-period': 'Perioada precedentă',
  'previous-year': 'Anul trecut',
  'recent-average': 'Media recentă',
};

function ComparisonMultiSelect({
  selected,
  onChange,
}: {
  selected: readonly (typeof analyticalComparisons)[number][];
  onChange: (values: (typeof analyticalComparisons)[number][]) => void;
}) {
  return (
    <details className="filter-popover filter-popover--comparisons">
      <summary>
        <span className="filter-summary-label">Comparații</span>
        <strong>{selected.length === 0 ? 'Fără reper' : `${selected.length} active`}</strong>
      </summary>
      <div className="filter-popover-panel">
        {analyticalComparisons.map((comparison) => (
          <label key={comparison} className="comparison-option">
            <input
              type="checkbox"
              checked={selected.includes(comparison)}
              onChange={() =>
                onChange(
                  selected.includes(comparison)
                    ? selected.filter((value) => value !== comparison)
                    : [...selected, comparison],
                )
              }
            />
            <span>{comparisonLabels[comparison]}</span>
          </label>
        ))}
      </div>
    </details>
  );
}

const presetFilterKeys = [
  'period',
  'comparison',
  'comparisons',
  'range',
  'start',
  'end',
  'firm',
  'regional',
  'asm',
  'stores',
  'agent',
] as const;

function presetFilters(search: ReturnType<typeof useGlobalSearch>): Record<string, string> {
  return Object.fromEntries(
    presetFilterKeys.flatMap((key) => {
      const value = search[key];
      return typeof value === 'string' && value ? [[key, value]] : [];
    }),
  );
}

const clearPresetFilters = Object.fromEntries(
  presetFilterKeys.map((key) => [key, undefined]),
) as Record<(typeof presetFilterKeys)[number], undefined>;

export function GlobalFilters() {
  const search = useGlobalSearch();
  const updateSearch = useUpdateGlobalSearch();
  const identity = useIdentity();
  const queryClient = useQueryClient();
  const requestedPeriod = search.period ?? currentBusinessMonth();
  const optionsQuery = useQuery(filterOptionsQuery(requestedPeriod));
  const presetsQuery = useQuery(filterPresetsQuery);
  const [presetId, setPresetId] = useState('');
  const [presetName, setPresetName] = useState('');
  const [presetShared, setPresetShared] = useState(false);
  const [presetMessage, setPresetMessage] = useState<string | null>(null);
  const options = optionsQuery.data;
  const selectedStores = parseStoreSelection(search.stores);
  const selectedComparisons = parseComparisons(search);
  const selectedPreset = presetsQuery.data?.find((preset) => preset.id === presetId);
  const refreshPresets = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ['filter-presets'] });
  };
  const createPresetMutation = useMutation({
    mutationFn: createFilterPreset,
    onSuccess: async (preset) => {
      setPresetId(preset.id);
      setPresetName(preset.name);
      setPresetShared(preset.shared);
      setPresetMessage('Preset salvat.');
      await refreshPresets();
    },
    onError: (error) =>
      setPresetMessage(error instanceof Error ? error.message : 'Presetul nu a putut fi salvat.'),
  });
  const updatePresetMutation = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      updateFilterPreset(id, {
        name: presetName.trim(),
        shared: presetShared,
        filters: presetFilters(search),
        version,
      }),
    onSuccess: async (preset) => {
      setPresetMessage('Preset actualizat.');
      setPresetShared(preset.shared);
      await refreshPresets();
    },
    onError: (error) =>
      setPresetMessage(
        error instanceof Error ? error.message : 'Presetul nu a putut fi actualizat.',
      ),
  });
  const deletePresetMutation = useMutation({
    mutationFn: deleteFilterPreset,
    onSuccess: async () => {
      setPresetId('');
      setPresetName('');
      setPresetShared(false);
      setPresetMessage('Preset șters.');
      await refreshPresets();
    },
    onError: (error) =>
      setPresetMessage(error instanceof Error ? error.message : 'Presetul nu a putut fi șters.'),
  });

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

  const drillPath = parseDrillPath(search.drill);
  const count = activeFilterCount(search) + drillPath.length;

  return (
    <div className="global-filter-stack">
      <div className="global-filters">
        <div className="filter-heading" title={`${count} filtre business active`}>
          <Filter size={16} />
          {count > 0 ? <span>{count}</span> : null}
        </div>

        <details className="filter-popover filter-popover--presets">
          <summary>
            <span className="filter-summary-label">Preset</span>
            <strong>{selectedPreset?.name ?? 'Alege'}</strong>
          </summary>
          <div className="filter-popover-panel filter-preset-panel">
            <select
              value={presetId}
              disabled={presetsQuery.isPending}
              onChange={(event) => {
                const id = event.target.value;
                setPresetId(id);
                const preset = presetsQuery.data?.find((item) => item.id === id);
                if (!preset) return;
                setPresetName(preset.name);
                setPresetShared(preset.shared);
                const parsed = globalSearchSchema.safeParse(preset.filters);
                if (parsed.success) {
                  updateSearch({ ...clearPresetFilters, ...parsed.data }, true);
                  setPresetMessage('Preset aplicat.');
                } else {
                  setPresetMessage('Preset incompatibil cu contractul curent.');
                }
              }}
            >
              <option value="">Alege un preset…</option>
              {(presetsQuery.data ?? []).map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.name}
                  {preset.shared ? ' · shared' : ''}
                </option>
              ))}
            </select>
            <input
              value={presetName}
              maxLength={160}
              placeholder="Nume preset"
              onChange={(event) => setPresetName(event.target.value)}
            />
            <label className="comparison-option">
              <input
                type="checkbox"
                checked={presetShared}
                onChange={(event) => setPresetShared(event.target.checked)}
              />
              <span>Partajat</span>
            </label>
            <div className="filter-preset-actions">
              <button
                type="button"
                disabled={!presetName.trim() || createPresetMutation.isPending}
                onClick={() =>
                  createPresetMutation.mutate({
                    name: presetName.trim(),
                    shared: presetShared,
                    filters: presetFilters(search),
                  })
                }
              >
                <BookmarkPlus size={13} /> Nou
              </button>
              {selectedPreset?.owner_subject === identity.subject ? (
                <>
                  <button
                    type="button"
                    disabled={!presetName.trim() || updatePresetMutation.isPending}
                    onClick={() =>
                      updatePresetMutation.mutate({
                        id: selectedPreset.id,
                        version: selectedPreset.version,
                      })
                    }
                  >
                    <Save size={13} /> Actualizează
                  </button>
                  <button
                    type="button"
                    disabled={deletePresetMutation.isPending}
                    onClick={() => deletePresetMutation.mutate(selectedPreset.id)}
                  >
                    <Trash2 size={13} /> Șterge
                  </button>
                </>
              ) : null}
            </div>
            {presetMessage ? <small>{presetMessage}</small> : null}
          </div>
        </details>

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

        <label className="filter-field filter-field--range">
          <span>Interval</span>
          <select
            value={search.range ?? 'month'}
            onChange={(event) => {
              const range = event.target.value as (typeof rangePresets)[number];
              updateSearch({
                range,
                ...(range === 'custom'
                  ? { start: search.start ?? requestedPeriod, end: search.end ?? requestedPeriod }
                  : { start: undefined, end: undefined }),
              });
            }}
          >
            <option value="month">Luna selectată</option>
            <option value="ytd">YTD</option>
            <option value="3">Ultimele 3 luni</option>
            <option value="6">Ultimele 6 luni</option>
            <option value="12">Ultimele 12 luni</option>
            <option value="year">An</option>
            <option value="custom">Custom</option>
          </select>
        </label>

        {search.range === 'custom' ? (
          <>
            <label className="filter-field filter-field--period">
              <span>De la</span>
              <input
                type="month"
                value={search.start ?? requestedPeriod}
                onChange={(event) => updateSearch({ start: event.target.value || undefined })}
              />
            </label>
            <label className="filter-field filter-field--period">
              <span>Până la</span>
              <input
                type="month"
                value={search.end ?? requestedPeriod}
                onChange={(event) => {
                  const end = event.target.value || undefined;
                  updateSearch({ end, period: end });
                }}
              />
            </label>
          </>
        ) : null}

        <ComparisonMultiSelect
          selected={selectedComparisons}
          onChange={(values) =>
            updateSearch({
              comparisons: serializeComparisons(values),
              comparison: values.includes('previous-year')
                ? 'previous-year'
                : values.includes('previous-period')
                  ? 'previous-month'
                  : 'none',
            })
          }
        />

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
                drill: undefined,
              },
              true,
            )
          }
        >
          <RotateCcw size={14} />
          Reset
        </button>
      </div>
      {drillPath.length > 0 ? (
        <nav className="drill-breadcrumb" aria-label="Traseu drill-down">
          <span>Drill</span>
          {drillPath.map((item, index) => (
            <button
              type="button"
              key={`${item.dimension}:${item.value}`}
              title={`Elimină ${item.label ?? item.value} și nivelurile următoare`}
              onClick={() =>
                updateSearch(
                  {
                    drill: serializeDrillPath(drillPath.slice(0, index)),
                    ...(item.dimension === 'store' || item.dimension === 'site_code'
                      ? { stores: undefined }
                      : {}),
                  },
                  true,
                )
              }
            >
              <small>{item.dimension}</small>
              <strong>{item.label ?? item.value}</strong>
              <X size={12} />
            </button>
          ))}
          <button
            type="button"
            className="drill-breadcrumb-reset"
            onClick={() => updateSearch({ drill: undefined, stores: undefined }, true)}
          >
            <RotateCcw size={12} /> Reset drill
          </button>
        </nav>
      ) : null}
    </div>
  );
}
