import { useState } from 'react';
import api, { errorMessage } from './api';

function AuthForm({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'register') {
        await api.post('/register', { email, password });
      }
      // /token expects OAuth2 form fields, not JSON.
      await api.post('/token', new URLSearchParams({ username: email, password }));
      onLogin();
    } catch (err) {
      setError(errorMessage(err, mode === 'login' ? 'Login failed' : 'Registration failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card auth" onSubmit={handleSubmit}>
      <h2>{mode === 'login' ? 'Log in' : 'Create account'}</h2>
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" required />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password (min 8 characters)"
        minLength={8}
        required
      />
      <button type="submit" disabled={busy}>{mode === 'login' ? 'Log in' : 'Register'}</button>
      {error && <p className="error">{error}</p>}
      <button type="button" className="link" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
        {mode === 'login' ? 'Need an account? Register' : 'Have an account? Log in'}
      </button>
    </form>
  );
}

export default AuthForm;
