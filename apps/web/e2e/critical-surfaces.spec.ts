import { expect, type Page, test } from '@playwright/test';

const routes = [
  ['/', 'Executive Overview'],
  ['/monthly-review', 'Raport lunar'],
  ['/sales', 'Sales Intelligence'],
  ['/performance', 'Performance'],
  ['/campaigns', 'Campaigns'],
  ['/workforce', 'Workforce'],
  ['/compensation', 'Compensation'],
  ['/finance', 'Finance & P&L'],
  ['/planning', 'Planning'],
  ['/dashboards', 'Custom Dashboards'],
] as const;

const moduleSubviews = [
  {
    path: '/sales',
    title: 'Sales Intelligence',
    views: [
      ['pace', 'Pace'],
      ['trend', 'Trend'],
      ['mix', 'Mix'],
      ['drivers', 'Drivers'],
      ['transactions', 'Transactions'],
      ['calendar', 'Calendar'],
    ],
  },
  {
    path: '/performance',
    title: 'Performance',
    views: [
      ['overview', 'Overview'],
      ['rankings', 'Rankings'],
      ['consistency', 'Consistency'],
      ['productivity', 'Productivity'],
      ['visits', 'Visits'],
    ],
  },
  {
    path: '/campaigns',
    title: 'Campaigns',
    views: [
      ['overview', 'Overview'],
      ['promo', 'Promo'],
      ['incentive', 'Incentive'],
      ['contest', 'Concurs'],
      ['focus', 'Focus'],
      ['folii', 'Folii'],
    ],
  },
  {
    path: '/workforce',
    title: 'Workforce',
    views: [
      ['people', 'People'],
      ['movements', 'Mișcări'],
      ['stability', 'Stability'],
      ['coverage', 'Coverage'],
      ['productivity', 'Productivity'],
      ['visits', 'Visits'],
      ['grile', 'Grile'],
    ],
  },
  {
    path: '/compensation',
    title: 'Compensation',
    views: [
      ['overview', 'Overview'],
      ['distribution', 'Distribution'],
      ['payroll-ratios', 'Payroll ratios'],
    ],
  },
  {
    path: '/finance',
    title: 'Finance & P&L',
    views: [
      ['overview', 'Overview'],
      ['trend', 'Trend'],
      ['cost-structure', 'Cost structure'],
      ['profitability', 'Profitability'],
      ['reconciliation', 'Reconciliation'],
      ['break-even', 'Break-even'],
    ],
  },
  {
    path: '/planning',
    title: 'Planning',
    views: [
      ['current', 'Current'],
      ['12-months', '12 luni'],
      ['accuracy', 'Accuracy'],
      ['scenarios', 'Scenarios'],
      ['sensitivity', 'Sensitivity'],
    ],
  },
] as const;

function collectRuntimeErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().startsWith('Failed to load resource:')) {
      errors.push(message.text());
    }
  });
  page.on('response', (response) => {
    if (
      response.status() >= 500 ||
      (response.url().includes('/api/v1/') && response.status() >= 400)
    ) {
      errors.push(`${response.status()} ${response.url()}`);
    }
  });
  return errors;
}

for (const [path, title] of routes) {
  test(`${title} renders its real route`, async ({ page }) => {
    const errors = collectRuntimeErrors(page);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`${path}?period=2026-08&range=12&comparison=previous-year`);

    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
    await expect(page.locator('.desktop-warning')).toBeHidden();
    await expect(page.locator('.page-state--error')).toHaveCount(0);
    await page.goto('about:blank');
    expect(errors).toEqual([]);
  });
}

for (const module of moduleSubviews) {
  test(`${module.title} renders every declared sub-view honestly`, async ({ page }) => {
    const errors = collectRuntimeErrors(page);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`${module.path}?period=2026-08&range=12`);
    const navigation = page.getByRole('navigation', { name: 'Sub-view analiză' });
    for (const [id, label] of module.views) {
      await navigation.getByRole('button', { name: new RegExp(`^${label}`) }).click();
      await expect(page.locator('.module-view-heading h2')).toHaveText(label);
      await expect(page).toHaveURL(new RegExp(`(?:\\?|&)subview=${id}(?:&|$)`));
      await expect(page.locator('.module-contract-state')).toBeVisible();
      await expect(page.locator('.module-unavailable, .insight-grid')).toHaveCount(1);
    }
    await page.goto('about:blank');
    expect(errors).toEqual([]);
  });
}

test('native modules render their specialized analytical forms', async ({ page }) => {
  test.slow();
  const errors = collectRuntimeErrors(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  const cases = [
    ['/sales?period=2026-08&range=12&subview=pace', 'pace', 'progress'],
    ['/sales?period=2026-08&range=12&subview=calendar', 'calendar', 'canvas'],
    ['/performance?period=2026-08&range=12&subview=rankings', 'ranking', 'canvas'],
    ['/performance?period=2026-08&range=12&subview=consistency', 'histogram', 'canvas'],
    ['/performance?period=2026-08&range=12&subview=productivity', 'scatter', 'canvas'],
    ['/campaigns?period=2026-08&range=12&subview=focus', 'focus-ranking', 'canvas'],
    ['/planning?period=2026-08&range=12&subview=12-months', 'forecast', 'canvas'],
    ['/planning?period=2026-08&range=12&subview=accuracy', 'accuracy-scatter', 'canvas'],
    ['/sales?period=2026-08&range=12&subview=transactions', 'kpi:receipts.total', '.kpi-widget'],
  ] as const;

  for (const [path, widgetId, surface] of cases) {
    await page.goto(path);
    const widget = page.locator(`[gs-id="${widgetId}"]`);
    await expect(widget).toBeVisible();
    await expect(widget.locator(surface).first()).toBeVisible();
  }

  await page.goto('about:blank');
  expect(errors).toEqual([]);
});

test('distribution reuses one eligible sample for histogram and box plot', async ({ page }) => {
  const errors = collectRuntimeErrors(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/performance?period=2026-08&range=12&subview=consistency');

  const widget = page.locator('[gs-id="histogram"]');
  const statistics = widget.locator('.module-distribution-stats');
  const statisticsText = await statistics.textContent();
  const histogram = widget.getByRole('button', { name: 'Histogramă', exact: true });
  const boxplot = widget.getByRole('button', { name: 'Box plot', exact: true });
  await expect(histogram).toHaveAttribute('aria-pressed', 'true');
  await expect(boxplot).toBeVisible();
  await boxplot.click();

  await expect(boxplot).toHaveAttribute('aria-pressed', 'true');
  await expect(widget.getByRole('img', { name: /Box plot Realizare target/ })).toBeVisible();
  expect(await statistics.textContent()).toBe(statisticsText);
  await page.goto('about:blank');
  expect(errors).toEqual([]);
});

for (const width of [1180, 1440, 1920, 2560]) {
  for (const theme of ['light', 'dark'] as const) {
    for (const density of ['comfortable', 'compact'] as const) {
      test(`performance ${width}px ${theme} ${density}`, async ({ page }) => {
        const errors = collectRuntimeErrors(page);
        await page.setViewportSize({ width, height: 1000 });
        await page.addInitScript(
          ({ dark, chartDensity }) => {
            try {
              localStorage.setItem('unihub-insight:dark', String(dark));
              localStorage.setItem(
                'unihub-insight:chart-preferences:v1',
                JSON.stringify({
                  palette: 'accessible',
                  density: chartDensity,
                  showLegend: true,
                  showLabels: false,
                  animate: false,
                  smoothLines: false,
                }),
              );
            } catch {
              // about:blank denies storage while teardown verifies chart cleanup.
            }
          },
          { dark: theme === 'dark', chartDensity: density },
        );
        await page.goto('/performance?period=2026-08&range=12&comparison=previous-year');

        await expect(page.getByRole('heading', { level: 1, name: 'Performance' })).toBeVisible();
        await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
        await expect(page.locator('[data-chart-theme]').first()).toHaveAttribute(
          'data-chart-theme',
          theme,
        );
        await expect(page.locator('[data-chart-palette]').first()).toHaveAttribute(
          'data-chart-palette',
          'accessible',
        );
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
        ).toBe(true);
        await page.goto('about:blank');
        expect(errors).toEqual([]);
      });
    }
  }
}

test('native inspector traps focus, exports safe source rows and restores focus', async ({
  page,
}) => {
  await page.goto('/sales?period=2026-08&range=12&comparison=previous-year');
  const inspect = page.getByRole('button', { name: /Inspectează datele/ }).first();
  await inspect.click();

  const dialog = page.getByRole('dialog', { name: /Vânzări/ });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'CSV server-side' })).toBeEnabled();
  await expect(dialog.locator('tbody tr')).not.toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(inspect).toBeFocused();
});

test('native chart toggles, fullscreen, PNG and XLSX actions are operational', async ({ page }) => {
  await page.goto('/sales?period=2026-08&range=12&subview=trend');
  const chartCard = page.locator('.widget-card').filter({ hasText: 'Trend' }).first();
  await chartCard.getByRole('button', { name: 'Arie' }).click();
  await expect(chartCard.getByRole('button', { name: 'Arie' })).toHaveClass(/is-active/);

  const expand = chartCard.getByRole('button', { name: /Extinde/ });
  await expand.click();
  const expanded = page.getByRole('dialog');
  await expect(expanded).toBeVisible();
  const png = page.waitForEvent('download');
  await expanded.getByRole('button', { name: /Descarcă PNG/ }).click();
  await expect((await png).suggestedFilename()).toMatch(/\.png$/);
  await page.keyboard.press('Escape');
  await expect(expanded).toBeHidden();
  await expect(expand).toBeFocused();

  const xlsx = page.waitForEvent('download');
  await page.getByRole('button', { name: /Excel/ }).click();
  await expect((await xlsx).suggestedFilename()).toMatch(/\.xlsx$/);
});

test('native chart supports keyboard drill and reset', async ({ page }) => {
  await page.goto('/sales?period=2026-08&range=12&subview=trend');
  const chart = page.getByRole('application', { name: /Evoluție Sales Intelligence/ });
  await chart.focus();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/(?:\?|&)drill=time%3A/);
  await chart.focus();
  await page.keyboard.press('Escape');
  await expect(page).not.toHaveURL(/(?:\?|&)drill=/);
});

test('detail shortcut opens contextual Retail without changing the analysis URL', async ({
  page,
}) => {
  await page.route('https://retail.unihub.ro/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: '<title>Retail detail</title>',
    });
  });
  await page.goto('/performance?period=2026-08&range=12&subview=rankings');
  const analysisUrl = page.url();
  const chart = page.getByRole('application', { name: 'Clasament Performance' });
  await expect(chart).toHaveAttribute('aria-keyshortcuts', 'Shift+Enter');
  await chart.focus();
  await page.keyboard.press('ArrowRight');

  const popupPromise = page.waitForEvent('popup');
  await page.keyboard.press('Shift+Enter');
  const popup = await popupPromise;
  await popup.waitForLoadState('domcontentloaded');
  const detailUrl = new URL(popup.url());
  expect(detailUrl.origin).toBe('https://retail.unihub.ro');
  expect(detailUrl.pathname).toBe('/agenti');
  expect(detailUrl.searchParams.get('source_context')).toBe('insight');
  expect(detailUrl.searchParams.get('magazin')).toBeTruthy();
  expect(page.url()).toBe(analysisUrl);
  await popup.close();
});

test('native trend renders simultaneous comparison contracts', async ({ page }) => {
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes('/api/v1/modules/sales') && response.status() === 200,
  );
  await page.goto(
    '/sales?period=2026-08&range=12&subview=trend&comparisons=target%2Cprevious-period%2Cprevious-year%2Crecent-average',
  );
  const response = await responsePromise;
  const body = (await response.json()) as {
    trend: Array<{ comparisons: Record<string, number | null> }>;
  };
  expect(Object.keys(body.trend.at(-1)?.comparisons ?? {})).toEqual(
    expect.arrayContaining(['previous-period', 'previous-year', 'recent-average']),
  );
  await expect(page.locator('.chart-widget .widget-filter-mode')).toContainText(
    'Target · Perioada precedentă · Anul trecut · Media ultimelor 3 perioade',
  );
});

test('native trend applies an exact custom range and survives reload', async ({ page }) => {
  await page.goto('/sales?period=2026-08&range=12&subview=trend');
  const controls = page.getByRole('group', { name: 'Selecție interval grafic' });
  const start = controls.getByLabel('De la');
  const end = controls.getByLabel('Până la');
  await expect(start).toBeVisible();
  await expect.poll(() => start.locator('option').count()).toBeGreaterThan(3);
  const startValues = await start
    .locator('option')
    .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value));
  expect(startValues.length).toBeGreaterThan(3);
  const selectedStart = startValues[1];
  const selectedEnd = startValues.at(-2);
  if (!selectedStart || !selectedEnd)
    throw new Error('Trendul nu oferă intervalul minim pentru QA.');
  await start.selectOption(selectedStart);
  await end.selectOption(selectedEnd);
  await controls.getByRole('button', { name: 'Aplică intervalul' }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('range')).toBe('custom');
  expect(new URL(page.url()).searchParams.get('start')).toBe(selectedStart);
  expect(new URL(page.url()).searchParams.get('end')).toBe(selectedEnd);
  expect(new URL(page.url()).searchParams.get('period')).toBe(selectedEnd);
  await page.reload();
  await expect(
    page.getByRole('group', { name: 'Selecție interval grafic' }).getByLabel('De la'),
  ).toHaveValue(selectedStart);
  await expect(page.getByRole('navigation', { name: 'Traseu drill-down' })).toContainText(
    `${selectedStart} → ${selectedEnd}`,
  );
});

test('module contextual Retail link preserves the operational scope', async ({ page }) => {
  await page.goto(
    '/sales?period=2026-08&range=custom&start=2026-03&end=2026-08&subview=trend&firm=Mobicell&regional=Nord&stores=S001&agent=Agent%20Test',
  );
  const link = page.getByRole('link', { name: /Deschide Trend în UniHub Retail/ });
  const linkHref = await link.getAttribute('href');
  if (!linkHref) throw new Error('Deep-link-ul Retail nu are href.');
  const href = new URL(linkHref);
  expect(href.origin).toBe('https://retail.unihub.ro');
  expect(href.pathname).toBe('/hub');
  expect(Object.fromEntries(href.searchParams)).toMatchObject({
    source_context: 'insight',
    section: 'history',
    period: '2026-08',
    range_start: '2026-03',
    range_end: '2026-08',
    firma: 'Mobicell',
    rm: 'Nord',
    magazin: 'S001',
    agent: 'Agent Test',
  });
});

test('drill breadcrumb survives reload and resets URL state', async ({ page }) => {
  await page.goto(
    '/sales?period=2026-08&range=12&comparison=previous-year&stores=S001&drill=store%3AS001%3AMagazin%25201',
  );
  const breadcrumb = page.getByRole('navigation', { name: 'Traseu drill-down' });
  await expect(breadcrumb).toContainText('Magazin 1');
  await page.reload();
  await expect(breadcrumb).toContainText('Magazin 1');
  await breadcrumb.getByRole('button', { name: /Reset drill/ }).click();
  await expect(breadcrumb).toBeHidden();
  await expect(page).not.toHaveURL(/(?:drill|stores)=/);
});

test('unauthorized module response is visible and bounded', async ({ page }) => {
  await page.route('**/api/v1/modules/workforce*', async (route) => {
    await route.fulfill({
      status: 403,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Capability insight:management is required.' }),
    });
  });
  await page.goto('/workforce?period=2026-08');
  await expect(page.locator('.page-state--error')).toContainText(
    'Capability insight:management is required.',
  );
});

for (const status of ['partial', 'stale'] as const) {
  test(`${status} source state is explicit and remains renderable`, async ({ page }) => {
    await page.route('**/api/v1/modules/sales*', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.meta.sources.sales.status = status;
      body.meta.sources.sales.warnings = [`Synthetic ${status} contract state for browser QA.`];
      await route.fulfill({ response, json: body });
    });
    await page.goto('/sales?period=2026-08&subview=pace');
    await expect(page.locator('.module-contract-state--partial')).toContainText('Contract parțial');
    await expect(page.locator('.insight-grid')).toBeVisible();
  });
}

test('unavailable source is fail-closed without substitute metrics', async ({ page }) => {
  await page.route('**/api/v1/modules/compensation*', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.meta.sources.compensation.status = 'unavailable';
    body.meta.sources.compensation.warnings = ['Synthetic unavailable state for browser QA.'];
    await route.fulfill({ response, json: body });
  });
  await page.goto('/compensation?period=2026-08&subview=overview');
  await expect(page.locator('.module-contract-state--unavailable')).toContainText('Contract lipsă');
  await expect(page.locator('.module-unavailable')).toContainText('nu este disponibil');
  await expect(page.locator('.insight-grid')).toHaveCount(0);
});

test('empty analytical arrays render bounded empty states', async ({ page }) => {
  await page.route('**/api/v1/modules/sales*', async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    for (const field of ['kpis', 'trend', 'distribution', 'breakdown', 'matrix', 'alerts']) {
      body[field] = [];
    }
    await route.fulfill({ response, json: body });
  });
  await page.goto('/sales?period=2026-08&subview=pace');
  await expect(page.locator('.page-state--error')).toHaveCount(0);
  await expect(page.locator('.empty-state').first()).toBeVisible();
});

test('custom dashboard blank, widget duplication, versioning and clone lifecycle', async ({
  page,
}) => {
  await page.goto('/dashboards?period=2026-08');
  await page.getByTitle('Creează dashboard gol').click();
  await expect(page.locator('.dashboard-name-input')).toHaveValue('Dashboard nou');
  await expect(page.locator('.save-message')).toContainText('Dashboard creat');

  await page.getByRole('button', { name: 'Configurare' }).click();
  await page.locator('.widget-editor-header select').selectOption('sales');
  await expect(page.locator('.widget-editor-card')).toHaveCount(1);
  const firstEditor = page.locator('.widget-editor-card').first();
  await firstEditor.getByLabel('Modul').selectOption('performance');
  await firstEditor.getByLabel('Vizualizare').selectOption('heatmap');
  await expect(firstEditor.getByRole('listbox', { name: 'Dimensiuni' })).toHaveValues([
    'store',
    'time',
  ]);
  await firstEditor.getByLabel('Legendă').uncheck();
  await firstEditor.getByLabel('Etichete').check();
  await firstEditor.getByLabel('Top N prezentat').fill('5');
  await firstEditor.getByLabel('Rezoluție PNG').selectOption('1');
  await page.getByRole('button', { name: 'Duplică cardul' }).click();
  await expect(page.locator('.widget-editor-card')).toHaveCount(2);
  await page
    .locator('.widget-editor-card')
    .first()
    .getByRole('listbox', { name: 'Comparații' })
    .selectOption(['previous-year']);
  await page.getByRole('button', { name: 'Salvează configurația' }).click();
  await expect(page.locator('.save-message')).toContainText('Dashboard salvat');
  await expect(page.locator('.dashboard-version-picker select')).toHaveValue('2');
  await expect(firstEditor.getByLabel('Top N prezentat')).toHaveValue('5');

  await page.getByRole('button', { name: 'Clonează' }).click();
  await expect(page.locator('.dashboard-name-input')).toHaveValue('Dashboard nou (copie)');
  await expect(page.locator('.save-message')).toContainText('Dashboard clonat');
  await page.getByRole('button', { name: 'Configurare' }).click();
  await expect(page.getByText('Niciun share explicit.')).toBeVisible();
  await expect(page.getByLabel('Vizibilitate')).toHaveValue('private');

  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: 'Șterge dashboard' }).click();
  await expect(
    page.locator('.dashboard-list-item').filter({ hasText: 'Dashboard nou (copie)' }),
  ).toHaveCount(0);

  await page
    .locator('.dashboard-list-item')
    .filter({ hasText: /^Dashboard nou/ })
    .click();
  await page.getByRole('button', { name: 'Configurare' }).click();
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: 'Șterge dashboard' }).click();
  await expect(
    page.locator('.dashboard-list-item').filter({ hasText: /^Dashboard nou/ }),
  ).toHaveCount(0);
});

test('custom dashboard template executes batch and exports inspected rows', async ({ page }) => {
  await page.goto('/dashboards?period=2026-08');
  await page
    .locator('.dashboard-templates')
    .getByRole('button', { name: /Regional Manager/ })
    .click();
  await expect(page.locator('.dashboard-name-input')).toHaveValue('Regional Manager');
  await expect(page.locator('.insight-grid')).toBeVisible();
  const inspect = page.getByRole('button', { name: /Inspectează datele Vânzări/ });
  await expect(inspect).toBeEnabled();
  await inspect.click();
  const dialog = page.getByRole('dialog', { name: /Vânzări/ });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('tbody tr')).not.toHaveCount(0);
  const csv = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'CSV' }).click();
  await expect((await csv).suggestedFilename()).toMatch(/\.csv$/);
  const xlsx = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'XLSX' }).click();
  await expect((await xlsx).suggestedFilename()).toMatch(/\.xlsx$/);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(inspect).toBeFocused();

  await page.getByRole('button', { name: 'Configurare' }).click();
  page.once('dialog', (confirmation) => confirmation.accept());
  await page.getByRole('button', { name: 'Șterge dashboard' }).click();
  await expect(
    page.locator('.dashboard-list-item').filter({ hasText: 'Regional Manager' }),
  ).toHaveCount(0);
});

test('canvas POC bounds 10 widgets, heatmap 100x36, scatter 5000 and repeated navigation', async ({
  context,
  page,
}, testInfo) => {
  testInfo.setTimeout(90_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/dashboards?period=2026-08&range=12');
  await page
    .locator('.dashboard-templates')
    .getByRole('button', { name: /Regional Manager/ })
    .click();
  await page.getByRole('button', { name: 'Configurare' }).click();
  const editors = page.locator('.widget-editor-card');
  const matrix = editors.nth(3);
  await expect(matrix.getByRole('listbox', { name: 'Dimensiuni' })).toHaveValues(['store', 'time']);
  await matrix.getByLabel('Limită rânduri').fill('5000');
  const scatter = editors.nth(4);
  await scatter.getByLabel('Vizualizare').selectOption('scatter');
  await scatter.getByRole('listbox', { name: 'Dimensiuni' }).selectOption('store');
  await scatter.getByLabel('Limită rânduri').fill('5000');
  for (let index = 0; index < 5; index += 1) {
    await page.locator('.widget-editor-header select').selectOption('sales');
  }
  await expect(editors).toHaveCount(10);

  await page.route('**/api/v1/query/batch*', async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as {
      results?: Array<{
        query: { visualization: string };
        dataset: { dimensions: unknown[]; rows: unknown[] } | null;
      }>;
    };
    if (!Array.isArray(body.results)) {
      await route.fulfill({ response, json: body });
      return;
    }
    for (const result of body.results) {
      if (!result.dataset) continue;
      if (result.query.visualization === 'heatmap') {
        result.dataset = {
          dimensions: [
            { id: 'x', label: 'Perioadă', kind: 'string', role: 'key' },
            { id: 'y', label: 'Entitate', kind: 'string', role: 'label' },
            { id: 'value', label: 'Realizare', kind: 'number', role: 'value' },
          ],
          rows: Array.from({ length: 36 }, (_, row) =>
            Array.from({ length: 100 }, (_unused, column) => ({
              x: `P${String(column + 1).padStart(3, '0')}`,
              y: `S${String(row + 1).padStart(3, '0')}`,
              value: 70 + ((row * 100 + column) % 41),
            })),
          ).flat(),
        };
      }
      if (result.query.visualization === 'scatter') {
        result.dataset = {
          dimensions: [
            { id: 'id', label: 'Cheie', kind: 'string', role: 'key' },
            { id: 'label', label: 'Entitate', kind: 'string', role: 'label' },
            { id: 'x', label: 'Productivitate', kind: 'number', role: 'value' },
            { id: 'y', label: 'Realizare', kind: 'number', role: 'metadata' },
          ],
          rows: Array.from({ length: 5000 }, (_unused, index) => ({
            id: `S${String(index + 1).padStart(5, '0')}`,
            label: `Entitate ${index + 1}`,
            x: 500 + (index % 1400),
            y: 70 + (index % 45),
          })),
        };
      }
    }
    await route.fulfill({ response, json: body });
  });

  await page.getByRole('button', { name: 'Salvează configurația' }).click();
  await expect(page.locator('.save-message')).toContainText('Dashboard salvat');
  const renderStart = await page.evaluate(() => performance.now());
  await page.getByRole('button', { name: 'Vizualizare' }).click();
  await expect
    .poll(() =>
      page
        .locator('.widget-card')
        .filter({ hasText: 'Matrice magazine' })
        .locator('canvas')
        .count(),
    )
    .toBeGreaterThanOrEqual(1);
  await expect
    .poll(() =>
      page.locator('.widget-card').filter({ hasText: 'Clasament' }).locator('canvas').count(),
    )
    .toBeGreaterThanOrEqual(1);
  const canvasCount = await page.locator('.configured-chart canvas').count();
  const firstRenderMs = await page.evaluate((start) => performance.now() - start, renderStart);
  await page.waitForTimeout(750);
  const cdp = await context.newCDPSession(page);
  await cdp.send('HeapProfiler.collectGarbage');
  await page.waitForTimeout(250);
  const resizeMeasurement = await page.evaluate(async () => {
    const grid = document.querySelector<HTMLElement>('.insight-grid');
    if (!grid) return { interactionDurations: [], maxFrameGaps: [] };
    const durations: number[] = [];
    const maxFrameGaps: number[] = [];
    const widths = Array.from(
      { length: 20 },
      (_unused, index) => ['82%', '94%', '76%', '100%', '88%'][index % 5],
    );
    for (const width of widths) {
      const started = performance.now();
      grid.style.width = width;
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      );
      durations.push(performance.now() - started);
      let previousFrame = performance.now();
      const observeUntil = previousFrame + 240;
      let maxFrameGap = 0;
      while (performance.now() < observeUntil) {
        const currentFrame = await new Promise<number>((resolve) => requestAnimationFrame(resolve));
        maxFrameGap = Math.max(maxFrameGap, currentFrame - previousFrame);
        previousFrame = currentFrame;
      }
      maxFrameGaps.push(maxFrameGap);
    }
    grid.style.removeProperty('width');
    return { interactionDurations: durations, maxFrameGaps };
  });
  const resizeDispatchSamples = resizeMeasurement.interactionDurations;
  const orderedFrameGaps = [...resizeMeasurement.maxFrameGaps].sort((left, right) => left - right);
  const resizeP95 =
    orderedFrameGaps[Math.ceil(orderedFrameGaps.length * 0.95) - 1] ?? Number.POSITIVE_INFINITY;
  await cdp.send('HeapProfiler.collectGarbage');
  const memoryBefore = await page.evaluate(
    () =>
      (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory
        ?.usedJSHeapSize ?? 0,
  );
  for (let index = 0; index < 3; index += 1) {
    await page.getByRole('button', { name: 'Configurare' }).click();
    await expect(editors).toHaveCount(10);
    await page.getByRole('button', { name: 'Vizualizare' }).click();
    await expect
      .poll(() => page.locator('.configured-chart canvas').count())
      .toBeGreaterThanOrEqual(2);
  }
  await cdp.send('HeapProfiler.collectGarbage');
  const memoryAfter = await page.evaluate(
    () =>
      (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory
        ?.usedJSHeapSize ?? 0,
  );
  const evidence = {
    widgetCount: 10,
    canvasCount,
    heatmapCells: 3600,
    scatterPoints: 5000,
    firstRenderMs,
    resizeDispatchSamples,
    resizeBlockingSamples: resizeMeasurement.maxFrameGaps,
    resizeP95,
    memoryBefore,
    memoryAfter,
    memoryGrowth: memoryBefore && memoryAfter ? memoryAfter - memoryBefore : null,
  };
  console.info(`[canvas-poc] ${JSON.stringify(evidence)}`);
  await testInfo.attach('canvas-performance.json', {
    body: JSON.stringify(evidence, null, 2),
    contentType: 'application/json',
  });
  expect(firstRenderMs).toBeLessThan(8000);
  expect(resizeP95).toBeLessThan(200);
  if (memoryBefore && memoryAfter)
    expect(memoryAfter - memoryBefore).toBeLessThan(64 * 1024 * 1024);

  await page.unrouteAll({ behavior: 'wait' });
  await page.getByRole('button', { name: 'Configurare' }).click();
  page.once('dialog', (confirmation) => confirmation.accept());
  await page.getByRole('button', { name: 'Șterge dashboard' }).click();
  await expect(
    page.locator('.dashboard-list-item').filter({ hasText: 'Regional Manager' }),
  ).toHaveCount(0);
});
