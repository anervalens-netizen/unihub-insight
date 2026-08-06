import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

import { expect, type Locator, test } from '@playwright/test';

const artifactDir = resolve(process.cwd(), '../../artifacts/browser-qa');

function savePath(name: string): string {
  mkdirSync(artifactDir, { recursive: true });
  return resolve(artifactDir, `${name}.png`);
}

async function chooseFirstTwo(control: Locator): Promise<void> {
  const checkboxes = control.locator('input[type="checkbox"]');
  await expect.poll(() => checkboxes.count()).toBeGreaterThanOrEqual(2);
  await checkboxes.nth(0).check();
  await checkboxes.nth(1).check();
}

test('Retail master filters cascade, serialize CSV, reload and reset', async ({ page }) => {
  const analyticalRequests: string[] = [];
  page.on('request', (request) => {
    if (/\/api\/v1\/(overview|modules|query\/batch|monthly-review|exports)/.test(request.url())) {
      analyticalRequests.push(request.url());
    }
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/?period=2026-08&range=12&comparison=previous-year');
  await expect(page.getByRole('heading', { level: 1, name: 'Executive Overview' })).toBeVisible();
  await expect(page.locator('.global-filters .filter-popover[data-filter-key="asm"]')).toHaveCount(
    0,
  );
  await expect(page.locator('.global-filters').getByText('ASM', { exact: true })).toHaveCount(0);
  await page.screenshot({ path: savePath('filters-light-empty-1440'), fullPage: true });

  await page
    .locator('.global-filters .filter-field')
    .filter({ hasText: 'Firmă' })
    .locator('select')
    .selectOption('MOBIUP');

  const rm = page.locator('[data-filter-key="regional"]');
  await rm.locator('summary').click();
  const rmSearch = rm.getByRole('textbox', { name: 'Caută RM' });
  await rmSearch.fill('Andrei');
  await expect(rm.locator('input[type="checkbox"]')).toHaveCount(1);
  await rm.locator('input[type="checkbox"]').first().check();
  await rmSearch.fill('Dobrogea');
  await expect(rm.locator('input[type="checkbox"]')).toHaveCount(1);
  await rm.locator('input[type="checkbox"]').first().check();
  await expect(page.locator('.global-filters .filter-popover--multi[open]')).toHaveCount(1);

  const stores = page.locator('[data-filter-key="stores"]');
  await stores.locator('summary').click();
  await expect(page.locator('.global-filters .filter-popover--multi[open]')).toHaveCount(1);
  await stores.getByRole('textbox', { name: 'Caută magazin' }).fill('București');
  await chooseFirstTwo(stores);

  const agents = page.locator('[data-filter-key="agent"]');
  await agents.locator('summary').click();
  await expect(page.locator('.global-filters .filter-popover--multi[open]')).toHaveCount(1);
  await chooseFirstTwo(agents);

  const selectedUrl = new URL(page.url());
  expect(selectedUrl.searchParams.get('regional')).toBe('Andrei Sud,Dobrogea');
  expect(selectedUrl.searchParams.get('stores')).toBe('B001,B002');
  expect(selectedUrl.searchParams.get('agent')).toMatch(/^Agent \d+,Agent \d+$/);
  expect(selectedUrl.searchParams.has('asm')).toBe(false);
  await expect
    .poll(() =>
      analyticalRequests.some((requestUrl) => {
        const params = new URL(requestUrl).searchParams;
        return (
          params.get('regional') === 'Andrei Sud,Dobrogea' &&
          params.get('stores') === 'B001,B002' &&
          Boolean(params.get('agent')) &&
          !params.has('asm')
        );
      }),
    )
    .toBe(true);

  await page.screenshot({ path: savePath('filters-light-selected-1440'), fullPage: true });
  await page.reload();
  await expect.poll(() => new URL(page.url()).searchParams.get('stores')).toBe('B001,B002');
  await expect(page.locator('[data-filter-key="regional"] summary')).toContainText('2 selectate');
  await expect(page.locator('[data-filter-key="stores"] summary')).toContainText('2 selectate');
  await expect(page.locator('[data-filter-key="agent"] summary')).toContainText('2 selectate');

  await page.goBack();
  await expect
    .poll(() => new URL(page.url()).searchParams.get('agent'))
    .not.toBe(selectedUrl.searchParams.get('agent'));
  await page.goForward();
  await expect
    .poll(() => new URL(page.url()).searchParams.get('agent'))
    .toBe(selectedUrl.searchParams.get('agent'));

  await page.getByRole('button', { name: 'Reset' }).click();
  await expect
    .poll(() => {
      const params = new URL(page.url()).searchParams;
      return [params.get('regional'), params.get('stores'), params.get('agent'), params.get('asm')];
    })
    .toEqual([null, null, null, null]);
});

for (const width of [1180, 1440, 1920, 2560] as const) {
  test(`Retail light shell remains usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/?period=2026-08&range=12');
    await expect(page.locator('.desktop-warning')).toBeHidden();
    await expect(page.locator('.brand-logo--wide')).toBeVisible();
    await expect(page.getByRole('heading', { level: 1, name: 'Executive Overview' })).toBeVisible();
    await page.screenshot({ path: savePath(`shell-light-${width}`), fullPage: true });
  });
}

test('Retail link preserves CSV scope and excludes ASM from primary context', async ({ page }) => {
  await page.goto(
    '/sales?period=2026-08&range=12&subview=trend&firm=MOBIUP&regional=Andrei%20Sud,Dobrogea&stores=B001,B002&agent=Agent%2001,Agent%2002',
  );
  const link = page.getByRole('link', { name: /Deschide Trend în UniHub Retail/ });
  await expect(link).toBeVisible();
  const href = new URL((await link.getAttribute('href')) ?? '');
  expect(href.searchParams.get('rm')).toBe('Andrei Sud,Dobrogea');
  expect(href.searchParams.get('stores')).toBe('B001,B002');
  expect(href.searchParams.get('agent')).toBe('Agent 01,Agent 02');
  expect(href.searchParams.has('asm')).toBe(false);
});
