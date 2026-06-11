/**
 * ReqLev – Project View
 *
 * Displays a single project with:
 *   - Requirements list with filter + CRUD (inline editing)
 *   - Collaborators panel + share form
 *   - Activity log
 *   - SSE live-updates for all changes
 *   - PDF export
 */

const projectView = {
  _pid:          null,   // project id (int)
  _project:      null,   // project object
  _requirements: [],
  _activities:   [],
  _permissions:  [],
  _filter:       'all',  // all | todo | in_progress | done
  _currentUser:  null,
  _sseHandlers:  [],     // {event, fn} pairs – cleaned up on unmount
  _editingState: {},     // req_id → [username, ...]

  // ── Entry point ────────────────────────────────────────────────────────

  async render(pid) {
    this._pid         = parseInt(pid, 10);
    this._currentUser = auth.getUser();
    this._filter      = 'all';
    this._editingState = {};

    // Disconnect any previous SSE connection
    sseClient.disconnect();

    // Shell with loading state
    mount(`
      <div class="app-shell">
        ${this._sidebar()}
        <div class="main-area" id="main-area">
          <header class="topbar" id="topbar">
            <div>
              <div class="breadcrumb">
                <a href="#/dashboard">Projetos</a>
                <span class="breadcrumb-sep"><i class="ph-bold ph-caret-right"></i></span>
                <span id="bc-name">Carregando…</span>
              </div>
              <div class="topbar-title" id="topbar-title">…</div>
            </div>
            <div class="topbar-actions" id="topbar-actions">
              <div class="sse-indicator">
                <div class="sse-dot connecting"></div>
                <span>conectando…</span>
              </div>
            </div>
          </header>
          <div class="page-content" id="page-content">
            <div class="empty-state"><span class="empty-state-icon"><i class="ph-bold ph-hourglass-medium"></i></span><h3>Carregando…</h3></div>
          </div>
        </div>
      </div>
    `);

    await this._loadAll();
    this._renderFull();
    this._bindSSE();
  },

  // ── Data loading ───────────────────────────────────────────────────────

  async _loadAll() {
    try {
      const [project, requirements, activities, permissions] = await Promise.all([
        api.get(`/api/projects/${this._pid}`),
        api.get(`/api/projects/${this._pid}/requirements`),
        api.get(`/api/projects/${this._pid}/activities`),
        api.get(`/api/projects/${this._pid}/permissions`),
      ]);
      this._project      = project;
      this._requirements = requirements;
      this._activities   = activities;
      this._permissions  = permissions;
    } catch (err) {
      document.getElementById('page-content').innerHTML = `
        <div class="empty-state">
          <span class="empty-state-icon"><i class="ph-bold ph-warning"></i></span>
          <h3>Erro ao carregar projeto</h3>
          <p>${escHtml(err.message)}</p>
          <a href="#/dashboard" class="btn btn-secondary mt-3">← Voltar</a>
        </div>`;
    }
  },

  // ── Main render ────────────────────────────────────────────────────────

  _renderFull() {
    if (!this._project) return;

    const p    = this._project;
    const perm = p.user_permission;
    const canEdit = perm === 'owner' || perm === 'edit';

    // Update breadcrumb + topbar
    const bcName = document.getElementById('bc-name');
    if (bcName) bcName.textContent = p.name;
    const topbarTitle = document.getElementById('topbar-title');
    if (topbarTitle) topbarTitle.textContent = p.name;

    // Topbar actions
    document.getElementById('topbar-actions').innerHTML = `
      <div class="sse-indicator">
        <div class="sse-dot connecting"></div>
        <span>conectando…</span>
      </div>
      <button class="btn btn-secondary btn-sm" id="btn-export-pdf" title="Exportar PDF">
        <i class="ph-bold ph-file-pdf"></i> PDF
      </button>
      ${canEdit ? `<button class="btn btn-secondary btn-sm" id="btn-edit-proj"><i class="ph-bold ph-pencil-simple"></i> Editar</button>` : ''}
      ${perm === 'owner' ? `<button class="btn btn-danger btn-sm" id="btn-del-proj"><i class="ph-bold ph-trash"></i> Deletar</button>` : ''}
    `;

    document.getElementById('btn-export-pdf')?.addEventListener('click', () => this._exportPdf());
    document.getElementById('btn-edit-proj')?.addEventListener('click', () => this._openEditProject());
    document.getElementById('btn-del-proj')?.addEventListener('click', () => this._deleteProject());

    // Page body
    document.getElementById('page-content').innerHTML = `
      <div class="project-layout">
        <!-- Left column: requirements -->
        <div>
          ${this._statsBar()}
          <div class="section-header">
            <h2 class="section-title">Requisitos</h2>
            ${canEdit
              ? `<button class="btn btn-primary btn-sm" id="btn-new-req">+ Adicionar</button>`
              : ''}
          </div>
          ${this._filterBar()}
          <div id="req-list">${this._reqListHTML()}</div>
        </div>

        <!-- Right column: info panels -->
        <div style="display:flex;flex-direction:column;gap:16px">
          ${this._projectInfoPanel()}
          ${this._collabPanel()}
          ${this._activityPanel()}
        </div>
      </div>
    `;

    // Bind requirement actions
    document.getElementById('btn-new-req')?.addEventListener('click', () => this._openCreateReq());
    this._bindFilterButtons();
    this._bindReqCardActions();
  },

  // ── Stats bar ──────────────────────────────────────────────────────────

  _statsBar() {
    const reqs = this._requirements;
    const total = reqs.length;
    const todo  = reqs.filter(r => r.status === 'todo').length;
    const ip    = reqs.filter(r => r.status === 'in_progress').length;
    const done  = reqs.filter(r => r.status === 'done').length;
    return `
      <div class="stats-bar mb-3">
        <div class="stat-chip">
          <span class="stat-chip-label">Total</span>
          <span class="stat-chip-value text-orange">${total}</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip-label">A fazer</span>
          <span class="stat-chip-value">${todo}</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip-label">Em andamento</span>
          <span class="stat-chip-value">${ip}</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip-label">Concluídos</span>
          <span class="stat-chip-value" style="color:var(--success)">${done}</span>
        </div>
      </div>
    `;
  },

  // ── Filter bar ─────────────────────────────────────────────────────────

  _filterBar() {
    const filters = [
      { key: 'all',         label: 'Todos' },
      { key: 'todo',        label: 'A fazer' },
      { key: 'in_progress', label: 'Em andamento' },
      { key: 'done',        label: 'Concluídos' },
    ];
    return `
      <div class="filter-bar" id="filter-bar">
        ${filters.map(f => `
          <button class="filter-btn${this._filter === f.key ? ' active' : ''}"
                  data-filter="${f.key}">${f.label}</button>
        `).join('')}
      </div>
    `;
  },

  _bindFilterButtons() {
    els('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this._filter = btn.dataset.filter;
        els('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('req-list').innerHTML = this._reqListHTML();
        this._bindReqCardActions();
      });
    });
  },

  // ── Requirements list HTML ─────────────────────────────────────────────

  _reqListHTML() {
    let reqs = this._requirements;
    if (this._filter !== 'all') {
      reqs = reqs.filter(r => r.status === this._filter);
    }
    if (!reqs.length) {
      return `<div class="empty-state" style="padding:32px 0">
        <span class="empty-state-icon"><i class="ph-bold ph-clipboard-text"></i></span>
        <h3>Nenhum requisito${this._filter !== 'all' ? ' neste filtro' : ''}</h3>
        ${this._filter === 'all' && (this._project?.user_permission !== 'view')
          ? '<p>Clique em <strong>+ Adicionar</strong> para criar o primeiro.</p>' : ''}
      </div>`;
    }
    return `<div class="req-list">${reqs.map(r => this._reqCardHTML(r)).join('')}</div>`;
  },

  _reqCardHTML(r) {
    const canEdit = this._project?.user_permission !== 'view';
    const editors = this._editingState[r.id] || [];
    const others  = editors.filter(u => u !== this._currentUser?.username);
    const isEditing = !!others.length;

    return `
      <div class="req-card${isEditing ? ' editing-by-other' : ''}" id="req-card-${r.id}" data-id="${r.id}">
        <div class="req-card-header">
          <div class="req-card-name">${escHtml(r.name)}</div>
          ${canEdit ? `
            <div class="req-card-actions">
              <button class="btn btn-ghost btn-icon btn-sm btn-edit-req" data-id="${r.id}" title="Editar"><i class="ph-bold ph-pencil-simple"></i></button>
              <button class="btn btn-ghost btn-icon btn-sm btn-del-req" data-id="${r.id}" title="Deletar"><i class="ph-bold ph-trash"></i></button>
            </div>` : ''}
        </div>
        <div class="req-badges">
          ${typeBadge(r.type)}
          ${statusBadge(r.status)}
        </div>
        ${r.description ? `<div class="req-card-desc">${escHtml(r.description)}</div>` : ''}
        ${isEditing ? `
          <div class="req-editing-indicator">
            <span class="editing-dot"></span>
            ${escHtml(others.join(', '))} está editando…
          </div>` : ''}
        <div id="req-edit-form-${r.id}"></div>
      </div>
    `;
  },

  _bindReqCardActions() {
    els('.btn-edit-req').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        this._openInlineEdit(parseInt(btn.dataset.id));
      });
    });
    els('.btn-del-req').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        this._deleteReq(parseInt(btn.dataset.id));
      });
    });
  },

  // ── Inline edit form ───────────────────────────────────────────────────

  _openInlineEdit(reqId) {
    // Close any other open form first
    els('.inline-edit-form').forEach(f => {
      const rid = f.closest('.req-card')?.dataset.id;
      if (rid) sseClient.signalStopEditing(this._pid, parseInt(rid));
      f.remove();
    });

    const req = this._requirements.find(r => r.id === reqId);
    if (!req) return;

    const formContainer = document.getElementById(`req-edit-form-${reqId}`);
    if (!formContainer) return;

    formContainer.innerHTML = `
      <div class="inline-edit-form" id="ief-${reqId}">
        <div class="form-group">
          <label class="form-label">Nome *</label>
          <input id="ie-name-${reqId}" type="text" class="form-input"
                 value="${escHtml(req.name)}" maxlength="200" />
        </div>
        <div class="form-group">
          <label class="form-label">Descrição</label>
          <textarea id="ie-desc-${reqId}" class="form-input" rows="2">${escHtml(req.description || '')}</textarea>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="form-group">
            <label class="form-label">Tipo</label>
            <select id="ie-type-${reqId}" class="form-input">
              <option value="RF"  ${req.type === 'RF'  ? 'selected' : ''}>RF – Funcional</option>
              <option value="RNF" ${req.type === 'RNF' ? 'selected' : ''}>RNF – Não Funcional</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Andamento</label>
            <select id="ie-status-${reqId}" class="form-input">
              <option value="todo"        ${req.status === 'todo'        ? 'selected' : ''}>A fazer</option>
              <option value="in_progress" ${req.status === 'in_progress' ? 'selected' : ''}>Em andamento</option>
              <option value="done"        ${req.status === 'done'        ? 'selected' : ''}>Concluído</option>
            </select>
          </div>
        </div>
        <div class="inline-edit-actions">
          <button class="btn btn-ghost btn-sm" id="ie-cancel-${reqId}">Cancelar</button>
          <button class="btn btn-primary btn-sm" id="ie-save-${reqId}">Salvar</button>
        </div>
      </div>
    `;

    document.getElementById(`ie-cancel-${reqId}`)?.addEventListener('click', () => {
      formContainer.innerHTML = '';
      sseClient.signalStopEditing(this._pid, reqId);
    });
    document.getElementById(`ie-save-${reqId}`)?.addEventListener('click', () => {
      this._submitInlineEdit(reqId);
    });

    // Signal editing
    sseClient.signalEditing(this._pid, reqId);
    document.getElementById(`ie-name-${reqId}`)?.focus();
  },

  async _submitInlineEdit(reqId) {
    const name   = document.getElementById(`ie-name-${reqId}`)?.value.trim();
    const desc   = document.getElementById(`ie-desc-${reqId}`)?.value.trim();
    const type   = document.getElementById(`ie-type-${reqId}`)?.value;
    const status = document.getElementById(`ie-status-${reqId}`)?.value;

    if (!name) { toast.error('Nome é obrigatório'); return; }

    const btn = document.getElementById(`ie-save-${reqId}`);
    if (btn) { btn.disabled = true; btn.textContent = 'Salvando…'; }

    try {
      await api.put(`/api/projects/${this._pid}/requirements/${reqId}`,
        { name, description: desc || null, type, status });
      sseClient.signalStopEditing(this._pid, reqId);
      // SSE will update the card; close form optimistically
      const fc = document.getElementById(`req-edit-form-${reqId}`);
      if (fc) fc.innerHTML = '';
      toast.success('Requisito atualizado');
    } catch (err) {
      toast.error(err.message);
      if (btn) { btn.disabled = false; btn.textContent = 'Salvar'; }
    }
  },

  // ── Create Requirement modal ───────────────────────────────────────────

  _openCreateReq() {
    modal.open(
      'Novo Requisito',
      `<form id="cr-form" novalidate>
        <div class="form-group">
          <label class="form-label">Nome *</label>
          <input id="cr-name" type="text" class="form-input"
                 placeholder="Ex: Autenticação de usuário" maxlength="200" />
          <span class="form-error hidden" id="cr-err"></span>
        </div>
        <div class="form-group">
          <label class="form-label">Descrição</label>
          <textarea id="cr-desc" class="form-input" rows="3"
                    placeholder="Detalhe o requisito…"></textarea>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="form-group">
            <label class="form-label">Tipo</label>
            <select id="cr-type" class="form-input">
              <option value="RF">RF – Funcional</option>
              <option value="RNF">RNF – Não Funcional</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Andamento</label>
            <select id="cr-status" class="form-input">
              <option value="todo">A fazer</option>
              <option value="in_progress">Em andamento</option>
              <option value="done">Concluído</option>
            </select>
          </div>
        </div>
      </form>`,
      `<button class="btn btn-secondary" onclick="modal.close()">Cancelar</button>
       <button class="btn btn-primary" id="btn-cr-submit">Criar Requisito</button>`
    );

    setTimeout(() => {
      document.getElementById('btn-cr-submit')
        ?.addEventListener('click', () => this._submitCreateReq());
      document.getElementById('cr-form')
        ?.addEventListener('submit', e => { e.preventDefault(); this._submitCreateReq(); });
      document.getElementById('cr-name')?.focus();
    }, 0);
  },

  async _submitCreateReq() {
    const name   = document.getElementById('cr-name')?.value.trim();
    const desc   = document.getElementById('cr-desc')?.value.trim();
    const type   = document.getElementById('cr-type')?.value;
    const status = document.getElementById('cr-status')?.value;
    const errEl  = document.getElementById('cr-err');

    if (!name) {
      if (errEl) { errEl.textContent = 'Nome é obrigatório'; errEl.classList.remove('hidden'); }
      return;
    }
    if (errEl) errEl.classList.add('hidden');

    const btn = document.getElementById('btn-cr-submit');
    if (btn) { btn.disabled = true; btn.textContent = 'Criando…'; }

    try {
      await api.post(`/api/projects/${this._pid}/requirements`,
        { name, description: desc || null, type, status });
      modal.close();
      toast.success('Requisito criado!');
    } catch (err) {
      toast.error(err.message);
      if (btn) { btn.disabled = false; btn.textContent = 'Criar Requisito'; }
    }
  },

  // ── Delete Requirement ─────────────────────────────────────────────────

  _deleteReq(reqId) {
    const req = this._requirements.find(r => r.id === reqId);
    modal.confirm(
      'Deletar Requisito',
      `Tem certeza que deseja deletar <strong>${escHtml(req?.name || 'este requisito')}</strong>? Esta ação não pode ser desfeita.`,
      async () => {
        try {
          await api.delete(`/api/projects/${this._pid}/requirements/${reqId}`);
          toast.success('Requisito deletado');
        } catch (err) { toast.error(err.message); }
      },
      true
    );
  },

  // ── Edit Project modal ─────────────────────────────────────────────────

  _openEditProject() {
    const p = this._project;
    modal.open(
      'Editar Projeto',
      `<form id="ep-form" novalidate>
        <div class="form-group">
          <label class="form-label">Nome *</label>
          <input id="ep-name" type="text" class="form-input"
                 value="${escHtml(p.name)}" maxlength="100" />
          <span class="form-error hidden" id="ep-err"></span>
        </div>
        <div class="form-group">
          <label class="form-label">Descrição</label>
          <textarea id="ep-desc" class="form-input" rows="3">${escHtml(p.description || '')}</textarea>
        </div>
      </form>`,
      `<button class="btn btn-secondary" onclick="modal.close()">Cancelar</button>
       <button class="btn btn-primary" id="btn-ep-submit">Salvar</button>`
    );

    setTimeout(() => {
      document.getElementById('btn-ep-submit')
        ?.addEventListener('click', () => this._submitEditProject());
      document.getElementById('ep-name')?.focus();
    }, 0);
  },

  async _submitEditProject() {
    const name  = document.getElementById('ep-name')?.value.trim();
    const desc  = document.getElementById('ep-desc')?.value.trim();
    const errEl = document.getElementById('ep-err');

    if (!name) {
      if (errEl) { errEl.textContent = 'Nome é obrigatório'; errEl.classList.remove('hidden'); }
      return;
    }
    if (errEl) errEl.classList.add('hidden');

    const btn = document.getElementById('btn-ep-submit');
    if (btn) { btn.disabled = true; btn.textContent = 'Salvando…'; }

    try {
      await api.put(`/api/projects/${this._pid}`, { name, description: desc || null });
      modal.close();
      toast.success('Projeto atualizado!');
    } catch (err) {
      toast.error(err.message);
      if (btn) { btn.disabled = false; btn.textContent = 'Salvar'; }
    }
  },

  // ── Delete Project ─────────────────────────────────────────────────────

  _deleteProject() {
    modal.confirm(
      'Deletar Projeto',
      `Tem certeza que deseja deletar <strong>${escHtml(this._project?.name)}</strong>?
       Todos os requisitos e histórico serão removidos permanentemente.`,
      async () => {
        try {
          await api.delete(`/api/projects/${this._pid}`);
          toast.success('Projeto deletado');
          router.go('/dashboard');
        } catch (err) { toast.error(err.message); }
      },
      true
    );
  },

  // ── PDF export ─────────────────────────────────────────────────────────

  async _exportPdf() {
    const btn = document.getElementById('btn-export-pdf');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Gerando…'; }
    try {
      const blob = await api.download(`/api/projects/${this._pid}/export/pdf`);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `ReqLev_${(this._project?.name || 'projeto').replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('PDF gerado e download iniciado!');
    } catch (err) {
      toast.error(`Erro ao gerar PDF: ${err.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '⬇ PDF'; }
    }
  },

  // ── Right-column panels ────────────────────────────────────────────────

  _projectInfoPanel() {
    const p = this._project;
    return `
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">Sobre o Projeto</span>
          ${permBadge(p.user_permission)}
        </div>
        <div class="panel-body" style="font-size:.85rem;display:flex;flex-direction:column;gap:8px">
          ${p.description
            ? `<p style="color:var(--text-sub);line-height:1.6">${escHtml(p.description)}</p><div class="divider" style="margin:4px 0"></div>`
            : ''}
          <div class="flex justify-between">
            <span class="text-muted">Dono</span>
            <span style="font-weight:600">${escHtml(p.owner?.username)}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted">Criado em</span>
            <span>${formatDate(p.created_at)}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted">Atualizado</span>
            <span>${timeAgo(p.updated_at)}</span>
          </div>
        </div>
      </div>
    `;
  },

  _collabPanel() {
    const p       = this._project;
    const isOwner = p.user_permission === 'owner';
    const perms   = this._permissions;

    const ownerItem = `
      <div class="collab-item">
        <div class="collab-avatar">${avatar(p.owner?.username)}</div>
        <div class="collab-info">
          <div class="collab-name">${escHtml(p.owner?.username)}</div>
          <div class="collab-role">${escHtml(p.owner?.email)}</div>
        </div>
        ${permBadge('owner')}
      </div>`;

    const sharedItems = perms.map(perm => `
      <div class="collab-item" id="collab-${perm.user_id}">
        <div class="collab-avatar">${avatar(perm.user?.username)}</div>
        <div class="collab-info">
          <div class="collab-name">${escHtml(perm.user?.username)}</div>
          <div class="collab-role text-muted text-xs">${escHtml(perm.user?.email)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;flex-shrink:0">
          ${permBadge(perm.permission)}
          ${isOwner ? `
            <button class="btn btn-ghost btn-icon btn-sm btn-change-perm"
                    data-uid="${perm.user_id}" data-perm="${perm.permission}"
                    title="Alterar permissão"><i class="ph-bold ph-gear"></i></button>
            <button class="btn btn-ghost btn-icon btn-sm btn-revoke"
                    data-uid="${perm.user_id}" data-uname="${escHtml(perm.user?.username)}"
                    title="Revogar acesso"><i class="ph-bold ph-x"></i></button>
          ` : ''}
        </div>
      </div>`).join('');

    return `
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">Colaboradores</span>
          ${isOwner ? `<button class="btn btn-primary btn-sm" id="btn-share">+ Compartilhar</button>` : ''}
        </div>
        <div class="panel-body">
          <div class="collab-list" id="collab-list">
            ${ownerItem}
            ${sharedItems}
          </div>
          ${!perms.length && !isOwner
            ? `<p class="text-xs text-muted mt-2">Nenhum colaborador adicional.</p>` : ''}
        </div>
      </div>
    `;
  },

  _activityPanel() {
    const acts = this._activities.slice(0, 20);
    return `
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">Atividades Recentes</span>
          ${this._activities.length > 20
            ? `<span class="text-xs text-muted">${this._activities.length} total</span>` : ''}
        </div>
        <div class="panel-body" id="activity-panel-body">
          ${acts.length
            ? `<div class="activity-list">${acts.map(a => this._activityItem(a)).join('')}</div>`
            : `<p class="text-xs text-muted">Nenhuma atividade ainda.</p>`}
        </div>
      </div>
    `;
  },

  _activityItem(a) {
    return `
      <div class="activity-item">
        <div class="activity-dot"></div>
        <div>
          <div class="activity-text">
            <strong>${escHtml(a.user?.username || 'Sistema')}</strong>
            ${escHtml(a.action)}
            ${a.object_name ? `em <strong>${escHtml(a.object_name)}</strong>` : ''}
            ${a.details ? `<span class="text-muted text-xs"> (${escHtml(a.details)})</span>` : ''}
          </div>
          <div class="activity-time">${timeAgo(a.created_at)}</div>
        </div>
      </div>
    `;
  },

  // ── Sharing UI ─────────────────────────────────────────────────────────

  _bindShareButton() {
    document.getElementById('btn-share')?.addEventListener('click', () => this._openShareModal());
  },

  _openShareModal() {
    modal.open(
      'Compartilhar Projeto',
      `<div class="form-group">
        <label class="form-label">Buscar usuário</label>
        <div class="search-wrap">
          <span class="search-icon"><i class="ph-bold ph-magnifying-glass"></i></span>
          <input id="share-search" type="text" class="form-input"
                 placeholder="Email ou username…" autocomplete="off" />
        </div>
        <div id="share-results"></div>
      </div>
      <div id="share-selected" style="display:none" class="mt-2">
        <div class="flex items-center gap-2 mb-2">
          <div class="collab-avatar" id="share-sel-avatar">?</div>
          <div>
            <div class="collab-name" id="share-sel-name"></div>
            <div class="text-xs text-muted" id="share-sel-email"></div>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Permissão</label>
          <select id="share-perm" class="form-input">
            <option value="view">Apenas Ver</option>
            <option value="edit">Editar</option>
          </select>
        </div>
      </div>`,
      `<button class="btn btn-secondary" onclick="modal.close()">Cancelar</button>
       <button class="btn btn-primary hidden" id="btn-share-confirm">Compartilhar</button>`
    );

    setTimeout(() => {
      let selectedUserId = null;

      const searchInput = document.getElementById('share-search');
      const resultsDiv  = document.getElementById('share-results');
      const selectedDiv = document.getElementById('share-selected');
      const confirmBtn  = document.getElementById('btn-share-confirm');

      // Pre-populate already-shared user ids to exclude
      const alreadyShared = new Set(this._permissions.map(p => p.user_id));
      alreadyShared.add(this._project.owner_id);

      const doSearch = debounce(async (q) => {
        if (!q.trim()) { resultsDiv.innerHTML = ''; return; }
        try {
          const users = await api.get('/api/users/search', { q });
          const filtered = users.filter(u => !alreadyShared.has(u.id));
          if (!filtered.length) {
            resultsDiv.innerHTML = `<div class="user-result-item"><span class="text-muted text-sm">Nenhum usuário encontrado.</span></div>`;
            return;
          }
          resultsDiv.innerHTML = `
            <div class="user-search-results">
              ${filtered.map(u => `
                <div class="user-result-item" data-uid="${u.id}"
                     data-name="${escHtml(u.username)}" data-email="${escHtml(u.email)}">
                  <div class="collab-avatar" style="font-size:11px">${avatar(u.username)}</div>
                  <div>
                    <div class="user-result-name">${escHtml(u.username)}</div>
                    <div class="user-result-email">${escHtml(u.email)}</div>
                  </div>
                </div>
              `).join('')}
            </div>`;

          els('.user-result-item', resultsDiv).forEach(item => {
            item.addEventListener('click', () => {
              selectedUserId = parseInt(item.dataset.uid);
              document.getElementById('share-sel-avatar').textContent = item.dataset.name[0].toUpperCase();
              document.getElementById('share-sel-name').textContent  = item.dataset.name;
              document.getElementById('share-sel-email').textContent = item.dataset.email;
              selectedDiv.style.display = 'block';
              confirmBtn.classList.remove('hidden');
              resultsDiv.innerHTML = '';
              searchInput.value    = '';
            });
          });
        } catch (_) {}
      }, 250);

      searchInput?.addEventListener('input', e => doSearch(e.target.value));

      confirmBtn?.addEventListener('click', async () => {
        if (!selectedUserId) return;
        const perm = document.getElementById('share-perm')?.value;
        confirmBtn.disabled    = true;
        confirmBtn.textContent = 'Compartilhando…';
        try {
          await api.post(`/api/projects/${this._pid}/permissions`,
            { user_id: selectedUserId, permission: perm });
          modal.close();
          toast.success('Projeto compartilhado!');
          // SSE will update the collab list
        } catch (err) {
          toast.error(err.message);
          confirmBtn.disabled    = false;
          confirmBtn.textContent = 'Compartilhar';
        }
      });
    }, 0);
  },

  _bindCollabActions() {
    els('.btn-change-perm').forEach(btn => {
      btn.addEventListener('click', () => {
        const uid  = parseInt(btn.dataset.uid);
        const curr = btn.dataset.perm;
        const next = curr === 'view' ? 'edit' : 'view';
        const label = next === 'edit' ? 'Editar' : 'Apenas Ver';
        modal.confirm(
          'Alterar Permissão',
          `Alterar permissão para <strong>${label}</strong>?`,
          async () => {
            try {
              await api.put(`/api/projects/${this._pid}/permissions/${uid}`, { permission: next });
              toast.success('Permissão atualizada');
            } catch (err) { toast.error(err.message); }
          }
        );
      });
    });

    els('.btn-revoke').forEach(btn => {
      btn.addEventListener('click', () => {
        const uid   = parseInt(btn.dataset.uid);
        const uname = btn.dataset.uname;
        modal.confirm(
          'Revogar Acesso',
          `Remover acesso de <strong>${escHtml(uname)}</strong>?`,
          async () => {
            try {
              await api.delete(`/api/projects/${this._pid}/permissions/${uid}`);
              toast.success('Acesso removido');
            } catch (err) { toast.error(err.message); }
          },
          true
        );
      });
    });
  },

  // ── SSE event wiring ───────────────────────────────────────────────────

  _bindSSE() {
    sseClient.connect(this._pid);

    const on = (event, fn) => {
      document.addEventListener(event, fn);
      this._sseHandlers.push({ event, fn });
    };

    on('rl:connected',           () => {});

    on('rl:requirement_created', e => this._onReqCreated(e.detail));
    on('rl:requirement_updated', e => this._onReqUpdated(e.detail));
    on('rl:requirement_deleted', e => this._onReqDeleted(e.detail));
    on('rl:project_updated',     e => this._onProjectUpdated(e.detail));
    on('rl:project_deleted',     ()  => this._onProjectDeleted());
    on('rl:permission_added',    e => this._onPermAdded(e.detail));
    on('rl:permission_removed',  e => this._onPermRemoved(e.detail));
    on('rl:editing_start',       e => this._onEditingStart(e.detail));
    on('rl:editing_stop',        e => this._onEditingStop(e.detail));
  },

  _cleanupSSE() {
    this._sseHandlers.forEach(({ event, fn }) =>
      document.removeEventListener(event, fn));
    this._sseHandlers = [];
  },

  // ── SSE handlers ───────────────────────────────────────────────────────

  _onReqCreated(req) {
    // Check if we already have it (avoid duplicates)
    if (this._requirements.some(r => r.id === req.id)) return;
    this._requirements.push(req);
    this._refreshReqList();
    this._refreshStats();

    setTimeout(() => flashEl(document.getElementById(`req-card-${req.id}`)), 50);

    // Refresh activity log
    this._refreshActivities();
  },

  _onReqUpdated(req) {
    const idx = this._requirements.findIndex(r => r.id === req.id);
    if (idx === -1) {
      this._requirements.push(req);
    } else {
      this._requirements[idx] = req;
    }
    this._refreshReqList();
    this._refreshStats();
    this._refreshActivities();

    setTimeout(() => flashEl(document.getElementById(`req-card-${req.id}`)), 50);
  },

  _onReqDeleted({ id }) {
    this._requirements = this._requirements.filter(r => r.id !== id);
    this._refreshReqList();
    this._refreshStats();
    this._refreshActivities();
  },

  _onProjectUpdated(proj) {
    this._project = { ...this._project, ...proj };
    const bc = document.getElementById('bc-name');
    if (bc) bc.textContent = this._project.name;
    const tt = document.getElementById('topbar-title');
    if (tt) tt.textContent = this._project.name;
    // Refresh info panel
    const infoPanel = document.querySelector('.panel:first-child');
    if (infoPanel) infoPanel.outerHTML = this._projectInfoPanel();
    this._refreshActivities();
  },

  _onProjectDeleted() {
    toast.warning('Este projeto foi deletado pelo proprietário.');
    setTimeout(() => router.go('/dashboard'), 2000);
  },

  async _onPermAdded(data) {
    // Re-fetch permissions to get full user info
    try {
      this._permissions = await api.get(`/api/projects/${this._pid}/permissions`);
      this._refreshCollabPanel();
    } catch (_) {}
    this._refreshActivities();
  },

  async _onPermRemoved({ user_id }) {
    this._permissions = this._permissions.filter(p => p.user_id !== user_id);
    this._refreshCollabPanel();
    this._refreshActivities();

    // If this user lost access
    if (user_id === this._currentUser?.id) {
      toast.warning('Seu acesso a este projeto foi revogado.');
      setTimeout(() => router.go('/dashboard'), 2000);
    }
  },

  _onEditingStart({ requirement_id, username }) {
    if (username === this._currentUser?.username) return;
    if (!this._editingState[requirement_id]) this._editingState[requirement_id] = [];
    if (!this._editingState[requirement_id].includes(username)) {
      this._editingState[requirement_id].push(username);
    }
    this._updateEditingIndicator(requirement_id);
  },

  _onEditingStop({ requirement_id, user_id }) {
    const cu = this._currentUser;
    // Remove by matching user_id is hard without a map; refresh the indicator
    if (this._editingState[requirement_id]) {
      delete this._editingState[requirement_id];
    }
    this._updateEditingIndicator(requirement_id);
  },

  _updateEditingIndicator(reqId) {
    const card = document.getElementById(`req-card-${reqId}`);
    if (!card) return;
    const editors = this._editingState[reqId] || [];
    const others  = editors.filter(u => u !== this._currentUser?.username);
    card.classList.toggle('editing-by-other', !!others.length);
    // Update or remove indicator
    let ind = card.querySelector('.req-editing-indicator');
    if (others.length) {
      if (!ind) {
        ind = document.createElement('div');
        ind.className = 'req-editing-indicator';
        card.appendChild(ind);
      }
      ind.innerHTML = `<span class="editing-dot"></span>${escHtml(others.join(', '))} está editando…`;
    } else if (ind) {
      ind.remove();
    }
  },

  // ── Partial re-renders (avoid full page rebuild) ───────────────────────

  _refreshReqList() {
    const listEl = document.getElementById('req-list');
    if (listEl) {
      listEl.innerHTML = this._reqListHTML();
      this._bindReqCardActions();
    }
  },

  _refreshStats() {
    const sb = document.querySelector('.stats-bar');
    if (sb) sb.outerHTML = this._statsBar();
  },

  async _refreshActivities() {
    try {
      this._activities = await api.get(`/api/projects/${this._pid}/activities`);
      const body = document.getElementById('activity-panel-body');
      if (body) {
        const acts = this._activities.slice(0, 20);
        body.innerHTML = acts.length
          ? `<div class="activity-list">${acts.map(a => this._activityItem(a)).join('')}</div>`
          : `<p class="text-xs text-muted">Nenhuma atividade ainda.</p>`;
      }
    } catch (_) {}
  },

  _refreshCollabPanel() {
    // Find existing panel and re-render
    const panels = els('.panel');
    // Collab panel is 2nd (index 1), but check for btn-share or collab-list
    const collabPanel = els('.panel').find(p => p.querySelector('#collab-list, #btn-share'));
    if (collabPanel) {
      const newHTML = this._collabPanel();
      const temp    = document.createElement('div');
      temp.innerHTML = newHTML;
      collabPanel.replaceWith(temp.firstElementChild);
    }
    // Re-bind actions
    this._bindCollabActions();
    this._bindShareButton();
  },

  // ── Sidebar (same as dashboard) ────────────────────────────────────────

  _sidebar() {
    const user = this._currentUser;
    return `
      <aside class="sidebar">
        <div class="sidebar-logo">
          <a href="#/dashboard">ReqLev<span class="logo-dot"></span></a>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-section-label">Menu</div>
          <button class="btn btn-ghost w-full"
                  style="justify-content:flex-start;gap:10px"
                  onclick="router.go('/dashboard')">
            ← Voltar aos Projetos
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
          <button class="btn btn-ghost w-full"
                  style="justify-content:flex-start"
                  onclick="projectView._handleLogout()">
            ← Sair
          </button>
        </div>
      </aside>
    `;
  },

  _handleLogout() {
    modal.confirm('Sair da conta', 'Tem certeza que deseja sair?', () => {
      sseClient.disconnect();
      auth.logout();
      router.go('/login');
    });
  },

  // Called by router when leaving this view
  unmount() {
    this._cleanupSSE();
    sseClient.disconnect();
  },
};

// After DOM renders the right column, bind share + collab actions
document.addEventListener('DOMContentLoaded', () => {
  // Re-bind after every render cycle that touches project view panels
  const observer = new MutationObserver(() => {
    if (document.getElementById('btn-share')) {
      projectView._bindShareButton();
    }
    if (document.querySelector('.btn-change-perm, .btn-revoke')) {
      projectView._bindCollabActions();
    }
  });
  observer.observe(document.getElementById('app') || document.body, {
    childList: true, subtree: true,
  });
});
