import { useCallback, useEffect, useState } from 'react';
import api from './api';
import AuthForm from './AuthForm';
import Dashboard from './Dashboard';
import './App.css';

function App() {
  // undefined = still checking the session cookie, null = logged out
  const [user, setUser] = useState(undefined);

  const loadUser = useCallback(
    () =>
      api
        .get('/me')
        .then((res) => setUser(res.data))
        .catch(() => setUser(null)),
    [],
  );

  const handleLogout = useCallback(async () => {
    try {
      await api.post('/logout');
    } finally {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <main className="app">
      {user === undefined ? (
        <p className="muted">Loading…</p>
      ) : user ? (
        <Dashboard user={user} onLogout={handleLogout} />
      ) : (
        <>
          <h1>URL Health Monitor</h1>
          <AuthForm onLogin={loadUser} />
        </>
      )}
    </main>
  );
}

export default App;
