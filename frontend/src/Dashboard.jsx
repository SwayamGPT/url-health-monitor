import { Fragment, useCallback, useEffect, useState } from 'react';
import api, { errorMessage } from './api';
import AskPanel from './AskPanel';
import AnalysisPanel from './AnalysisPanel';

// The API returns naive UTC timestamps; mark them as UTC so the browser converts to local time.
const toDate = (ts) => new Date(ts.endsWith('Z') ? ts : ts + 'Z');

function StatusDot({ isUp }) {
  const cls = isUp == null ? 'unknown' : isUp ? 'up' : 'down';
  return <span className={`dot ${cls}`} title={cls} />;
}

function Dashboard({ user, onLogout }) {
  const [websites, setWebsites] = useState([]);
  const [newUrl, setNewUrl] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [history, setHistory] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [busy, setBusy] = useState('');

  const fetchWebsites = useCallback(
    () =>
      api
        .get('/websites')
        .then((res) => setWebsites(res.data))
        .catch((err) => {
          if (err.response?.status === 401) onLogout();
          else setError('Failed to load websites');
        }),
    [onLogout],
  );

  const fetchHistory = useCallback(async (id) => {
    try {
      const res = await api.get(`/websites/${id}/history`);
      setHistory(res.data);
    } catch (err) {
      setError(errorMessage(err, 'Failed to load history'));
    }
  }, []);

  useEffect(() => {
    fetchWebsites();
    const interval = setInterval(fetchWebsites, 5000);
    return () => clearInterval(interval);
  }, [fetchWebsites]);

  const toggleHistory = (id) => {
    if (selectedId === id) {
      setSelectedId(null);
      return;
    }
    setSelectedId(id);
    setHistory([]);
    fetchHistory(id);
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await api.post('/websites', { url: newUrl });
      setNewUrl('');
      fetchWebsites();
    } catch (err) {
      setError(errorMessage(err, 'Failed to add website'));
    }
  };

  const handleDelete = async (site) => {
    setError('');
    try {
      await api.delete('/websites', { data: { url: site.url } });
      if (selectedId === site.id) setSelectedId(null);
      fetchWebsites();
    } catch (err) {
      setError(errorMessage(err, 'Failed to delete website'));
    }
  };

  const handleCheckAll = async () => {
    setError('');
    setBusy('check');
    try {
      const res = await api.post('/websites/check-all');
      const { checked, up, elapsed_ms } = res.data;
      setNotice(`Checked ${checked} sites concurrently in ${elapsed_ms} ms: ${up} up, ${checked - up} down`);
      fetchWebsites();
      if (selectedId) fetchHistory(selectedId);
    } catch (err) {
      setError(errorMessage(err, 'Check failed'));
    } finally {
      setBusy('');
    }
  };

  const handleAnalyze = async () => {
    setError('');
    setBusy('analyze');
    try {
      const res = await api.post('/websites/analyze');
      setAnalysis(res.data);
    } catch (err) {
      setError(errorMessage(err, 'Analysis failed'));
    } finally {
      setBusy('');
    }
  };

  return (
    <>
      <header className="row spread">
        <h1>URL Health Monitor</h1>
        <div className="row">
          <span className="muted">{user.email}</span>
          <button className="secondary" onClick={onLogout}>Log out</button>
        </div>
      </header>

      <section className="card">
        <form className="row" onSubmit={handleAdd}>
          <input
            type="text"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            placeholder="https://example.com"
            required
          />
          <button type="submit">Add</button>
          <button type="button" className="secondary" onClick={handleCheckAll} disabled={!!busy || !websites.length}>
            {busy === 'check' ? 'Checking…' : 'Check all now'}
          </button>
          <button type="button" className="secondary" onClick={handleAnalyze} disabled={!!busy || !websites.length}>
            {busy === 'analyze' ? 'Analyzing…' : 'Analyze HTML'}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
        {notice && <p className="muted">{notice}</p>}

        {websites.length === 0 ? (
          <p className="muted">No websites yet. Add one above; it is checked every 30 seconds.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>URL</th>
                <th>Code</th>
                <th>Response time</th>
                <th>Last checked</th>
                <th>Added</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {websites.map((site) => (
                <Fragment key={site.id}>
                  <tr className="clickable" onClick={() => toggleHistory(site.id)}>
                    <td><StatusDot isUp={site.is_up} /></td>
                    <td>{site.url}</td>
                    <td>{site.status_code ?? (site.is_up === false ? 'no response' : '-')}</td>
                    <td>{site.response_time_ms != null ? `${site.response_time_ms.toFixed(0)} ms` : '-'}</td>
                    <td>{site.last_checked ? toDate(site.last_checked).toLocaleTimeString() : 'Never'}</td>
                    <td>{toDate(site.created_at).toLocaleDateString()}</td>
                    <td>
                      <button
                        className="link danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(site);
                        }}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                  {site.is_up === false && site.ai_summary && (
                    <tr className="summary-row">
                      <td />
                      <td colSpan={6}><strong>Likely cause:</strong> {site.ai_summary}</td>
                    </tr>
                  )}
                  {selectedId === site.id && (
                    <tr className="history-row">
                      <td colSpan={7}>
                        {history.length === 0 ? (
                          <p className="muted">No checks yet.</p>
                        ) : (
                          <ul className="history">
                            {history.map((h) => (
                              <li key={h.id}>
                                <StatusDot isUp={h.is_up} /> {toDate(h.checked_at).toLocaleString()} ·{' '}
                                {h.status_code ?? h.error ?? 'down'} · {h.response_time_ms?.toFixed(0)} ms
                                {h.ai_summary && <div className="muted">{h.ai_summary}</div>}
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {analysis && <AnalysisPanel results={analysis} onClose={() => setAnalysis(null)} />}

      <AskPanel />
    </>
  );
}

export default Dashboard;
