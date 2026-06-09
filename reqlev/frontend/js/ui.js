/**
 * ReqLev – UI Helpers
 * Toast notifications, modal dialog, global loader, DOM helpers.
 */

// ── Toast ────────────────────────────────────────────────────────────────────

const toast = (() => {
  const ICONS = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };

  function show(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span class="toast-icon">${ICONS[type] || 'ℹ'}</span><span>${message}</span>`;
    container.appendChild(el);

    setTimeout(() => {
      el.style.opacity    = '0';
      el.style.transform  = 'translateY(12px)';
      el.style.transition = 'opacity .3s, transform .3s';
      setTimeout(() => el.remove(), 300);
    }, duration);
  }

  return {
    success: (msg, d) => show(msg, 'success', d),
    error:   (msg, d) => show(msg, 'error',   d),
    info:    (msg, d) => show(msg, 'info',     d),
    warning: (msg, d) => show(msg, 'warning',  d),
  };
})();


// ── Modal ────────────────────────────────────────────────────────────────────

const modal = (() => {
  const overlay = () => document.getElementById('modal-overlay');
  const box     = () => document.getElementById('modal-box');

  function open(title, bodyHTML, footerHTML = '') {
    box().innerHTML = `
      <div class="modal-header">
        <h2 class="modal-title">${title}</h2>
        <button class="modal-close" onclick="modal.close()" aria-label="Fechar">✕</button>
      </div>
      <div class="modal-body">${bodyHTML}</div>
      ${footerHTML ? `<div class="modal-footer">${footerHTML}</div>` : ''}
    `;
    overlay().classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Close on backdrop click
    overlay().onclick = e => { if (e.target === overlay()) close(); };
  }

  function close() {
    overlay().classList.add('hidden');
    document.body.style.overflow = '';
    box().innerHTML = '';
  }

  function confirm(title, message, onConfirm, danger = false) {
    open(
      title,
      `<p style="color:var(--text-sub)">${message}</p>`,
      `<button class="btn btn-secondary" onclick="modal.close()">Cancelar</button>
       <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" id="modal-confirm-btn">Confirmar</button>`
    );
    setTimeout(() => {
      const btn = document.getElementById('modal-confirm-btn');
      if (btn) btn.onclick = () => { close(); onConfirm(); };
    }, 0);
  }

  return { open, close, confirm };
})();


// ── Global loader ────────────────────────────────────────────────────────────

const loader = {
  show() { document.getElementById('global-loader')?.classList.remove('hidden'); },
  hide() { document.getElementById('global-loader')?.classList.add('hidden');    },
  async wrap(fn) {
    this.show();
    try     { return await fn(); }
    finally { this.hide(); }
  },
};


// ── DOM helpers ──────────────────────────────────────────────────────────────

function el(selector, root = document) {
  return root.querySelector(selector);
}

function els(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function mount(html, targetSelector = '#app') {
  const target = document.querySelector(targetSelector);
  if (!target) return;
  target.innerHTML = html;
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });
}

function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  }) + ' ' + d.toLocaleTimeString('pt-BR', {
    hour: '2-digit', minute: '2-digit',
  });
}

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const m    = Math.floor(diff / 60_000);
  if (m < 1)  return 'agora mesmo';
  if (m < 60) return `há ${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `há ${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7)  return `há ${d}d`;
  return formatDate(dateStr);
}

function permLabel(perm) {
  if (perm === 'owner') return 'Proprietário';
  if (perm === 'edit')  return 'Editar';
  if (perm === 'view')  return 'Apenas Ver';
  return perm;
}

function permBadge(perm) {
  return `<span class="perm-badge perm-${perm}">${permLabel(perm)}</span>`;
}

function statusBadge(status) {
  const map = {
    todo:        ['badge-todo',  'A fazer'],
    in_progress: ['badge-ip',   'Em andamento'],
    done:        ['badge-done', 'Concluído'],
  };
  const [cls, label] = map[status] || ['badge-todo', status];
  return `<span class="badge ${cls}">${label}</span>`;
}

function typeBadge(type) {
  const cls = type === 'RF' ? 'badge-rf' : 'badge-rnf';
  return `<span class="badge ${cls}">${type}</span>`;
}

function avatar(username) {
  return (username || '?')[0].toUpperCase();
}

function escHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function flashEl(el) {
  if (!el) return;
  el.classList.remove('flash-update');
  void el.offsetWidth; // force reflow
  el.classList.add('flash-update');
}

// Debounce helper
function debounce(fn, ms = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
