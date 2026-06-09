/**
 * ReqLev – SSE Client
 *
 * Opens a Server-Sent Events connection for a given project and dispatches
 * a custom DOM event for every incoming event type.
 *
 * Dispatched CustomEvents (on document):
 *   rl:project_updated   – project metadata changed
 *   rl:project_deleted   – project was deleted
 *   rl:requirement_created
 *   rl:requirement_updated
 *   rl:requirement_deleted
 *   rl:permission_added
 *   rl:permission_removed
 *   rl:editing_start     – another user started editing a requirement
 *   rl:editing_stop      – another user stopped editing
 *   rl:connected         – SSE handshake complete
 *
 * All events carry `detail = { ...payload }`.
 */

const sseClient = (() => {
  let _es            = null;   // EventSource instance
  let _projectId     = null;
  let _reconnectTimer = null;
  let _closed        = false;

  const RECONNECT_DELAY = 3000;  // ms

  const EVENT_TYPES = [
    'connected',
    'project_updated',
    'project_deleted',
    'requirement_created',
    'requirement_updated',
    'requirement_deleted',
    'permission_added',
    'permission_removed',
    'editing_start',
    'editing_stop',
  ];

  function _updateIndicator(state) {
    const dot = document.querySelector('.sse-dot');
    if (!dot) return;
    dot.className = `sse-dot ${state}`;
    const label = dot.nextElementSibling;
    if (label) {
      const labels = { connected: 'ao vivo', connecting: 'conectando…', error: 'desconectado' };
      label.textContent = labels[state] || state;
    }
  }

  function connect(projectId) {
    if (_es) disconnect();

    _projectId = projectId;
    _closed    = false;
    _updateIndicator('connecting');

    const token = auth.getToken();
    const url   = `/api/sse/projects/${projectId}?token=${encodeURIComponent(token)}`;
    _es         = new EventSource(url);

    EVENT_TYPES.forEach(type => {
      _es.addEventListener(type, (e) => {
        let data;
        try { data = JSON.parse(e.data); } catch (_) { data = {}; }

        // Dispatch as CustomEvent so any view can listen
        document.dispatchEvent(new CustomEvent(`rl:${type}`, { detail: data }));
      });
    });

    _es.onopen = () => {
      _updateIndicator('connected');
      console.log(`[SSE] Connected to project ${projectId}`);
    };

    _es.onerror = () => {
      _updateIndicator('error');
      _es.close();
      _es = null;

      if (!_closed) {
        _reconnectTimer = setTimeout(() => connect(projectId), RECONNECT_DELAY);
      }
    };
  }

  function disconnect() {
    _closed = true;
    clearTimeout(_reconnectTimer);
    if (_es) { _es.close(); _es = null; }
    _projectId = null;
    _updateIndicator('error');
  }

  // ── Editing indicators (sent via regular HTTP POST to backend) ────────────

  async function signalEditing(projectId, requirementId) {
    const token = auth.getToken();
    try {
      await fetch(
        `/api/sse/projects/${projectId}/editing/start?requirement_id=${requirementId}&token=${token}`,
        { method: 'POST' }
      );
    } catch (_) { /* non-critical */ }
  }

  async function signalStopEditing(projectId, requirementId) {
    const token = auth.getToken();
    try {
      await fetch(
        `/api/sse/projects/${projectId}/editing/stop?requirement_id=${requirementId}&token=${token}`,
        { method: 'POST' }
      );
    } catch (_) { /* non-critical */ }
  }

  return { connect, disconnect, signalEditing, signalStopEditing };
})();
