import type { ColumnDef, SortingState } from '@tanstack/react-table';
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table';
import type { EChartsCoreOption } from 'echarts/core';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { EChart, type EChartEvent } from '../../components/charts/EChart';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatCurrency, formatInteger } from '../../lib/format';
import { useModuleData, useModuleEntityOpen, useModuleUrlStateChange } from './context';
import type { BreakdownRow, ModuleAnalytics } from './schemas';

export const PORTFOLIO_PAGE_SIZE = 50;

export function portfolioSearchText(row: Pick<BreakdownRow, 'id' | 'label' | 'context'>): string {
  return `${row.label} ${row.context} ${row.id}`.toLocaleLowerCase('ro-RO');
}

export function filterPortfolioRows(rows: readonly BreakdownRow[], search: string): BreakdownRow[] {
  const query = search.trim().toLocaleLowerCase('ro-RO');
  if (!query) return [...rows];
  return rows.filter((row) => portfolioSearchText(row).includes(query));
}

export function portfolioPageCount(totalRows: number, pageSize = PORTFOLIO_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(totalRows / pageSize));
}

export function portfolioPageRows<T>(
  rows: readonly T[],
  page: number,
  pageSize = PORTFOLIO_PAGE_SIZE,
): T[] {
  const safePage = Math.max(1, page);
  return rows.slice((safePage - 1) * pageSize, safePage * pageSize);
}

const portfolioDimensionLabels: Record<string, string> = {
  category: 'Categorie',
  subcategory: 'Subcategorie',
  brand: 'Brand',
  product: 'Produs / SKU',
};

function dimensionLabel(dimension: string): string {
  return portfolioDimensionLabels[dimension] ?? 'Entitate';
}

function portfolioInteraction(
  data: ModuleAnalytics,
  row: BreakdownRow,
): { dimensionId: string; value: string; label: string } {
  return {
    dimensionId: data.entity_dimension ?? 'category',
    value: row.id,
    label: row.label,
  };
}

export function PortfolioDistributionWidget() {
  const data = useModuleData();
  const onUrlStateChange = useModuleUrlStateChange();
  const onEntityOpen = useModuleEntityOpen();
  const rows = useMemo(
    () => [...data.distribution].sort((left, right) => right.value - left.value).slice(0, 20),
    [data.distribution],
  );
  const dimension = data.distribution_dimension ?? data.entity_dimension ?? 'category';
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 220,
      aria: {
        enabled: true,
        description: `Top 20 ${dimensionLabel(dimension).toLocaleLowerCase('ro-RO')} după vânzări nete.`,
      },
      grid: { top: 12, right: 18, bottom: 28, left: 128 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        valueFormatter: (value: number) => formatCurrency(value, true),
      },
      xAxis: {
        type: 'value',
        axisLabel: {
          color: '#64748b',
          fontSize: 9,
          formatter: (value: number) => formatCurrency(value, true),
        },
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: rows.map((row) => row.label),
        axisLabel: { color: '#64748b', fontSize: 9, width: 116, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          data: rows.map((row) => row.value),
          itemStyle: { color: '#4f46e5', borderRadius: [0, 5, 5, 0] },
        },
      ],
    }),
    [dimension, rows],
  );

  if (rows.length === 0) {
    return <EmptyState message="Nu există vânzări pozitive pentru distribuția curentă." />;
  }

  const interaction = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    return row
      ? {
          dimensionId: dimension,
          value: row.id,
          label: row.label,
        }
      : undefined;
  };

  return (
    <EChart
      option={option}
      className="chart--fill"
      ariaLabel={`Distribuție top ${dimensionLabel(dimension)} după vânzări`}
      pngExport={{ filename: `sales-portfolio-${dimension}-distribution`, pixelRatio: 2 }}
      onEvent={(event) => {
        const item = interaction(event);
        if (item) onUrlStateChange?.(item);
      }}
      onDoubleEvent={(event) => {
        const item = interaction(event);
        if (item) onEntityOpen?.(item);
      }}
    />
  );
}

export function PortfolioTableWidget() {
  const data = useModuleData();
  const onUrlStateChange = useModuleUrlStateChange();
  const onEntityOpen = useModuleEntityOpen();
  const dimension = data.entity_dimension ?? 'category';
  const isItemDetail = dimension === 'brand' || dimension === 'product';
  const isProduct = dimension === 'product';
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [sorting, setSorting] = useState<SortingState>([{ id: 'primary', desc: true }]);
  const entityClickTimer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (entityClickTimer.current !== null) window.clearTimeout(entityClickTimer.current);
    },
    [],
  );

  const filteredRows = useMemo(
    () => filterPortfolioRows(data.breakdown, search),
    [data.breakdown, search],
  );
  const columns = useMemo<ColumnDef<BreakdownRow>[]>(() => {
    const next: ColumnDef<BreakdownRow>[] = [
      {
        id: 'label',
        accessorFn: (row) => row.label,
        header: dimensionLabel(dimension),
        cell: ({ row }) => (
          <div className="entity-cell portfolio-entity-cell">
            <div>
              <button
                type="button"
                className="table-sort"
                onClick={() => {
                  if (entityClickTimer.current !== null)
                    window.clearTimeout(entityClickTimer.current);
                  entityClickTimer.current = window.setTimeout(() => {
                    entityClickTimer.current = null;
                    onUrlStateChange?.(portfolioInteraction(data, row.original));
                  }, 250);
                }}
                onDoubleClick={() => {
                  if (entityClickTimer.current !== null) {
                    window.clearTimeout(entityClickTimer.current);
                    entityClickTimer.current = null;
                  }
                  onEntityOpen?.(portfolioInteraction(data, row.original));
                }}
              >
                <strong>{row.original.label}</strong>
              </button>
              <span>{row.original.context}</span>
              <small>
                {isProduct ? 'SKU' : 'ID'}: {row.original.id}
              </small>
            </div>
          </div>
        ),
      },
      {
        accessorKey: 'primary',
        header: 'Vânzări nete',
        cell: ({ getValue }) => formatCurrency(Number(getValue()), true),
      },
      {
        accessorKey: 'secondary',
        header: 'Cantitate netă',
        cell: ({ getValue }) => formatInteger(Number(getValue() ?? 0)),
      },
    ];
    if (isItemDetail) {
      next.push({
        accessorKey: 'tertiary',
        header: 'Cantitate retur semnată',
        cell: ({ getValue }) => formatInteger(Number(getValue() ?? 0)),
      });
    }
    if (isProduct) {
      next.push({
        accessorKey: 'quaternary',
        header: 'Incidențe SKU în bonuri',
        cell: ({ getValue }) => formatInteger(Number(getValue() ?? 0)),
      });
    }
    return next;
  }, [data, dimension, isItemDetail, isProduct, onEntityOpen, onUrlStateChange]);
  const table = useReactTable({
    data: filteredRows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  const sortedRows = table.getSortedRowModel().rows;
  const pageCount = portfolioPageCount(sortedRows.length);
  const visibleRows = portfolioPageRows(sortedRows, page);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  if (data.breakdown.length === 0) {
    return <EmptyState message="Nu există entități în portofoliul pentru scope-ul curent." />;
  }

  return (
    <div className="portfolio-table-widget">
      <div className="portfolio-table-toolbar">
        <label className="portfolio-search">
          <span>Caută</span>
          <input
            type="search"
            value={search}
            placeholder="Nume, context, SKU sau ID"
            aria-label={`Caută în ${dimensionLabel(dimension)}`}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <fieldset className="portfolio-sort-controls">
          <legend className="sr-only">Sortare vânzări</legend>
          <button
            type="button"
            className={`button button--ghost ${sorting[0]?.id === 'primary' && sorting[0].desc ? 'is-active' : ''}`}
            onClick={() => setSorting([{ id: 'primary', desc: true }])}
          >
            Top vânzări
          </button>
          <button
            type="button"
            className={`button button--ghost ${sorting[0]?.id === 'primary' && !sorting[0].desc ? 'is-active' : ''}`}
            onClick={() => setSorting([{ id: 'primary', desc: false }])}
          >
            Bottom vânzări
          </button>
        </fieldset>
      </div>
      {sortedRows.length === 0 ? (
        <EmptyState message="Căutarea nu a găsit entități în portofoliul curent." />
      ) : (
        <>
          <div className="table-scroll portfolio-table-scroll">
            <table className="data-table portfolio-table">
              <thead>
                {table.getHeaderGroups().map((group) => (
                  <tr key={group.id}>
                    {group.headers.map((header) => (
                      <th key={header.id}>
                        <button
                          type="button"
                          className="table-sort"
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {header.column.getIsSorted() === 'asc'
                            ? ' ↑'
                            : header.column.getIsSorted() === 'desc'
                              ? ' ↓'
                              : ''}
                        </button>
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <footer className="portfolio-table-footer">
            <span>
              {sortedRows.length.toLocaleString('ro-RO')} rezultate · pagina {page} din {pageCount}{' '}
              · maximum {PORTFOLIO_PAGE_SIZE} rânduri
            </span>
            <div>
              <button
                type="button"
                className="icon-button"
                aria-label="Pagina anterioară"
                disabled={page <= 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                <ChevronLeft size={15} />
              </button>
              <button
                type="button"
                className="icon-button"
                aria-label="Pagina următoare"
                disabled={page >= pageCount}
                onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
              >
                <ChevronRight size={15} />
              </button>
            </div>
          </footer>
        </>
      )}
    </div>
  );
}
