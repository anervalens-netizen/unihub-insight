import { Check, Palette, RotateCcw, SlidersHorizontal, X } from 'lucide-react';
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

export type AppTheme = 'light' | 'dark';
export type ChartPalette = 'executive' | 'ocean' | 'vibrant' | 'accessible' | 'monochrome';
export type ChartDensity = 'comfortable' | 'compact';

export interface ChartPreferences {
  palette: ChartPalette;
  density: ChartDensity;
  showLegend: boolean;
  showLabels: boolean;
  animate: boolean;
  smoothLines: boolean;
}

interface ChartPreferencesContextValue {
  theme: AppTheme;
  preferences: ChartPreferences;
  update: (patch: Partial<ChartPreferences>) => void;
  reset: () => void;
}

const STORAGE_KEY = 'unihub-insight:chart-preferences:v1';
const DEFAULT_PREFERENCES: ChartPreferences = {
  palette: 'executive',
  density: 'comfortable',
  showLegend: true,
  showLabels: false,
  animate: true,
  smoothLines: false,
};

const ChartPreferencesContext = createContext<ChartPreferencesContextValue | null>(null);

function readPreferences(): ChartPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    const value = JSON.parse(raw) as Partial<ChartPreferences>;
    const palettes: ChartPalette[] = ['executive', 'ocean', 'vibrant', 'accessible', 'monochrome'];
    return {
      palette: palettes.includes(value.palette as ChartPalette)
        ? (value.palette as ChartPalette)
        : DEFAULT_PREFERENCES.palette,
      density: value.density === 'compact' ? 'compact' : 'comfortable',
      showLegend:
        typeof value.showLegend === 'boolean' ? value.showLegend : DEFAULT_PREFERENCES.showLegend,
      showLabels:
        typeof value.showLabels === 'boolean' ? value.showLabels : DEFAULT_PREFERENCES.showLabels,
      animate: typeof value.animate === 'boolean' ? value.animate : DEFAULT_PREFERENCES.animate,
      smoothLines:
        typeof value.smoothLines === 'boolean'
          ? value.smoothLines
          : DEFAULT_PREFERENCES.smoothLines,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function ChartPreferencesProvider({
  theme,
  children,
}: {
  theme: AppTheme;
  children: ReactNode;
}) {
  const [preferences, setPreferences] = useState(readPreferences);
  const update = useCallback((patch: Partial<ChartPreferences>): void => {
    setPreferences((current) => {
      const next = { ...current, ...patch };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);
  const reset = useCallback((): void => {
    localStorage.removeItem(STORAGE_KEY);
    setPreferences(DEFAULT_PREFERENCES);
  }, []);
  const value = useMemo(
    () => ({ theme, preferences, update, reset }),
    [preferences, reset, theme, update],
  );
  return (
    <ChartPreferencesContext.Provider value={value}>{children}</ChartPreferencesContext.Provider>
  );
}

export function useChartPreferences(): ChartPreferencesContextValue {
  const value = useContext(ChartPreferencesContext);
  if (!value) throw new Error('ChartPreferencesProvider is missing.');
  return value;
}

const paletteOptions: Array<{
  id: ChartPalette;
  label: string;
  description: string;
  colors: string[];
}> = [
  {
    id: 'executive',
    label: 'Executive',
    description: 'Sobru, premium, optimizat pentru management.',
    colors: ['#4f46e5', '#0f766e', '#d97706', '#be123c'],
  },
  {
    id: 'ocean',
    label: 'Ocean',
    description: 'Albastru–turcoaz, calm și analitic.',
    colors: ['#2563eb', '#0891b2', '#0d9488', '#7c3aed'],
  },
  {
    id: 'vibrant',
    label: 'Vibrant',
    description: 'Contrast ridicat pentru prezentări și ecrane mari.',
    colors: ['#7c3aed', '#06b6d4', '#f59e0b', '#ec4899'],
  },
  {
    id: 'accessible',
    label: 'Accesibil',
    description: 'Paletă color-blind-safe și diferențiere suplimentară.',
    colors: ['#0072b2', '#e69f00', '#009e73', '#cc79a7'],
  },
  {
    id: 'monochrome',
    label: 'Monocrom',
    description: 'Elegant, discret, potrivit pentru rapoarte formale.',
    colors: ['#334155', '#64748b', '#94a3b8', '#cbd5e1'],
  },
];

function Toggle({
  checked,
  label,
  description,
  onChange,
}: {
  checked: boolean;
  label: string;
  description: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      className="chart-pref-toggle"
      aria-pressed={checked}
      onClick={() => onChange(!checked)}
    >
      <span className={`chart-pref-switch ${checked ? 'is-active' : ''}`}>
        {checked ? <Check size={11} /> : null}
      </span>
      <span>
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
    </button>
  );
}

export function ChartPreferencesButton() {
  const { preferences, update, reset } = useChartPreferences();
  const [open, setOpen] = useState(false);
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent): void => {
      if (!hostRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const handleEscape = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', close);
    window.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', close);
      window.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  return (
    <div ref={hostRef} className="chart-preferences-host">
      <button
        type="button"
        className="icon-button icon-button--topbar"
        aria-label="Personalizează graficele"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Palette size={17} />
      </button>
      {open ? (
        <section className="chart-preferences-panel" aria-label="Preferințe grafice">
          <header>
            <div>
              <span>Visual Studio</span>
              <h2>Design grafice</h2>
              <p>Preferințele se aplică tuturor modulelor și se păstrează local.</p>
            </div>
            <button
              type="button"
              className="icon-button"
              aria-label="Închide preferințele"
              onClick={() => setOpen(false)}
            >
              <X size={16} />
            </button>
          </header>

          <div className="chart-pref-section">
            <h3>
              <SlidersHorizontal size={14} /> Stil vizual
            </h3>
            <div className="chart-palette-grid">
              {paletteOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={
                    preferences.palette === option.id
                      ? 'chart-palette-card is-active'
                      : 'chart-palette-card'
                  }
                  onClick={() => update({ palette: option.id })}
                >
                  <span className="chart-palette-swatches">
                    {option.colors.map((color) => (
                      <i key={color} style={{ backgroundColor: color }} />
                    ))}
                  </span>
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </button>
              ))}
            </div>
          </div>

          <div className="chart-pref-section">
            <h3>Densitate</h3>
            <fieldset className="chart-pref-segmented">
              <legend>Densitate grafice</legend>
              <button
                type="button"
                className={preferences.density === 'comfortable' ? 'is-active' : ''}
                aria-pressed={preferences.density === 'comfortable'}
                onClick={() => update({ density: 'comfortable' })}
              >
                Aerisit
              </button>
              <button
                type="button"
                className={preferences.density === 'compact' ? 'is-active' : ''}
                aria-pressed={preferences.density === 'compact'}
                onClick={() => update({ density: 'compact' })}
              >
                Compact
              </button>
            </fieldset>
          </div>

          <div className="chart-pref-section chart-pref-toggles">
            <Toggle
              checked={preferences.showLegend}
              label="Legendă"
              description="Afișează seriile și reperele explicite."
              onChange={(showLegend) => update({ showLegend })}
            />
            <Toggle
              checked={preferences.showLabels}
              label="Etichete pe date"
              description="Util în prezentări; poate aglomera graficele dense."
              onChange={(showLabels) => update({ showLabels })}
            />
            <Toggle
              checked={preferences.smoothLines}
              label="Linii fluide"
              description="Curbe discrete pentru trenduri, fără deformarea valorilor."
              onChange={(smoothLines) => update({ smoothLines })}
            />
            <Toggle
              checked={preferences.animate}
              label="Animații"
              description="Tranziții scurte între tipuri, filtre și perioade."
              onChange={(animate) => update({ animate })}
            />
          </div>

          <footer>
            <button type="button" className="button button--ghost" onClick={reset}>
              <RotateCcw size={14} /> Resetare
            </button>
          </footer>
        </section>
      ) : null}
    </div>
  );
}
