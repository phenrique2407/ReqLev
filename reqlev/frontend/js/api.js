/**
 * ReqLev – API Client
 * Centralised wrapper around fetch() for all backend calls.
 */

const API_BASE = '';   // Same origin (FastAPI serves frontend)

const api = (() => {
  function _token() {
    return localStorage.getItem('rl_token') || '';
  }

  function _headers(extra = {}) {
    const h = { 'Content-Type': 'application/json', ...extra };
    const t = _token();
    if (t) h['Authorization'] = `Bearer ${t}`;
    return h;
  }

  async function _request(method, path, body = null, params = null) {
    let url = `${API_BASE}${path}`;
    if (params) {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([,v]) => v != null))
      );
      if (qs.toString()) url += `?${qs}`;
    }

    const opts = { method, headers: _headers() };
    if (body !== null) opts.body = JSON.stringify(body);

    try {
      const res = await fetch(url, opts);

      // Handle no-content responses (204)
      if (res.status === 204) return null;

      const data = await res.json().catch(() => ({ detail: 'Unexpected server response' }));

      if (!res.ok) {
        const msg = Array.isArray(data.detail)
          ? data.detail.map(e => e.msg).join('; ')
          : (data.detail || `HTTP ${res.status}`);
        throw new ApiError(msg, res.status);
      }

      return data;
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError('Network error – check that the server is running', 0);
    }
  }

  return {
    get:    (path, params)       => _request('GET',    path, null, params),
    post:   (path, body, params) => _request('POST',   path, body, params),
    put:    (path, body)         => _request('PUT',    path, body),
    delete: (path)               => _request('DELETE', path),

    // Raw download (PDF, etc.)
    download: async (path) => {
      const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'Authorization': `Bearer ${_token()}` },
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new ApiError(j.detail || `HTTP ${res.status}`, res.status);
      }
      return res.blob();
    },
  };
})();

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name    = 'ApiError';
    this.status  = status;
  }
}
