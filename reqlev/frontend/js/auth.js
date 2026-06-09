/**
 * ReqLev – Auth Manager
 * Manages JWT token and current-user object in localStorage.
 * Sessions persist until explicit logout.
 */

const auth = (() => {
  const TOKEN_KEY = 'rl_token';
  const USER_KEY  = 'rl_user';

  let _user  = null;
  let _token = null;

  // ── Init ────────────────────────────────────────────────────────────────

  function init() {
    _token = localStorage.getItem(TOKEN_KEY);
    const raw = localStorage.getItem(USER_KEY);
    if (raw) {
      try { _user = JSON.parse(raw); } catch (_) { clear(); }
    }
  }

  // ── State ────────────────────────────────────────────────────────────────

  function isLoggedIn() { return !!_token && !!_user; }
  function getToken()   { return _token; }
  function getUser()    { return _user; }

  // ── Persistence ──────────────────────────────────────────────────────────

  function setSession(token, user) {
    _token = token;
    _user  = user;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY,  JSON.stringify(user));
  }

  function clear() {
    _token = null;
    _user  = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  // ── API calls ─────────────────────────────────────────────────────────────

  async function login(email, password) {
    const data = await api.post('/api/auth/login', { email, password });
    // Guardamos o token primeiro para que a próxima linha consiga usá-lo
    localStorage.setItem(TOKEN_KEY, data.access_token);
    _token = data.access_token;
    
    const user = await api.get('/api/auth/me');
    setSession(data.access_token, user);
    return user;
  }

  async function register(username, email, password) {
    const data = await api.post('/api/auth/register', { username, email, password });
    // Guardamos o token primeiro para que a próxima linha consiga usá-lo
    localStorage.setItem(TOKEN_KEY, data.access_token);
    _token = data.access_token;
    
    const user = await api.get('/api/auth/me');
    setSession(data.access_token, user);
    return user;
  }

  async function refreshUser() {
    if (!_token) return null;
    try {
      const user = await api.get('/api/auth/me');
      _user = user;
      localStorage.setItem(USER_KEY, JSON.stringify(user));
      return user;
    } catch (_) {
      clear();
      return null;
    }
  }

  function logout() {
    clear();
  }

  // Expose
  init();
  return { isLoggedIn, getToken, getUser, login, register, logout, refreshUser };
})();
