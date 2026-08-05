# ADR 0001 — ECharts prin `ChartSpec`

- Status: Accepted
- Data: 2026-08-05
- Domeniu: Web analytics, Custom Dashboards, inspect/export

## Context

Modulele și dashboardurile configurabile trebuie să redea aceeași metrică fără a
reinterpreta payloaduri generice în browser. Un label de chart nu este o
implementare. Datele lipsă rămân `null`, iar orice chart are alternativă
tabelară accesibilă.

## Decizie

API-ul publică un dataset finit cu `dimensions`, roluri și rânduri. Web-ul îl
transformă exclusiv prin registrul versionat `ChartSpec`:

- whitelist comună metrică × shape; o combinație necunoscută revine la tabel;
- ECharts `dataset`, `dimensions` și `encode`, fără indici de coloană ascunși;
- Canvas implicit; SVG se acceptă numai după un benchmark mai bun pe o suprafață
  cu cardinalitate mică și fără dashboard dens;
- opțiunile sunt construite intern; configurația salvată nu injectează obiecte
  ECharts, HTML, formatter JavaScript sau URL-uri;
- event adapterul emite numai chei/valori din dataset către URL state;
- ARIA, decals, contrast și backing table sunt obligatorii;
- PNG este non-persistent, cu nume și opțiuni sanitizate;
- waterfall este disponibil numai din pași reconciliabili cu start/end/helper și
  total verificat; altfel registrul livrează tabel, nu bar redenumit;
- smooth/interpolare rămâne o alegere explicită și este dezactivată pentru serii
  unde ar sugera valori inexistente.

Implementarea urmează contractele oficiale ECharts pentru
[dataset](https://echarts.apache.org/handbook/en/concepts/dataset/),
[events/actions](https://echarts.apache.org/handbook/en/concepts/event/),
[Canvas versus SVG](https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/),
[ARIA](https://echarts.apache.org/handbook/en/best-practices/aria/) și
[security](https://echarts.apache.org/handbook/en/best-practices/security/).

## Matrice semantică

| Întrebare managerială | Shape primar | Alternativă tabelară | Cardinalitate | Interacțiune | Accessibility / performanță |
| --- | --- | --- | --- | --- | --- |
| Care este valoarea și abaterea? | KPI | metrică, valoare, comparație, metadata | 1 | inspect / explicație | text complet; fără Canvas necesar |
| Cum evoluează în timp? | line; area numai pentru bandă/range | perioadă, actual, comparație, target | ≤ 36 puncte/serie, ≤ 4 serii | click interval, zoom bounded | axe/legendă ARIA; gaps pentru `null` |
| Cine conduce clasamentul? | bar orizontal | entitate, valoare, rang | top 20 implicit | click drill, sort | etichete complete în tabel; Canvas |
| Care este mixul? | donut pentru ≤ 6; treemap pentru 7–30 | categorie, valoare, pondere | max 30 | select/cross-filter | decals; categoriile mici grupate explicit |
| Unde sunt anomaliile pe două dimensiuni? | heatmap | x, y, valoare, status | POC 100×36 | hover, click celulă | paletă + text/risc, Canvas, progressive |
| Există relație între două măsuri? | scatter | entitate, x, y, mărime, status | prag documentat ≤ 5.000 | zoom, click punct | backing table sortabil; Canvas large mode după benchmark |
| Cum este distribuția? | histogram/boxplot | bandă sau quartile, count | ≤ 40 benzi / ≤ 20 grupuri | select bandă | explică quartile/outliers textual |
| Ce contribuie la variație? | waterfall real | pas, start, delta, end | ≤ 20 pași | inspect pas | total reconciliat; tabel dacă lipsesc pași |
| Care este forecastul și incertitudinea? | line + forecast band/range | perioadă, actual, forecast, lower, upper, target | ≤ 24 luni | select scenariu/interval | stil distinct actual/estimate; fără valori repetate |
| Ce se întâmplă în calendar? | calendar heatmap | dată, valoare, status | ≤ 366 zile | click zi/săptămână | etichetă dată completă și paletă redundantă |

## Bugete și gate

POC-ul final măsoară pentru 8–12 widgeturi: chunk ECharts, first render, resize,
frame time și memorie la 1180/1440/1920/ultrawide, inclusiv heatmap 100×36 și
scatter până la pragul documentat. Se păstrează Canvas dacă SVG nu demonstrează
un avantaj măsurabil. Gate-urile aplicației rămân LCP p75 < 2,5 s, INP p75 <
200 ms, task UI blocant < 200 ms și fără creștere monotonă de memorie.

## Consecințe

- modulele specializate, Custom, inspectorul și exportul folosesc aceeași
  semantică versionată;
- adăugarea unui chart cere dataset compatibil, registru, fallback și test;
- charturile decorative sau reinterpretarea locală a unei metrici sunt respinse;
- benchmarkul vizual/performance și pilotul ownerului rămân gate de release, nu
  presupuneri documentare.
