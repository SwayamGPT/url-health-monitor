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

  if (user === undefined) return <div className="loading">Loading…</div>;
  return user ? <Dashboard user={user} onLogout={handleLogout} /> : <AuthForm onLogin={loadUser} />;
}

export default App;
