import type { ModuleAnalytics } from './schemas';

export function SourceMetadataStrip({ data }: { data: ModuleAnalytics }) {
  const sources = Object.values(data.meta.sources ?? {});
  return (
    <section className="module-source-strip" aria-labelledby="module-source-metadata-title">
      <h3 id="module-source-metadata-title" className="sr-only">
        Metadata surse
      </h3>
      {data.meta.range_start && data.meta.range_end ? (
        <span className="meta-chip">
          Fereastră serie: {data.meta.range_start} → {data.meta.range_end}
        </span>
      ) : null}
      {data.meta.range_start && data.meta.range_start !== data.meta.period ? (
        <span className="meta-chip">KPI/mix/ranking: {data.meta.period}</span>
      ) : null}
      {data.meta.warnings?.map((warning) => (
        <span className="meta-chip meta-chip--warning" key={warning}>
          {warning}
        </span>
      ))}
      {sources.length === 0 ? (
        <span className="meta-chip meta-chip--warning">Metadata sursă indisponibilă</span>
      ) : (
        sources.map((source) => (
          <details className="source-meta" key={source.domain}>
            <summary>
              <span>{source.domain}</span>
              <strong className={`source-status source-status--${source.status}`}>
                {source.status}
              </strong>
            </summary>
            <div>
              <span>{source.source}</span>
              <span>
                Cutoff: {source.cutoff ?? '—'} · as of: {source.as_of ?? '—'} ·{' '}
                {source.is_final ? 'final' : 'deschis'}
              </span>
              <span>
                Coverage: {source.coverage_numerator ?? '—'}/{source.coverage_denominator ?? '—'}
              </span>
              <span>
                Autoritate: {source.authority} · head {source.authority_head ?? '—'}
              </span>
              <span>
                Generație: {source.source_generation ?? '—'} · contract v{source.contract_version} ·
                rule {source.rule_version ?? '—'}
              </span>
              {source.warnings.length > 0 ? (
                <span>Warnings: {source.warnings.join(' · ')}</span>
              ) : null}
            </div>
          </details>
        ))
      )}
    </section>
  );
}
