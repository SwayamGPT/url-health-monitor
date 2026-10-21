function AnalysisPanel({ results, onClose }) {
  return (
    <section className="card">
      <div className="row spread">
        <h2>HTML analysis</h2>
        <button className="link" onClick={onClose}>Close</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>URL</th>
            <th>Title</th>
            <th>Size</th>
            <th>Words</th>
            <th>Links</th>
            <th>Images (no alt)</th>
            <th>Scripts</th>
            <th>Meta desc.</th>
            <th>Top words</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <tr key={r.website_id}>
              <td>{r.url}</td>
              {r.error ? (
                <td colSpan={8} className="error">{r.error}</td>
              ) : (
                <>
                  <td>{r.title ?? '-'}</td>
                  <td>{(r.page_size_bytes / 1024).toFixed(1)} KB</td>
                  <td>{r.word_count}</td>
                  <td>{r.link_count}</td>
                  <td>{r.image_count} ({r.images_missing_alt})</td>
                  <td>{r.script_count}</td>
                  <td>{r.has_meta_description ? 'yes' : 'no'}</td>
                  <td>{r.top_words.slice(0, 5).map(([w]) => w).join(', ')}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default AnalysisPanel;
