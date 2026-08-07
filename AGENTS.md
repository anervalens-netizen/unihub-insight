# AGENTS.md — UniHub Insight

## Mission

Build a fast, trustworthy desktop analytics product over UniHub Retail data. Prefer clear business contracts, measurable performance and maintainable domain boundaries over visual novelty or premature infrastructure.

## Operating authority

For an explicitly requested implementation task, execute end-to-end: inspect relevant contracts, implement, test, document and publish. Do not stop at a plan when the repository can be changed safely.

## Canonical sources

1. `README.md` — product entrypoint and commands.
2. `APP_ARCHITECTURE.md` — component and data boundaries.
3. `docs/PLAN_DEZVOLTARE_INTEGRAT.md` — target product, integrated execution plan and Definition of Done.
4. `ROADMAP.md` — concise reality/closure register.
5. `docs/DATA_CONTRACTS.md` — analytical semantics.
6. `docs/adr/` — decisions that must not drift silently.
7. UniHub Retail reporting views/tables — source of business truth.

## Non-negotiable invariants

- Insight is read-only against Retail business data.
- Browser code never receives database credentials and never sends SQL.
- Missing data remains missing unless the metric contract explicitly defines a zero.
- Every analytical response carries period, scope, cutoff, source and generated time.
- Every allowlisted Insight user has full server-side access to every analytical module and all available business detail, including person-level Compensation and Finance. Authentication remains mandatory; module-specific HR/P&L roles must not hide data from an authorized user.
- A metric formula has one canonical implementation and version.
- Store selection dominates historical parent-company mapping when the source contract requires it.
- `Cartele` and distribution/TR locations stay outside normal Retail KPI calculations unless a dedicated metric says otherwise.
- Quantities are net; returns reduce volume.
- Large scans need a measured reason and a bounded deadline.
- Dashboard widgets in one render use one coherent analytical snapshot; promoted authority is preferred without hiding canonical Retail rows, and metadata cutoff/finality/provenance is per source domain.
- Compensation uses a versioned, read-only Retail contract that preserves person identity, salary values/components and all useful business dimensions in UI, inspect and export. It must not apply cohort suppression, identity masking or legacy-batch eligibility rules that hide rows already accepted by Retail.

## Architecture rules

- Web: feature modules depend on shared UI/lib; shared code must not depend on features.
- API: router → service/repository contract; no SQL in routers.
- Pydantic response models are authoritative at the API boundary.
- PostgreSQL access uses approved reporting models and parameterized queries only.
- New metrics enter through the metric catalog before appearing in widgets.
- Layout persistence is versioned and migratable.
- Avoid microservices, generic event buses, generalized caches and new databases without measured need.

## Agent orchestration

- Root/coordinator owns shared contracts, cross-repository integration, live mutations, deploy and release closure.
- Use Terra `xhigh` selectively for DB/read-models, semantic review, grants/RBAC/ACL, privacy, query plans, load gates and reconciliation.
- Use Luna `xhigh` through the terminal for bounded UI/docs/chart prototypes, fixtures, targeted tests and browser QA after contracts are frozen.
- Maximum three independent parallel lanes; never give concurrent ownership of the same contract, migration or file.
- Agents start read-only and report exact evidence. Run targeted gates per lane and one integrated gate for the unchanged final candidate.

## Completion definition

A change is complete only when behavior and error states are implemented, types remain explicit, relevant tests pass, formatting/lint/type checking/build pass, and documentation changes with semantics.

## Verification

```bash
npm run verify
```

## Delivery

Ordinary repository work may be committed directly to `main` when the user has explicitly authorized autonomous direct delivery. Keep commits intentional and avoid GitHub Actions for every small step; verification is manual by default.
