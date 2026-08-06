import {
  type DrillPathItem,
  type GlobalSearchPatch,
  normalizeDrillDimension,
  parseDrillPath,
  updateDrillPath,
} from './search';

export interface CrossFilterEvent {
  dimensionId: string;
  value: string;
  label: string | null;
}

function clearPatch(items: readonly DrillPathItem[]): GlobalSearchPatch {
  const patch: GlobalSearchPatch = {};
  for (const item of items) {
    switch (normalizeDrillDimension(item.dimension)) {
      case 'time':
        patch.period = undefined;
        patch.range = undefined;
        patch.start = undefined;
        patch.end = undefined;
        break;
      case 'firm':
        patch.firm = undefined;
        break;
      case 'regional':
        patch.regional = undefined;
        break;
      case 'asm':
        patch.asm = undefined;
        break;
      case 'store':
        patch.stores = undefined;
        break;
      case 'agent':
        patch.agent = undefined;
        break;
    }
  }
  return patch;
}

export function crossFilterPatch(
  currentDrill: string | undefined,
  event: CrossFilterEvent,
): GlobalSearchPatch {
  const dimension = normalizeDrillDimension(event.dimensionId);
  const value = event.value.trim();
  if (!value || !['time', 'firm', 'regional', 'asm', 'store', 'agent'].includes(dimension)) {
    return {};
  }
  if (dimension === 'time' && !/^\d{4}-(0[1-9]|1[0-2])$/.test(value)) return {};
  const drill = updateDrillPath(currentDrill, {
    dimension,
    value,
    label: event.label,
  });
  switch (dimension) {
    case 'time':
      return { drill, period: value, range: 'month', start: undefined, end: undefined };
    case 'firm':
      return {
        drill,
        firm: value,
        regional: undefined,
        asm: undefined,
        stores: undefined,
        agent: undefined,
      };
    case 'regional':
      return { drill, regional: value, asm: undefined, stores: undefined, agent: undefined };
    case 'asm':
      return { drill, asm: value, stores: undefined, agent: undefined };
    case 'store':
      return { drill, stores: value, agent: undefined };
    case 'agent':
      return { drill, agent: value };
    default:
      return {};
  }
}

export function truncateCrossFilterPatch(
  currentDrill: string | undefined,
  keepCount: number,
): GlobalSearchPatch {
  const items = parseDrillPath(currentDrill);
  return {
    ...clearPatch(items.slice(keepCount)),
    drill: updateDrillPathFromItems(items.slice(0, keepCount)),
  };
}

export function resetCrossFilterPatch(currentDrill: string | undefined): GlobalSearchPatch {
  return { ...clearPatch(parseDrillPath(currentDrill)), drill: undefined };
}

function updateDrillPathFromItems(items: readonly DrillPathItem[]): string | undefined {
  let drill: string | undefined;
  for (const item of items) drill = updateDrillPath(drill, item);
  return drill;
}
