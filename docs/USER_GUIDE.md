# UniHub Insight User Guide

## Global scope

The filter bar controls period, comparison, company, RM, ASM, stores and agent. Scope is stored in the URL, so a copied link reproduces the same analysis. Selected stores dominate historical parent-company filters where the Retail identity contract requires it.

Finance and Planning do not accept agent scope. Compensation is visible only with the HR capability; Finance only with the P&L capability.

## Modules

- **Overview** — business health, target pace, forecast, contribution and priority alerts.
- **Sales** — pace, history, receipts, product/category mix and temporal patterns.
- **Performance** — rankings, consistency, volatility and entity heatmaps.
- **Campaigns** — Focus and commercial mechanism adoption/contribution.
- **Workforce** — headcount, staffing coverage, lifecycle and Grile status.
- **Compensation** — payroll, average/median, distribution and sales ratio.
- **Finance** — revenue, cost structure, EBIT, margin and monthly profitability.
- **Planning** — actual, forecast, target gap and forecast accuracy.
- **Custom** — personal and shared dashboards assembled from governed metrics.

În RC1, Sales–Planning au sub-view-uri și rețete distincte. Pace, ranking, scatter, histogramă, waterfall reconciliat, forecast și Calendar au forme native; fiecare folosește același contract pentru inspect/export. Fiecare tab afișează `LIVE`, `PARTIAL` sau `UNAVAILABLE` din metadata sursei; un mecanism fără contract nu este înlocuit cu altă metrică. Click-ul pe entități actualizează drill-ul din URL și reload-ul reproduce selecția.

## Dashboard interaction

- Use **Edit layout** to drag a card by its header and resize it from its edges.
- Use **Layout implicit** to restore the versioned default.
- Expand any card to fullscreen.
- Folosește iconul tabel pentru inspect. Inspectorul rerulează server-side exact query-ul și snapshotul widgetului și oferă CSV bounded.
- Chart toggles offer only visualizations compatible with the analytical contract.

## Custom dashboards

Start blank or clone Director, Regional Manager, Finance or Risk templates. A card selects a module, registered metric, visualization and filter policy:

- **Inherit** — uses all global filters.
- **Augment** — starts from global filters and adds/replaces specified local values.
- **Override** — ignores global business filters and uses only specified local values; period/comparison remain global.
- **Ignore** — analyzes network scope for the selected period/comparison.

Orice stare non-inherited este vizibilă pe card. Share-ul este țintit per subject cu `read/edit/admin`; capability și scope ceiling sunt reverificate server-side la read/query/inspect/export. Versiunile anterioare rămân selectabile, iar preset-urile pot fi personale sau partajate.

## Data-state interpretation

- `Demo` means deterministic development data, never production evidence.
- `PostgreSQL live` means the read-only Retail adapter supplied the result.
- Cutoff is the last covered business date, not page-load time.
- Forecast run-rate is labeled separately from persisted AI forecast.
- Missing data is not silently converted to zero.
- Calendarul Sales arată numai zile observate până la cutoff. O celulă absentă rămâne missing; returul este cantitate negativă, iar numărul afișat de magazine este observat, nu coverage complet declarat.
- Visits din Performance și Workforce folosește autorul Team Leader păstrat în vizită, nu ASM-ul magazinului. Filtrele firmă/RM/ASM/magazin folosesc ierarhia curentă; filtrul agent este incompatibil și trebuie eliminat înainte de deschiderea sub-view-ului.
- Compensation citește numai read-model-ul agregat Retail; nu există persoană/nume/CNP în contract. Cohortele sub trei persoane sunt suprimate inclusiv în inspect și export.
- `UNAVAILABLE` înseamnă că nu există o generație autoritativă eligibilă; UI nu transformă date legacy sau lipsa în zero.

## Operational actions

Insight is analytical and read-only. Use **Deschide în Retail** din modul pentru a transfera perioada, suprafața operațională și scope-ul curent către Retail; o selecție multi-store nu este redusă arbitrar la un singur magazin. Folosește Retail pentru importuri, configurări, închiderea lunii sau orice mutație business. Autorizarea este evaluată independent de Retail.
