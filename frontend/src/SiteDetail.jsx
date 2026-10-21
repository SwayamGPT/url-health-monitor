import { useEffect, useState } from 'react';
import api, { errorMessage } from './api';
import ResponseChart from './ResponseChart';
import { formatMs, toDate } from './format';
import StatusPill from './StatusPill';

function SiteDetail({ site, refreshKey }) {
  const [history, setHistory] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/websites/${site.id}/history`)
      .then((res) => !cancelled && setHistory(res.data))
      .catch((err) => !cancelled && setError(errorMessage(err, 'Failed to load history')));
    return () => {
      cancelled = true;
    };
  }, [site.id, refreshKey]);

  if (error) return <div className="detail"><div className="alert alert-error">{error}</div></div>;
  if (!history) return <div className="detail muted">Loading history…</div>;
  if (history.length === 0) return <div className="detail muted">No checks yet. The first one runs within 30 seconds.</div>;

  const upCount = history.filter((h) => h.is_up).length;
  const upTimes = history.filter((h) => h.is_up && h.response_time_ms != null).map((h) => h.response_time_ms);
  const lastDown = history.find((h) => !h.is_up);

  return (
    <div className="detail">
      <div className="detail-stats">
        <div>
          <strong>{((100 * upCount) / history.length).toFixed(1)}%</strong>
          Uptime (last {history.length})
        </div>
        <div>
          <strong>{upTimes.length ? formatMs(upTimes.reduce((a, b) => a + b, 0) / upTimes.length) : '–'}</strong>
          Avg response
        </div>
        <div>
          <strong>{upTimes.length ? formatMs(Math.max(...upTimes)) : '–'}</strong>
          Slowest
        </div>
        <div>
          <strong>{lastDown ? toDate(lastDown.checked_at).toLocaleString() : 'None'}</strong>
          Last incident
        </div>
      </div>

      <ResponseChart checks={history} />

      <ul className="history">
        {history.map((h) => (
          <li key={h.id}>
            <span className="history-time">{toDate(h.checked_at).toLocaleTimeString()}</span>
            <span>
              <StatusPill isUp={h.is_up} />{' '}
              <span className="muted">{h.status_code ?? h.error ?? ''}</span>
            </span>
            <span className="history-ms">{formatMs(h.response_time_ms)}</span>
            {h.ai_summary && <span className="history-summary">{h.ai_summary}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default SiteDetail;
