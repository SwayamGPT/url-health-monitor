import axios from 'axios';

// withCredentials sends the httpOnly auth cookies; JS never sees the tokens themselves.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
});

const NO_REFRESH = ['/token', '/register', '/refresh', '/logout'];

// One in-flight refresh shared by every request that hit a 401 at the same time,
// so a burst of requests doesn't rotate the refresh token several times.
let refreshing = null;

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    if (err.response?.status !== 401 || !original || original._retried || NO_REFRESH.includes(original.url)) {
      throw err;
    }
    original._retried = true;
    refreshing ??= api.post('/refresh').finally(() => {
      refreshing = null;
    });
    try {
      await refreshing;
    } catch {
      throw err; // refresh failed: surface the original 401 so the app logs out
    }
    return api(original);
  },
);

export const errorMessage = (err, fallback) => {
  const detail = err.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ');
  return detail || fallback;
};

export default api;
