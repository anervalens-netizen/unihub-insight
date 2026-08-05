---
title: UniHub Insight roadmap integrat
status: active
baseline_date: 2026-08-05
candidate: 1.0.0-rc.1
---

# Roadmap integrat UniHub Insight

Roadmapul urmărește un singur obiectiv persistent: transformarea aplicației live într-un cockpit managerial complet peste adevărul UniHub Retail. Nu este un calendar pe luni și nu declară drept module finalizate paginile care refolosesc șablonul generic.

Planul executabil și Definition of Done sunt în [Planul integrat](docs/PLAN_DEZVOLTARE_INTEGRAT.md). Acest fișier este registrul scurt de realitate și închidere.

## Realitate la baseline

| Zonă | Stare | Următorul rezultat necesar |
| --- | --- | --- |
| Runtime, deploy, Authentik, acces doar Andrei/Alexandra/Bogdan, DB read-only, monitoring | `LIVE` | păstrare și regresie continuă |
| Shell, filtre URL, Overview | `LIVE` | cross-filter/drill și semantică comună |
| Raport lunar și XLSX numeric | `LIVE` | integrare în catalogul comun de metrici/widgeturi |
| Sales, Performance, Campaigns, Workforce, Compensation, Finance, Planning | `PARȚIAL` | înlocuirea șablonului generic cu sub-view-uri și contracte proprii |
| Custom dashboards | `PARȚIAL` | query batch, editor complet, ACL per subject, preset/clone/share/versionare |
| ECharts 6.1 | `PARȚIAL` | `ChartSpec`, matrice întrebare→chart, interactions, renderer POC, accesibilitate și PNG |
| Reconciliere și QA | `PARȚIAL` | matrice completă date/roluri/browser și pilot vizual owner |

## Flux unic de livrare

```mermaid
flowchart LR
  A[Read models Retail] --> B[Metrici, dimensiuni, snapshot]
  B --> C[Query batch, inspect, export]
  C --> D[ChartSpec si interactiuni]
  D --> E[Module specializate]
  D --> F[Custom dashboards]
  E --> G[Reconciliere si QA]
  F --> G
  G --> H[Release exact SHA si acceptare owner]
```

Dependențele se implementează vertical: o suprafață ajunge `LIVE` numai când include contract de date, autorizare, UI specializat, inspect/export, reconciliere, browser QA, documentație și verificare live.

## Registru de workstream-uri

- [ ] Read-model-uri Retail v1 sunt publicate aditiv; Workforce/Visits/Campaigns rămân `partial`, iar Finance/Compensation nu au încă head eligibil.
- [ ] Catalogul și snapshotul sunt versionate; matricea metrică × dimensiune × chart este în curs de restrângere la combinații dovedite.
- [x] Query batch finit, snapshot fail-closed, deadline comun, izolare per widget, inspect și CSV server-side.
- [ ] Intervalele și URL state există; drill-ul de bază cu breadcrumb/reset/reload și comparațiile multiple din dashboard trec browser QA, dar modulul nativ nu redă încă toate comparațiile simultan și toate nivelurile de cross-filter.
- [ ] `ChartSpec` ECharts 6.1 Canvas are dataset/encode, fallback, PNG și interacțiuni de bază; POC-ul Canvas/SVG, keyboard QA și toate formele specializate rămân deschise.
- [ ] Cele șapte module au sub-view-uri/rețete distincte, dar încă reutilizează componente generice și nu acoperă toate contractele specializate din plan.
- [x] Compensation folosește exclusiv agregatul aprobat, fără persoană/nume/filtre diferențiatoare.
- [ ] Custom dashboards acoperă blank/template/clone/duplicate/layout/versionare/ACL/scope/batch, inclusiv lifecycle v1→v2 și export din inspector; editorul multi-dimensiune și toate opțiunile semantice rămân deschise.
- [ ] XLSX/CSV/PNG și audit există și acțiunile native/custom trec browser QA; paritatea metrică modul→dashboard→inspect→export nu este încă demonstrată pentru toate modulele.
- [ ] Reconcilierea, rollback B→A→B, load/concurrency și backup-ul off-host post-release trec; matricea reală a celor trei utilizatori Authentik, RUM pe 7 zile și N/N-1 acceptat rămân deschise.
- [ ] Suita Playwright trece 43/43 pentru cele 10 rute, toate sub-view-urile declarate, 1180/1440/1920/ultrawide, light/dark, densități, empty/partial/stale/unavailable/403, PNG/XLSX/CSV, drill/reload și dashboard lifecycle; pilotul vizual owner rămâne poartă distinctă.
- [ ] Acceptare vizuală owner și șapte zile curate de SLI producție.

## Porți deschise după RC1

- Finance și Compensation sunt corect `UNAVAILABLE` în producție: tabelele de generații/head nu publică încă o generație eligibilă. Datele legacy nu sunt promovate implicit.
- Migrarea Retail 047 este aditivă pentru compatibilitatea N/N-1. Granturile raw Finance/Planning se revocă numai după două release-uri de produs acceptate și rollback B→A; drill-ul tehnic între artefacte RC1 nu autorizează încă revocarea.
- RC1 este publicat ca artefact immutable, reconciliat live, restaurat izolat și acoperit de rollback fail-closed. Release-urile pre-RC1 incompatibile sunt refuzate înainte de schimbarea symlinkului.
- Promovarea `1.0.0` mai cere acceptarea vizuală owner și șapte zile curate conform [Performance Acceptance](docs/PERFORMANCE_ACCEPTANCE.md).

## Reguli de execuție

- coordonatorul deține contractele comune, mutațiile live, deploy-ul și closure;
- Terra `xhigh` auditează/implementează selectiv DB, semantică, ACL, securitate, concurență, performanță și reconciliere;
- Luna `xhigh` prin terminal primește taskuri delimitate de UI/docs/chart mapping/test/browser QA;
- maximum trei taskuri independente în paralel, ownership exclusiv pe fișiere, fără full-suite-uri duplicate;
- local-first, puține candidate integrate, un deploy pentru candidatul stabil și evidence reuse.

## Definition of 1.0

Toate modulele sunt specializate și live; read-model-urile și metrica sunt autoritative; custom dashboards folosesc același query/inspect/export; drill/cross-filter/URL/preset/share funcționează; datele se reconciliază cu Retail; accesul sensibil și exporturile trec testele negative; browser QA și pilotul vizual owner sunt acceptate; șapte zile de performanță producție ating pragurile; exact SHA, monitorizare, backup/restore, rollback, documentație și Git sunt închise.
