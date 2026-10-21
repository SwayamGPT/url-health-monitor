import { useState } from 'react';
import { formatMs, toDate } from './format';

// Response time per check, oldest -> newest. Failed checks are drawn in the status
// "critical" color and named in the legend and tooltip, so color is never the only cue.
function ResponseChart({ checks }) {
  const [hover, setHover] = useState(null);
  const points = [...checks].reverse();
  const max = Math.max(...points.map((c) => c.response_time_ms ?? 0), 1);
  const top = niceCeil(max);
  const ticks = [top, top / 2];

  return (
    <div className="chart">
      <div className="chart-head">
        <span className="chart-title">Response time · last {points.length} checks</span>
        <div className="legend">
          <span>
            <i className="swatch" style={{ background: 'var(--bar)' }} /> Up
          </span>
          <span>
            <i className="swatch" style={{ background: 'var(--critical)' }} /> Down
          </span>
        </div>
      </div>
      <div className="plot">
        {ticks.map((t) => (
          <div key={t} className="plot-grid" style={{ top: `${100 - (t / top) * 100}%` }}>
            <span className="plot-tick">{formatMs(t)}</span>
          </div>
        ))}
        <span className="plot-tick" style={{ top: '100%' }}>0</span>
        <div className="bars" onMouseLeave={() => setHover(null)}>
          {points.map((c, i) => (
            <div key={c.id} className="bar-hit" onMouseEnter={() => setHover(i)}>
              <div
                className={`bar${c.is_up ? '' : ' down'}`}
                style={{ height: `${((c.response_time_ms ?? 0) / top) * 100}%` }}
              />
            </div>
          ))}
        </div>
        {hover != null && points[hover] && (
          <div className="tooltip" style={{ left: `${Math.min(85, Math.max(15, ((hover + 0.5) / points.length) * 100))}%` }}>
            <strong>{points[hover].is_up ? 'Up' : 'Down'}</strong> · {formatMs(points[hover].response_time_ms)}
            {points[hover].status_code != null && ` · ${points[hover].status_code}`}
            <br />
            {toDate(points[hover].checked_at).toLocaleString()}
          </div>
        )}
      </div>
      {points.length > 0 && (
        <div className="plot-x">
          <span>{toDate(points[0].checked_at).toLocaleTimeString()}</span>
          <span>{toDate(points[points.length - 1].checked_at).toLocaleTimeString()}</span>
        </div>
      )}
    </div>
  );
}

function niceCeil(v) {
  const pow = 10 ** Math.floor(Math.log10(v));
  const n = v / pow;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * pow;
}

export default ResponseChart;
