// The API returns naive UTC timestamps; mark them as UTC so the browser converts to local time.
export const toDate = (ts) => new Date(/Z|[+-]\d\d:\d\d$/.test(ts) ? ts : ts + 'Z');

export const formatMs = (ms) => (ms == null ? '–' : ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`);

export const timeAgo = (ts, now) => {
  const s = Math.max(0, Math.round((now - toDate(ts).getTime()) / 1000));
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};

export const displayUrl = (url) => url.replace(/^https?:\/\//, '').replace(/\/$/, '');
