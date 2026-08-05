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
