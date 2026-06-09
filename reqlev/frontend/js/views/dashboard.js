/**
 * ReqLev – Dashboard View
 * Lists all user projects (owned + shared) and allows creating new ones.
 */

const dashboardView = {
  _projects: [],

  async render() {
    const user = auth.getUser();

    mount(`
      <div class="app-shell">
        ${this._sidebar(user)}
        <div class="main-area">
          <header class="topbar">
            <span class="topbar-title">Meus Projetos</span>
            <div class="topbar-actions">
              <button class="btn btn-primary" id="btn-new-project">
                + Novo Projeto
              </button>
            </div>
          </header>
          <div class="page-content">
            <div id="dash-stats" class="stats-bar"></div>
            <div id="dash-search" class="mb-3">
              <div class="search-wrap" style="max-width:320px">
                <span class="search-icon">🔍</span>
                <input id="project-search" type="text" class="form-input"
                       placeholder="Buscar projeto…" />
              </div>
            </div>
            <div id="projects-container">
              <div class="empty-state">
                <span class="empty-state-icon">⏳</span>
                <h3>Carregando projetos…</h3>
              </div>
            </div>
          </div>
        </div>
      </div>
    `);

    this._bindNav();
    await this._loadProjects();
    this._bindSearch();
    document.getElementById('btn-new-project')?.addEventListener('click', () => this._openCreateModal());
  },

  _sidebar(user) {
    return `
      <aside class="sidebar">
        <div class="sidebar-logo">
          <a href="#/dashboard">ReqLev<span class="logo-dot"></span></a>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-section-label">Menu</div>
          <button class="btn btn-ghost w-full" style="justify-content:flex-start;gap:10px"
                  onclick="router.go('/dashboard')">
            📁 Projetos
          </button>
        </div>
        <div class="sidebar-footer">
          <div class="sidebar-user">
            <div class="sidebar-avatar">${avatar(user?.username)}</div>
            <div>
              <div class="sidebar-username">${escHtml(user?.username)}</div>
              <div class="sidebar-email">${escHtml(user?.email)}</div>
            </div>
          </div>
          <button class="btn btn-ghost w-full" style="justify-content:flex-start"
                  onclick="dashboardView._logout()">
            ← Sair
          </button>
        </div>
      </aside>
    `;
  },

  _logout() {
    modal.confirm(
      'Sair da conta',
      'Tem certeza que deseja sair?',
      () => { auth.logout(); router.go('/login'); }
    );
  },

  async _loadProjects() {
    try {
      this._projects = await api.get('/api/projects');
      this._renderProjects(this._projects);
      this._renderStats(this._projects);
    } catch (err) {
      document.getElementById('projects-container').innerHTML = `
        <div class="empty-state">
          <span class="empty-state-icon">⚠️</span>
          <h3>Erro ao carregar projetos</h3>
          <p>${escHtml(err.message)}</p>
        </div>
      `;
    }
  },

  _renderStats(projects) {
    const owned  = projects.filter(p => p.user_permission === 'owner').length;
    const shared = projects.filter(p => p.user_permission !== 'owner').length;
    const total  = projects.reduce((s, p) => s + (p.requirement_count || 0), 0);

    document.getElementById('dash-stats').innerHTML = `
      <div class="stat-chip">
        <span class="stat-chip-label">Total</span>
        <span class="stat-chip-value text-orange">${projects.length}</span>
      </div>
      <div class="stat-chip">
        <span class="stat-chip-label">Próprios</span>
        <span class="stat-chip-value">${owned}</span>
      </div>
      <div class="stat-chip">
        <span class="stat-chip-label">Compartilhados</span>
        <span class="stat-chip-value">${shared}</span>
      </div>
      <div class="stat-chip">
        <span class="stat-chip-label">Requisitos</span>
        <span class="stat-chip-value">${total}</span>
      </div>
    `;
  },

  _renderProjects(projects) {
    const container = document.getElementById('projects-container');
    if (!projects.length) {
      container.innerHTML = `
        <div class="empty-state">
          <span class="empty-state-icon">📂</span>
          <h3>Nenhum projeto ainda</h3>
          <p>Clique em <strong>+ Novo Projeto</strong> para criar o primeiro.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="projects-grid">
        ${projects.map(p => this._projectCard(p)).join('')}
      </div>
    `;

    els('.project-card').forEach(card => {
      card.addEventListener('click', () => {
        router.go(`/project/${card.dataset.id}`);
      });
    });
  },

  _projectCard(p) {
    return `
      <div class="project-card" data-id="${p.id}" role="button" tabindex="0">
        <div class="flex items-center justify-between">
          ${permBadge(p.user_permission)}
          <span class="text-xs text-muted font-mono">#${p.id}</span>
        </div>
        <div class="project-card-name">${escHtml(p.name)}</div>
        ${p.description
          ? `<div class="project-card-desc">${escHtml(p.description)}</div>`
          : ''}
        <div class="project-card-meta">
          <span class="project-card-count">${p.requirement_count} requisito${p.requirement_count !== 1 ? 's' : ''}</span>
          <span class="text-xs text-muted">${timeAgo(p.updated_at)}</span>
        </div>
      </div>
    `;
  },

  _bindSearch() {
    const input = document.getElementById('project-search');
    if (!input) return;
    input.addEventListener('input', debounce(() => {
      const q = input.value.toLowerCase();
      const filtered = q
        ? this._projects.filter(p =>
            p.name.toLowerCase().includes(q) ||
            (p.description || '').toLowerCase().includes(q))
        : this._projects;
      this._renderProjects(filtered);
    }, 200));
  },

  _bindNav() {
    // keyboard accessibility for cards
    document.addEventListener('keydown', e => {
      if (e.key === 'Enter' && e.target.classList.contains('project-card')) {
        router.go(`/project/${e.target.dataset.id}`);
      }
    });
  },

  _openCreateModal() {
    modal.open(
      'Novo Projeto',
      `<form id="create-form" novalidate>
        <div class="form-group">
          <label class="form-label" for="cp-name">Nome *</label>
          <input id="cp-name" type="text" class="form-input"
                 placeholder="Ex: Sistema de Cadastro" maxlength="100" />
          <span class="form-error hidden" id="cp-err-name"></span>
        </div>
        <div class="form-group">
          <label class="form-label" for="cp-desc">Descrição</label>
          <textarea id="cp-desc" class="form-input"
                    placeholder="Descreva o objetivo do projeto…"></textarea>
        </div>
      </form>`,
      `<button class="btn btn-secondary" onclick="modal.close()">Cancelar</button>
       <button class="btn btn-primary" id="btn-create-proj">Criar Projeto</button>`
    );

    setTimeout(() => {
      document.getElementById('btn-create-proj')?.addEventListener('click', () => {
        this._submitCreate();
      });
      document.getElementById('create-form')?.addEventListener('submit', e => {
        e.preventDefault(); this._submitCreate();
      });
      document.getElementById('cp-name')?.focus();
    }, 0);
  },

  async _submitCreate() {
    const name = document.getElementById('cp-name')?.value.trim();
    const desc = document.getElementById('cp-desc')?.value.trim();
    const errEl = document.getElementById('cp-err-name');

    if (!name) {
      if (errEl) { errEl.textContent = 'Nome é obrigatório'; errEl.classList.remove('hidden'); }
      return;
    }
    if (errEl) errEl.classList.add('hidden');

    const btn = document.getElementById('btn-create-proj');
    if (btn) { btn.disabled = true; btn.textContent = 'Criando…'; }

    try {
      const proj = await api.post('/api/projects', { name, description: desc || null });
      modal.close();
      toast.success(`Projeto "${proj.name}" criado!`);
      await this._loadProjects();
    } catch (err) {
      toast.error(err.message);
      if (btn) { btn.disabled = false; btn.textContent = 'Criar Projeto'; }
    }
  },
};
