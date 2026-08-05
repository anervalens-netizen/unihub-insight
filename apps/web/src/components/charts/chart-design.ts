import type { EChartsCoreOption } from 'echarts/core';

import {
  type AppTheme,
  type ChartPalette,
  type ChartPreferences,
  useChartPreferences,
} from './ChartPreferences';

export interface ChartDesign {
  theme: AppTheme;
  paletteName: ChartPalette;
  palette: string[];
  primary: string;
  secondary: string;
  positive: string;
  warning: string;
  negative: string;
  text: string;
  muted: string;
  subtle: string;
  grid: string;
  border: string;
  surface: string;
  tooltip: string;
  areaPrimary: string;
  areaPositive: string;
  preferences: ChartPreferences;
}

type PlainRecord = Record<string, unknown>;

const paletteDefinitions: Record<ChartPalette, { light: string[]; dark: string[] }> = {
  executive: {
    light: ['#4f46e5', '#0f766e', '#d97706', '#be123c', '#2563eb', '#7c3aed', '#0891b2'],
    dark: ['#818cf8', '#5eead4', '#fbbf24', '#fb7185', '#60a5fa', '#c4b5fd', '#67e8f9'],
  },
  ocean: {
    light: ['#2563eb', '#0891b2', '#0d9488', '#7c3aed', '#0284c7', '#14b8a6', '#6366f1'],
    dark: ['#60a5fa', '#22d3ee', '#5eead4', '#c4b5fd', '#38bdf8', '#2dd4bf', '#a5b4fc'],
  },
  vibrant: {
    light: ['#7c3aed', '#06b6d4', '#f59e0b', '#ec4899', '#2563eb', '#10b981', '#f97316'],
    dark: ['#c4b5fd', '#67e8f9', '#fcd34d', '#f9a8d4', '#93c5fd', '#6ee7b7', '#fdba74'],
  },
  accessible: {
    light: ['#0072b2', '#e69f00', '#009e73', '#cc79a7', '#56b4e9', '#d55e00', '#f0e442'],
    dark: ['#56b4e9', '#f0e442', '#6ee7b7', '#f0a6ca', '#93c5fd', '#fdba74', '#fde68a'],
  },
  monochrome: {
    light: ['#1e293b', '#475569', '#64748b', '#94a3b8', '#334155', '#cbd5e1'],
    dark: ['#f1f5f9', '#cbd5e1', '#94a3b8', '#64748b', '#e2e8f0', '#475569'],
  },
};

function withAlpha(hex: string, alpha: number): string {
  const normalized = hex.replace('#', '');
  if (normalized.length !== 6) return hex;
  const red = Number.parseInt(normalized.slice(0, 2), 16);
  const green = Number.parseInt(normalized.slice(2, 4), 16);
  const blue = Number.parseInt(normalized.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

export function createChartDesign(theme: AppTheme, preferences: ChartPreferences): ChartDesign {
  const palette = paletteDefinitions[preferences.palette][theme];
  const dark = theme === 'dark';
  return {
    theme,
    paletteName: preferences.palette,
    palette,
    primary: palette[0] ?? '#4f46e5',
    secondary: palette[4] ?? palette[1] ?? '#2563eb',
    positive:
      preferences.palette === 'monochrome'
        ? (palette[1] ?? '#475569')
        : dark
          ? '#5eead4'
          : '#0f766e',
    warning:
      preferences.palette === 'monochrome'
        ? (palette[2] ?? '#64748b')
        : dark
          ? '#fbbf24'
          : '#d97706',
    negative:
      preferences.palette === 'monochrome'
        ? (palette[3] ?? '#94a3b8')
        : dark
          ? '#fb7185'
          : '#be123c',
    text: dark ? '#eef4fb' : '#172033',
    muted: dark ? '#9eacc0' : '#64748b',
    subtle: dark ? '#6f7f96' : '#94a3b8',
    grid: dark ? '#263449' : '#e5ebf3',
    border: dark ? '#35465e' : '#d8e1ec',
    surface: dark ? '#111a29' : '#ffffff',
    tooltip: dark ? 'rgba(9, 15, 26, 0.96)' : 'rgba(255, 255, 255, 0.98)',
    areaPrimary: withAlpha(palette[0] ?? '#4f46e5', dark ? 0.2 : 0.13),
    areaPositive: withAlpha(dark ? '#5eead4' : '#0f766e', dark ? 0.16 : 0.1),
    preferences,
  };
}

export function useChartDesign(): ChartDesign {
  const { theme, preferences } = useChartPreferences();
  return createChartDesign(theme, preferences);
}

function isPlainRecord(value: unknown): value is PlainRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function mappedColor(value: string, design: ChartDesign): string {
  const normalized = value.toLowerCase().replaceAll(' ', '');
  const replacements: Record<string, string> = {
    '#4f46e5': design.primary,
    '#3730a3': design.primary,
    '#2563eb': design.secondary,
    '#0f766e': design.positive,
    '#0891b2': design.palette[2] ?? design.secondary,
    '#d97706': design.warning,
    '#b45309': design.warning,
    '#be123c': design.negative,
    '#d55e00': design.negative,
    '#64748b': design.muted,
    '#718096': design.muted,
    '#94a3b8': design.subtle,
    '#dbe3ef': design.border,
    '#dce4ee': design.border,
    '#e7edf5': design.grid,
    '#e9eef5': design.grid,
    '#ffffff': design.surface,
    '#fff': design.surface,
    'rgba(79,70,229,0.10)': design.areaPrimary,
    'rgba(79,70,229,.10)': design.areaPrimary,
    'rgba(79,70,229,0.12)': design.areaPrimary,
    'rgba(79,70,229,.12)': design.areaPrimary,
    'rgba(15,118,110,.10)': design.areaPositive,
  };
  return replacements[normalized] ?? value;
}

function mergeTextStyle(value: unknown, design: ChartDesign): PlainRecord {
  const existing = isPlainRecord(value) ? value : {};
  return {
    color: design.muted,
    fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
    fontSize: design.preferences.density === 'compact' ? 10 : 11,
    ...existing,
  };
}

function styleAxis(value: unknown, design: ChartDesign): unknown {
  if (Array.isArray(value)) return value.map((item) => styleAxis(item, design));
  if (!isPlainRecord(value)) return value;
  const axisLine = value['axisLine'];
  const axisTick = value['axisTick'];
  const splitLine = value['splitLine'];
  return {
    ...value,
    axisLine: {
      lineStyle: { color: design.border },
      ...(isPlainRecord(axisLine) ? axisLine : {}),
    },
    axisTick: {
      show: false,
      ...(isPlainRecord(axisTick) ? axisTick : {}),
    },
    axisLabel: mergeTextStyle(value['axisLabel'], design),
    nameTextStyle: mergeTextStyle(value['nameTextStyle'], design),
    splitLine: {
      lineStyle: { color: design.grid, type: 'dashed', opacity: 0.9 },
      ...(isPlainRecord(splitLine) ? splitLine : {}),
    },
  };
}

function styleLegend(value: unknown, design: ChartDesign): unknown {
  if (Array.isArray(value)) return value.map((item) => styleLegend(item, design));
  const existing = isPlainRecord(value) ? value : {};
  return {
    show: design.preferences.showLegend,
    itemWidth: 13,
    itemHeight: 7,
    itemGap: design.preferences.density === 'compact' ? 9 : 13,
    textStyle: mergeTextStyle(existing['textStyle'], design),
    ...existing,
  };
}

function styleTooltip(value: unknown, design: ChartDesign): unknown {
  const existing = isPlainRecord(value) ? value : {};
  return {
    confine: true,
    backgroundColor: design.tooltip,
    borderColor: design.border,
    borderWidth: 1,
    padding: design.preferences.density === 'compact' ? [7, 9] : [9, 11],
    textStyle: {
      color: design.text,
      fontSize: design.preferences.density === 'compact' ? 10 : 11,
    },
    extraCssText:
      'border-radius:10px;box-shadow:0 14px 34px rgba(15,23,42,.18);backdrop-filter:blur(12px)',
    ...existing,
  };
}

function labelStyle(existing: PlainRecord, design: ChartDesign): PlainRecord {
  return {
    position: 'top',
    color: design.muted,
    fontSize: design.preferences.density === 'compact' ? 9 : 10,
    ...existing,
    show: design.preferences.showLabels || existing['show'] === true,
  };
}

function styleSeries(value: unknown, design: ChartDesign): unknown {
  if (Array.isArray(value)) return value.map((item) => styleSeries(item, design));
  if (!isPlainRecord(value)) return value;
  const typeValue = value['type'];
  const type = typeof typeValue === 'string' ? typeValue : '';
  const itemStyleValue = value['itemStyle'];
  const labelValue = value['label'];
  const emphasisValue = value['emphasis'];
  const existingItemStyle = isPlainRecord(itemStyleValue) ? itemStyleValue : {};
  const existingLabel = isPlainRecord(labelValue) ? labelValue : {};
  const existingEmphasis = isPlainRecord(emphasisValue) ? emphasisValue : {};
  const base: PlainRecord = {
    ...value,
    universalTransition: value['universalTransition'] ?? true,
    emphasis: { focus: 'series', ...existingEmphasis },
  };

  if (type === 'line') {
    base['smooth'] = design.preferences.smoothLines ? (value['smooth'] ?? 0.16) : false;
    base['showSymbol'] = value['showSymbol'] ?? false;
    base['symbol'] = value['symbol'] ?? 'circle';
    base['symbolSize'] = value['symbolSize'] ?? 6;
    base['label'] = labelStyle(existingLabel, design);
  }
  if (type === 'bar') {
    base['barMaxWidth'] =
      value['barMaxWidth'] ?? (design.preferences.density === 'compact' ? 26 : 34);
    base['itemStyle'] = {
      borderRadius: [7, 7, 2, 2],
      ...existingItemStyle,
    };
    base['label'] = labelStyle(existingLabel, design);
  }
  if (type === 'pie') {
    base['itemStyle'] = {
      borderColor: design.surface,
      borderWidth: 2,
      borderRadius: 7,
      ...existingItemStyle,
    };
    base['label'] = {
      color: design.text,
      fontSize: design.preferences.density === 'compact' ? 9 : 10,
      ...existingLabel,
      show: design.preferences.showLabels || existingLabel['show'] === true,
    };
  }
  if (type === 'scatter') {
    base['symbolSize'] = value['symbolSize'] ?? 10;
    base['itemStyle'] = {
      opacity: 0.82,
      shadowBlur: 8,
      shadowColor: withAlpha(design.primary, 0.22),
      ...existingItemStyle,
    };
    base['label'] = labelStyle(existingLabel, design);
  }
  if (type === 'heatmap') {
    base['label'] = {
      color: design.text,
      fontSize: design.preferences.density === 'compact' ? 8 : 9,
      ...existingLabel,
      show: design.preferences.showLabels || existingLabel['show'] === true,
    };
  }
  return base;
}

function styleValue(value: unknown, design: ChartDesign, key?: string): unknown {
  if (typeof value === 'string') return mappedColor(value, design);
  if (Array.isArray(value)) {
    if (key === 'series') return styleSeries(value, design);
    return value.map((item) => styleValue(item, design));
  }
  if (!isPlainRecord(value)) return value;

  const mapped: PlainRecord = {};
  for (const [entryKey, entryValue] of Object.entries(value)) {
    if (entryKey === 'xAxis' || entryKey === 'yAxis') {
      mapped[entryKey] = styleAxis(entryValue, design);
    } else if (entryKey === 'legend') {
      mapped[entryKey] = styleLegend(entryValue, design);
    } else if (entryKey === 'tooltip') {
      mapped[entryKey] = styleTooltip(entryValue, design);
    } else if (entryKey === 'series') {
      mapped[entryKey] = styleSeries(entryValue, design);
    } else {
      mapped[entryKey] = styleValue(entryValue, design, entryKey);
    }
  }
  return mapped;
}

export function applyChartDesign(
  option: EChartsCoreOption,
  design: ChartDesign,
): EChartsCoreOption {
  const mapped = styleValue(option, design);
  const record = isPlainRecord(mapped) ? mapped : {};
  const ariaValue = record['aria'];
  const textStyleValue = record['textStyle'];
  const existingAria = isPlainRecord(ariaValue) ? ariaValue : {};
  return {
    ...record,
    color: design.palette,
    backgroundColor: 'transparent',
    animation: design.preferences.animate,
    animationDuration: design.preferences.animate ? 280 : 0,
    animationDurationUpdate: design.preferences.animate ? 360 : 0,
    animationEasing: 'cubicOut',
    animationEasingUpdate: 'cubicInOut',
    textStyle: {
      color: design.text,
      fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
      ...(isPlainRecord(textStyleValue) ? textStyleValue : {}),
    },
    aria: {
      enabled: true,
      decal: { show: design.paletteName === 'accessible' },
      ...existingAria,
    },
  } as EChartsCoreOption;
}
