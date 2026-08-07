# UniHub Insight User Guide

## Global scope

The filter bar controls period, comparison, company, RM, stores and agent. RM, stores and agents are searchable multi-selects; ASM remains available only in internal drill/reconciliation contracts. Scope is stored in the URL, so a copied link reproduces the same analysis. Selected stores dominate historical parent-company filters where the Retail identity contract requires it.

Both allowlisted users can open every module and use every available business dimension. Compensation includes person-level drill and export. Finance/Planning accept agent scope only where Retail publishes a meaningful agent allocation; absence of that grain is shown as a source limitation, never as a permission denial.

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

În RC1, Sales–Planning au sub-view-uri și rețete distincte. Pace, ranking, scatter, histogramă/boxplot, waterfall reconciliat, forecast și Calendar au forme native; fiecare folosește același contract pentru inspect/export. Distribuția comută între histogramă și boxplot fără alt fetch sau alt eșantion; sub cinci agregate eligibile rămâne numai histograma. Fiecare tab afișează `LIVE`, `PARTIAL` sau `UNAVAILABLE` din metadata sursei; un mecanism fără contract nu este înlocuit cu altă metrică. Click-ul pe entități actualizează drill-ul din URL și reload-ul reproduce selecția. Dublu-click sau `Shift+Enter` deschide detaliul contextual read-only în Retail, într-un tab nou, fără schimbarea analizei curente.

## Dashboard interaction

- Use **Edit layout** to drag a card by its header and resize it from its edges.
- Use **Layout implicit** to restore the versioned default.
- Expand any card to fullscreen.
- Folosește iconul info pentru definiție/formulă/missing policy și iconul tabel pentru inspect. Inspectorul rerulează server-side exact query-ul și snapshotul widgetului și oferă CSV/XLSX bounded. `Raport complet XLSX` este exportul separat al întregului modul.
- Chart toggles offer only visualizations compatible with the analytical contract.

## Custom dashboards

Start blank or clone Director, Regional Manager, Finance or Risk templates. A card selects a module, registered metric, visualization and filter policy:

- **Inherit** — uses all global filters.
- **Augment** — starts from global filters and adds/replaces specified local values.
- **Override** — ignores global business filters and uses only specified local values; period/comparison remain global.
- **Ignore** — analyzes network scope for the selected period/comparison.

Orice stare non-inherited este vizibilă pe card. Duplicarea din vizualizare salvează atomic o versiune nouă înainte să execute query-ul nou. Share-ul este țintit per subject cu `read/edit/admin` pentru layout; nu schimbă vizibilitatea datelor, identică pentru ambii utilizatori autorizați. Versiunile anterioare rămân selectabile, iar preset-urile pot fi personale sau partajate și suportă creare, aplicare, actualizare și ștergere.

## Data-state interpretation

- `Demo` means deterministic development data, never production evidence.
- `PostgreSQL live` means the read-only Retail adapter supplied the result.
- Cutoff is the last covered business date, not page-load time.
- Forecast run-rate is labeled separately from persisted AI forecast.
- Missing data is not silently converted to zero.
- Calendarul Sales arată numai zile observate până la cutoff. O celulă absentă rămâne missing; returul este cantitate negativă, iar numărul afișat de magazine este observat, nu coverage complet declarat.
- Visits din Performance și Workforce folosește autorul Team Leader păstrat în vizită, nu ASM-ul magazinului. Filtrele firmă/RM/magazin folosesc ierarhia curentă; filtrul agent este incompatibil și trebuie eliminat înainte de deschiderea sub-view-ului.
- Compensation folosește read-model-ul Retail complet: persoane, salarii/componente, firmă, magazin, ierarhie, provenance și agregate. Nu suprimă cohorte sau persoane în UI, inspect ori export pentru utilizatorii autorizați.
- `UNAVAILABLE` înseamnă că nu există rânduri canonice Retail pentru perioada/scope-ul cerut sau sursa este inaccesibilă. Datele legacy/estimate existente rămân vizibile și etichetate corect; lipsa nu devine zero.

## Operational actions

Insight is analytical and read-only. Use **Deschide în Retail** din modul pentru a transfera perioada, suprafața operațională și scope-ul curent către Retail; o selecție multi-store nu este redusă arbitrar la un singur magazin. Folosește Retail pentru importuri, configurări, închiderea lunii sau orice mutație business. Autorizarea este evaluată independent de Retail.
