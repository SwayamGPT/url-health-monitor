import axios from 'axios';

// withCredentials sends the httpOnly auth cookie; JS never sees the token itself.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
});

export const errorMessage = (err, fallback) => {
  const detail = err.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ');
  return detail || fallback;
};

export default api;
