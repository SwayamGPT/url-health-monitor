import { displayUrl } from './format';
import { AlertIcon, CloseIcon } from './icons';

function AnalysisPanel({ results, onClose }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>HTML analysis</h2>
        <button className="btn btn-ghost" onClick={onClose}>
          <CloseIcon size={14} /> Close
        </button>
      </div>
      <div className="card-body analysis-grid">
        {results.map((r) => (
          <article key={r.website_id} className="analysis-card">
            <h3 title={r.title ?? undefined}>{r.title || displayUrl(r.url)}</h3>
            <div className="site-url">{displayUrl(r.url)}</div>
            {r.error ? (
              <div className="alert alert-error" style={{ marginTop: 12 }}>
                <AlertIcon size={14} /> {r.error}
              </div>
            ) : (
              <>
                <div className="metrics">
                  <div className="metric"><strong>{(r.page_size_bytes / 1024).toFixed(1)} KB</strong>Page size</div>
                  <div className="metric"><strong>{r.word_count.toLocaleString()}</strong>Words</div>
                  <div className="metric"><strong>{r.link_count}</strong>Links</div>
                  <div className="metric"><strong>{r.image_count}</strong>Images</div>
                  <div className="metric"><strong>{r.script_count}</strong>Scripts</div>
                  <div className="metric"><strong>{r.images_missing_alt}</strong>Missing alt</div>
                </div>
                <div className="tags">
                  <span className={`tag ${r.has_meta_description ? 'tag-ok' : 'tag-warn'}`}>
                    {r.has_meta_description ? 'Has meta description' : 'No meta description'}
                  </span>
                  {r.top_words.slice(0, 5).map(([w, n]) => (
                    <span key={w} className="tag">{w} · {n}</span>
                  ))}
                </div>
              </>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

export default AnalysisPanel;
