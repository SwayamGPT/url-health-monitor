import { useState } from 'react';
import api, { errorMessage } from './api';

function AskPanel() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleAsk = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const res = await api.post('/ask', { question });
      setResult(res.data);
    } catch (err) {
      setError(errorMessage(err, 'Failed to get an answer'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <h2>Ask about your monitoring history</h2>
      <form className="row" onSubmit={handleAsk}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="When did example.com go down last week and why?"
          minLength={3}
          required
        />
        <button type="submit" disabled={busy}>{busy ? 'Thinking…' : 'Ask'}</button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="answer">
          <p>{result.answer}</p>
          {result.sources.length > 0 && (
            <details>
              <summary>{result.sources.length} source checks</summary>
              <ul>
                {result.sources.map((s) => (
                  <li key={s.check_id}>
                    {new Date(s.checked_at + 'Z').toLocaleString()} · {s.url} · {s.is_up ? 'up' : 'down'}
                    {s.status_code != null && ` (${s.status_code})`}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
}

export default AskPanel;
