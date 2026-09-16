import { useState, useEffect } from 'react';
import axios from 'axios';

const api_url = import.meta.env.VITE_API_URL

function App() {
  const [ websites, setWebsites ] = useState([]);
  const [ newUrl, setNewUrl ] = useState("");
  const [ error, setError ] = useState("");
  const [ selectedId, setSelectedId] = useState(null);
  const [ history, setHistory ] = useState([]);

const fetchWebsites = async () =>  {
  try {
    const res = await axios.get(`${api_url}/websites`);
    setWebsites(res.data);
  } catch (err) {
    setError("Error to load websites");
  }
};

const showHistory = async (id) => {
  setSelectedId(id);
  const res = await axios.get(`${api_url}/website/${id}/history`);
  setHistory(res.data);
}

useEffect(() => {
  fetchWebsites();
  const interval = setInterval(fetchWebsites, 5000);
  return () => clearInterval(interval);
}, []);

const handleAdd = async (e) => {
  e.preventDefault();
  setError("");
  try {
    await axios.post(`${api_url}/websites`, {url: newUrl});
    setNewUrl("");
    fetchWebsites();
  } catch (err) {
    setError(err.response?.data?.detail || "Failed to add website");
  }
};

return (
  <>
  <div style={{ padding: "2rem", fontFamily: "sans-serif"}}>
    <h1>URL Health Monitor</h1>

    <form onSubmit={handleAdd}>
      <input
      type="text"
      value={newUrl}
      onChange={(e) => setNewUrl(e.target.value)}
      placeholder="https://example.com"
      />
      <button type="submit">Add</button>
    </form>
    {error && <p style={{ color: "red"}}>{error}</p>}

    <table>
      <thead>
        <tr>
          <th>URL</th>
          <th>Added</th>
          <th>Status</th>
          <th>Response time</th>
          <th>Last Checked</th>
        </tr>
      </thead>
      <tbody>
        {websites.map((site) => (
          <>
          <tr key={site.id} onClick={() => showHistory(site.id)} style={{cursor: "pointer"}}>
            {
              selectedId && (
                <ul>
                  {history.map(h => (
                    <li key={h.id}>{new Date(h.checked_at).toLocaleTimeString()} - {h.status_code ?? "down"} -  {h.response_time_ms?.toFixed(0)}ms</li>
                  ))}
                </ul>
              )
            }
            <td>{site.url}</td>
            <td>{new Date(site.created_at).toLocaleString()}</td>
            <td>
              <span style={{
                display: "inline-block",
                width: 10,
                height: 10,
                borderRadius: "50%",
                backgroundColor:
                site.is_up === "null" ? "gray" : site.is_up ? "green" : "red",
              }} />
            </td>
            <td>{site.response_time_ms ? `${site.response_time_ms.toFixed(0)} ms` : "-"}</td>
            <td>{site.last_checked ? new Date(site.last_checked).toLocaleTimeString() : "Never"}</td>
          </tr>
          </>
        ))}
      </tbody>
    </table>
  </div>
  </>
);
}

export default App;
