import { useState } from 'react';
import api, { errorMessage } from './api';
import { AlertIcon, PulseIcon } from './icons';

function AuthForm({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const switchMode = (m) => {
    setMode(m);
    setError('');
  };

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
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-box">
        <div className="brand">
          <span className="brand-mark"><PulseIcon size={18} /></span>
          URL Health Monitor
        </div>
        <p className="auth-tagline">Uptime monitoring with AI incident analysis.</p>

        <form className="card auth-card" onSubmit={handleSubmit}>
          <div className="tabs" role="tablist">
            <button type="button" role="tab" aria-selected={mode === 'login'} className={`tab${mode === 'login' ? ' active' : ''}`} onClick={() => switchMode('login')}>
              Log in
            </button>
            <button type="button" role="tab" aria-selected={mode === 'register'} className={`tab${mode === 'register' ? ' active' : ''}`} onClick={() => switchMode('register')}>
              Create account
            </button>
          </div>

          <label className="field">
            Email
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" required />
          </label>
          <label className="field">
            Password
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === 'register' ? 'At least 8 characters' : '••••••••'}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={8}
              required
            />
          </label>

          {error && (
            <div className="alert alert-error" role="alert">
              <AlertIcon /> {error}
            </div>
          )}

          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default AuthForm;
