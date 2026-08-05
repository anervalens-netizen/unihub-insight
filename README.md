# UniHub Insight

**UniHub Insight** este aplicația desktop de analiză și business intelligence a ecosistemului UniHub. Citește adevărul operațional din UniHub Retail și îl transformă în dashboarduri manageriale configurabile, rapide și explicabile.

> Retail operează businessul. Insight îl analizează.

## Starea curentă

Versiunea inițială `0.1.0` livrează fundația tehnică și primul vertical slice:

- shell desktop full-width, fără limitările mobile din UniHub Retail;
- rutare tipizată și filtre globale păstrate în URL;
- Overview funcțional cu KPI, evoluție cumulată, contribuții, risc și alerte;
- canvas GridStack pe 24 de coloane, drag & resize, mod View/Edit și layout persistent;
- ECharts 6 modular, încărcat doar pe pagina analitică;
- TanStack Query, Router și Table;
- API FastAPI separat, cu mod demo determinist și adaptor PostgreSQL read-only;
- contracte API validate, health checks, teste și bugete explicite de performanță;
- documentație canonică, roadmap și ADR-uri.

## Stack

| Zonă | Tehnologie |
| --- | --- |
| Runtime web | Node.js 24 LTS |
| Frontend | React 19.2, TypeScript 7, Vite 8.1 |
| Rutare / URL state | TanStack Router |
| Server state | TanStack Query |
| Grafice | Apache ECharts 6.1, import modular |
| Dashboard layout | GridStack 13 |
| Tabele | TanStack Table + TanStack Virtual |
| API | FastAPI 0.139, Pydantic v2 |
| Date | PostgreSQL prin `asyncpg`, rol read-only |
| Tooling Python | Python 3.13, uv, Ruff, mypy, pytest |
| Testare web | Vitest; browser E2E intră la integrarea live |

## Pornire locală

Cerințe: Node.js 24, npm 11, Python 3.13 și `uv`.

```bash
cp .env.example .env
npm install
uv sync --project apps/api --all-groups
npm run dev
```

- Web: `http://localhost:3100`
- API: `http://localhost:8100`
- OpenAPI: `http://localhost:8100/docs`

Modul implicit este `demo`, deci aplicația pornește fără baza de date Retail.

## Conectare la PostgreSQL UniHub

Creează prin `ops/postgres/roles-before-migration.sql.template` autorități
NOLOGIN și login-uri de proces separate. Login-ul analitic are
`default_transaction_read_only=on` și acces `SELECT` numai la read models
aprobate; nu primește acces raw la tranzacții. Apoi:

```env
UNIHUB_INSIGHT_DATA_MODE=postgres
UNIHUB_INSIGHT_DATABASE_URL=postgresql://unihub_insight_api_reader:...@host:5432/unihub
```

API-ul mai impune `default_transaction_read_only=on`, `statement_timeout` și un pool limitat. Insight nu execută importuri, DDL sau mutații business.

## Comenzi

```bash
npm run dev
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify
```

## Documentație

- [Arhitectură](APP_ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Specificație produs](docs/PRODUCT_SPEC.md)
- [Contracte de date](docs/DATA_CONTRACTS.md)
- [Sistem de design](docs/DESIGN_SYSTEM.md)
- [Deploy](docs/DEPLOYMENT.md)
- [Autorizare și date sensibile](docs/AUTHORIZATION.md)

## Principii

1. O singură definiție pentru fiecare metrică.
2. Filtrele importante sunt serializabile și partajabile prin URL.
3. Clientul cere metrici și dimensiuni aprobate; nu trimite SQL.
4. Datele lipsă nu devin zero implicit.
5. Orice card arată perioada, scope-ul și cutoff-ul datelor.
6. Insight rămâne read-only; mutațiile se deschid în UniHub Retail.
7. Se optimizează pe bază de măsurători, nu prin infrastructură prematură.
