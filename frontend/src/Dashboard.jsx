import { Fragment, useCallback, useEffect, useState } from 'react';
import api, { errorMessage } from './api';
import AskPanel from './AskPanel';
import AnalysisPanel from './AnalysisPanel';
import SiteDetail from './SiteDetail';
import StatusPill from './StatusPill';
import { displayUrl, formatMs, timeAgo } from './format';
import {
  AlertIcon,
  ChevronIcon,
  CloseIcon,
  GlobeIcon,
  LogoutIcon,
  PlusIcon,
  PulseIcon,
  RefreshIcon,
  ScanIcon,
  TrashIcon,
} from './icons';

function Dashboard({ user, onLogout }) {
  const [websites, setWebsites] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [newUrl, setNewUrl] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [busy, setBusy] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const fetchWebsites = useCallback(
    () =>
      api
        .get('/websites')
        .then((res) => {
          setWebsites(res.data);
          setNow(Date.now());
          setLoaded(true);
        })
        .catch((err) => {
          if (err.response?.status === 401) onLogout();
          else setError('Failed to load websites');
        }),
    [onLogout],
  );

  useEffect(() => {
    fetchWebsites();
    const interval = setInterval(fetchWebsites, 5000);
    return () => clearInterval(interval);
  }, [fetchWebsites]);

  const handleAdd = async (e) => {
    e.preventDefault();
    setError('');
    let url = newUrl.trim();
    if (url && !/^https?:\/\//i.test(url)) url = `https://${url}`;
    setBusy('add');
    try {
      await api.post('/websites', { url });
      setNewUrl('');
      await fetchWebsites();
    } catch (err) {
      setError(errorMessage(err, 'Failed to add website'));
    } finally {
      setBusy('');
    }
  };

  const handleDelete = async (site) => {
    if (!window.confirm(`Stop monitoring ${displayUrl(site.url)}? Its history will be deleted.`)) return;
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
      setNotice(`Checked ${checked} sites concurrently in ${formatMs(elapsed_ms)}: ${up} up, ${checked - up} down.`);
      await fetchWebsites();
      setRefreshKey((k) => k + 1);
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

  const checked = websites.filter((w) => w.is_up != null);
  const up = checked.filter((w) => w.is_up).length;
  const down = checked.length - up;
  const upTimes = websites.filter((w) => w.is_up && w.response_time_ms != null).map((w) => w.response_time_ms);
  const avgMs = upTimes.length ? upTimes.reduce((a, b) => a + b, 0) / upTimes.length : null;

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark"><PulseIcon size={18} /></span>
            URL Health Monitor
          </div>
          <div className="user">
            <span className="avatar">{user.email[0]}</span>
            <span className="user-email">{user.email}</span>
            <button className="btn btn-ghost" onClick={onLogout} title="Log out">
              <LogoutIcon /> <span className="hide-sm">Log out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="container">
        <div className="page-head">
          <div>
            <h1>Dashboard</h1>
            <p className="subtle">Sites are checked automatically every 30 seconds.</p>
          </div>
          <div className="actions">
            <button className="btn btn-secondary" onClick={handleCheckAll} disabled={!!busy || !websites.length}>
              <RefreshIcon className={busy === 'check' ? 'spin' : undefined} />
              {busy === 'check' ? 'Checking…' : 'Check now'}
            </button>
            <button className="btn btn-secondary" onClick={handleAnalyze} disabled={!!busy || !websites.length}>
              <ScanIcon className={busy === 'analyze' ? 'spin' : undefined} />
              {busy === 'analyze' ? 'Analyzing…' : 'Analyze HTML'}
            </button>
          </div>
        </div>

        <section className="stats">
          <div className="card stat">
            <div className="stat-label">Monitored sites</div>
            <div className="stat-value">{websites.length}</div>
          </div>
          <div className="card stat">
            <div className="stat-label"><span className="pill pill-up">Up</span></div>
            <div className="stat-value">{up}</div>
          </div>
          <div className="card stat">
            <div className="stat-label"><span className="pill pill-down">Down</span></div>
            <div className="stat-value">{down}</div>
          </div>
          <div className="card stat">
            <div className="stat-label">Avg response (up sites)</div>
            <div className="stat-value">
              {avgMs == null ? '–' : avgMs >= 1000 ? (avgMs / 1000).toFixed(1) : Math.round(avgMs)}
              {avgMs != null && <small>{avgMs >= 1000 ? 's' : 'ms'}</small>}
            </div>
          </div>
        </section>

        {error && (
          <div className="alert alert-error" role="alert">
            <AlertIcon /> {error}
            <button className="alert-dismiss" onClick={() => setError('')} aria-label="Dismiss"><CloseIcon size={14} /></button>
          </div>
        )}
        {notice && (
          <div className="alert alert-info">
            {notice}
            <button className="alert-dismiss" onClick={() => setNotice('')} aria-label="Dismiss"><CloseIcon size={14} /></button>
          </div>
        )}

        <section className="card">
          <div className="card-head">
            <h2>Websites</h2>
            <form className="add-form" onSubmit={handleAdd}>
              <input
                className="input"
                type="text"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="https://example.com"
                aria-label="URL to monitor"
                required
              />
              <button type="submit" className="btn btn-primary" disabled={busy === 'add'}>
                <PlusIcon /> Add site
              </button>
            </form>
          </div>

          {!loaded ? (
            <div className="empty">Loading…</div>
          ) : websites.length === 0 ? (
            <div className="empty">
              <div className="empty-icon"><GlobeIcon size={22} /></div>
              <h3>No websites yet</h3>
              <p>Add a URL above to start monitoring its uptime and response time.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="sites-table">
                <thead>
                  <tr>
                    <th>Website</th>
                    <th>Status</th>
                    <th className="hide-sm">Code</th>
                    <th className="num">Response</th>
                    <th className="hide-md">Last checked</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {websites.map((site) => {
                    const selected = selectedId === site.id;
                    return (
                      <Fragment key={site.id}>
                        <tr
                          className={`site-row${selected ? ' selected' : ''}`}
                          onClick={() => setSelectedId(selected ? null : site.id)}
                          aria-expanded={selected}
                        >
                          <td>
                            <div className="site-host">
                              <ChevronIcon className="chevron" />
                              <span className="site-url">{displayUrl(site.url)}</span>
                            </div>
                            {site.is_up === false && site.ai_summary && (
                              <div className="cause">
                                <AlertIcon size={14} />
                                <span>{site.ai_summary}</span>
                              </div>
                            )}
                          </td>
                          <td><StatusPill isUp={site.is_up} /></td>
                          <td className="hide-sm nowrap">{site.status_code ?? (site.is_up === false ? 'No response' : '–')}</td>
                          <td className="num">{formatMs(site.response_time_ms)}</td>
                          <td className="hide-md muted">{site.last_checked ? timeAgo(site.last_checked, now) : 'Never'}</td>
                          <td className="num">
                            <button
                              className="btn-icon"
                              title="Remove"
                              aria-label={`Remove ${displayUrl(site.url)}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDelete(site);
                              }}
                            >
                              <TrashIcon />
                            </button>
                          </td>
                        </tr>
                        {selected && (
                          <tr>
                            <td colSpan={6} className="detail-cell">
                              <SiteDetail site={site} refreshKey={`${refreshKey}-${site.last_checked}`} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {analysis && <AnalysisPanel results={analysis} onClose={() => setAnalysis(null)} />}

        <AskPanel />
      </main>
    </>
  );
}

export default Dashboard;
