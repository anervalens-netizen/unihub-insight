export type ProfessionalChartType =
  | 'line'
  | 'area'
  | 'bar'
  | 'donut'
  | 'waterfall'
  | 'heatmap'
  | 'scatter'
  | 'histogram'
  | 'boxplot'
  | 'treemap'
  | 'calendar'
  | 'forecast-band';

const labels: Record<ProfessionalChartType, string> = {
  line: 'Linie',
  area: 'Arie',
  bar: 'Coloane',
  donut: 'Donut',
  waterfall: 'Waterfall',
  heatmap: 'Heatmap',
  scatter: 'Scatter',
  histogram: 'Histogramă',
  boxplot: 'Box plot',
  treemap: 'Treemap',
  calendar: 'Calendar',
  'forecast-band': 'Bandă forecast',
};

export function ChartTypeSelector<Type extends ProfessionalChartType>({
  value,
  options,
  onChange,
  label = 'Tip grafic',
}: {
  value: Type;
  options: readonly Type[];
  onChange: (value: Type) => void;
  label?: string;
}) {
  if (options.length < 2) return null;
  return (
    <fieldset className="chart-type-selector">
      <legend>{label}</legend>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          className={value === option ? 'is-active' : ''}
          aria-pressed={value === option}
          onClick={() => onChange(option)}
        >
          {labels[option]}
        </button>
      ))}
    </fieldset>
  );
}
