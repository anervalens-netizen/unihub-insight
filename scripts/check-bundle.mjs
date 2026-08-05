import { readdir, readFile, stat } from 'node:fs/promises';
import { basename, extname, join, relative, resolve } from 'node:path';
import { gzipSync } from 'node:zlib';

const root = resolve('apps/web/dist');
const assets = join(root, 'assets');
const kib = 1024;

const budgets = {
  singleJavaScriptGzip: 250 * kib,
  totalJavaScriptGzip: 475 * kib,
  totalCssGzip: 20 * kib,
  routeJavaScriptGzip: 12 * kib,
};

async function filesRecursively(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await filesRecursively(path)));
    else files.push(path);
  }
  return files;
}

function format(bytes) {
  return `${(bytes / kib).toFixed(2)} KiB`;
}

function fail(message, failures) {
  failures.push(message);
  console.error(`✗ ${message}`);
}

const rootStats = await stat(root).catch(() => null);
if (!rootStats?.isDirectory()) {
  throw new Error('Production build is missing. Run `npm run build` before bundle:check.');
}

const files = await filesRecursively(assets);
const rows = [];
for (const path of files) {
  const extension = extname(path);
  if (extension !== '.js' && extension !== '.css') continue;
  const content = await readFile(path);
  rows.push({
    path: relative(root, path),
    file: basename(path),
    extension,
    raw: content.byteLength,
    gzip: gzipSync(content, { level: 9 }).byteLength,
  });
}

const failures = [];
const JavaScript = rows.filter((row) => row.extension === '.js');
const css = rows.filter((row) => row.extension === '.css');
const totalJavaScriptGzip = JavaScript.reduce((sum, row) => sum + row.gzip, 0);
const totalCssGzip = css.reduce((sum, row) => sum + row.gzip, 0);

for (const row of JavaScript) {
  if (row.gzip > budgets.singleJavaScriptGzip) {
    fail(
      `${row.path} is ${format(row.gzip)} gzip; single-chunk budget is ${format(budgets.singleJavaScriptGzip)}.`,
      failures,
    );
  }
  const isRouteChunk =
    /(?:OverviewPage|AnalyticsModulePage|MonthlyReviewPage|CustomDashboardsPage)-/.test(row.file);
  if (isRouteChunk && row.gzip > budgets.routeJavaScriptGzip) {
    fail(
      `${row.path} is ${format(row.gzip)} gzip; route budget is ${format(budgets.routeJavaScriptGzip)}.`,
      failures,
    );
  }
}

if (totalJavaScriptGzip > budgets.totalJavaScriptGzip) {
  fail(
    `Total JavaScript is ${format(totalJavaScriptGzip)} gzip; budget is ${format(budgets.totalJavaScriptGzip)}.`,
    failures,
  );
}
if (totalCssGzip > budgets.totalCssGzip) {
  fail(
    `Total CSS is ${format(totalCssGzip)} gzip; budget is ${format(budgets.totalCssGzip)}.`,
    failures,
  );
}

console.log('\nProduction bundle (gzip):');
for (const row of rows.sort((left, right) => right.gzip - left.gzip)) {
  console.log(`  ${row.path.padEnd(58)} ${format(row.gzip).padStart(11)}`);
}
console.log(`\n  JavaScript total: ${format(totalJavaScriptGzip)} / ${format(budgets.totalJavaScriptGzip)}`);
console.log(`  CSS total:        ${format(totalCssGzip)} / ${format(budgets.totalCssGzip)}`);

if (failures.length > 0) {
  throw new Error(`${failures.length} production bundle budget${failures.length === 1 ? '' : 's'} exceeded.`);
}
console.log('✓ Production bundle budgets passed.');
