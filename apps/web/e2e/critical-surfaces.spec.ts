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

  const dialog = page.getByRole('dialog', { name: /Sales Intelligence/ });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'CSV' })).toBeEnabled();
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

  await chartCard.getByRole('button', { name: /Extinde/ }).click();
  const expanded = page.getByRole('dialog');
  await expect(expanded).toBeVisible();
  const png = page.waitForEvent('download');
  await expanded.getByRole('button', { name: /Descarcă PNG/ }).click();
  await expect((await png).suggestedFilename()).toMatch(/\.png$/);
  await expanded.getByRole('button', { name: 'Închide' }).click();
  await expect(expanded).toBeHidden();

  const xlsx = page.waitForEvent('download');
  await page.getByRole('button', { name: /Excel/ }).click();
  await expect((await xlsx).suggestedFilename()).toMatch(/\.xlsx$/);
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
  await page.getByRole('button', { name: 'Duplică cardul' }).click();
  await expect(page.locator('.widget-editor-card')).toHaveCount(2);
  await page
    .locator('.widget-editor-card')
    .first()
    .getByRole('listbox', { name: 'Comparații' })
    .selectOption(['target', 'previous-year']);
  await page.getByRole('button', { name: 'Salvează configurația' }).click();
  await expect(page.locator('.save-message')).toContainText('Dashboard salvat');
  await expect(page.locator('.dashboard-version-picker select')).toHaveValue('2');

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
  await dialog.getByRole('button', { name: 'Închide' }).click();

  await page.getByRole('button', { name: 'Configurare' }).click();
  page.once('dialog', (confirmation) => confirmation.accept());
  await page.getByRole('button', { name: 'Șterge dashboard' }).click();
  await expect(
    page.locator('.dashboard-list-item').filter({ hasText: 'Regional Manager' }),
  ).toHaveCount(0);
});
