function StatusPill({ isUp }) {
  if (isUp == null) return <span className="pill pill-pending">Pending</span>;
  return isUp ? <span className="pill pill-up">Up</span> : <span className="pill pill-down">Down</span>;
}

export default StatusPill;
