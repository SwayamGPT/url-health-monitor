import { useState } from 'react';
import api, { errorMessage } from './api';
import { displayUrl, toDate } from './format';
import { AlertIcon, SparkIcon } from './icons';

const SUGGESTIONS = [
  'Which sites went down today and why?',
  'What is the uptime of each site?',
  'Which site is the slowest?',
];

function AskPanel() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const ask = async (q) => {
    setError('');
    setBusy(true);
    try {
      const res = await api.post('/ask', { question: q });
      setResult(res.data);
    } catch (err) {
      setError(errorMessage(err, 'Failed to get an answer'));
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    ask(question);
  };

  return (
    <section className="card">
      <div className="card-head">
        <h2>Ask about your monitoring history</h2>
        <span className="muted">Answers are generated from your recorded checks</span>
      </div>
      <div className="card-body">
        <form className="ask-form" onSubmit={handleSubmit}>
          <input
            className="input"
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="When did example.com go down last week and why?"
            aria-label="Question"
            minLength={3}
            required
          />
          <button type="submit" className="btn btn-primary" disabled={busy}>
            <SparkIcon className={busy ? 'spin' : undefined} /> {busy ? 'Thinking…' : 'Ask'}
          </button>
        </form>
        <div className="chips">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className="chip"
              disabled={busy}
              onClick={() => {
                setQuestion(s);
                ask(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginTop: 16 }} role="alert">
            <AlertIcon /> {error}
          </div>
        )}
        {result && (
          <div className="answer">
            <p className="answer-text">{result.answer}</p>
            {result.sources.length > 0 && (
              <details>
                <summary>Based on {result.sources.length} check records</summary>
                <ul>
                  {result.sources.map((s) => (
                    <li key={s.check_id}>
                      {toDate(s.checked_at).toLocaleString()} · {displayUrl(s.url)} · {s.is_up ? 'up' : 'down'}
                      {s.status_code != null && ` (${s.status_code})`}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

export default AskPanel;
