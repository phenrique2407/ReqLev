/**
 * ReqLev – Register View
 */

const registerView = {
  render() {
    mount(`
      <div class="auth-root">
        <div class="auth-brand">
          <div class="auth-brand-logo">ReqLev</div>
          <p class="auth-brand-tag">
            Crie sua conta e comece a gerenciar projetos
            com sua equipe em tempo real.
          </p>
        </div>
        <div class="auth-panel">
          <div class="auth-card">
            <h1 class="auth-title">Criar conta</h1>
            <p class="auth-subtitle">Preencha os dados para se registrar</p>

            <form id="reg-form" novalidate>
              <div class="form-group">
                <label class="form-label" for="reg-username">Nome de usuário</label>
                <input id="reg-username" type="text" class="form-input"
                       placeholder="meu_usuario" autocomplete="username" required />
                <span class="form-error hidden" id="err-username"></span>
              </div>

              <div class="form-group">
                <label class="form-label" for="reg-email">Email</label>
                <input id="reg-email" type="email" class="form-input"
                       placeholder="seu@email.com" autocomplete="email" required />
                <span class="form-error hidden" id="err-email"></span>
              </div>

              <div class="form-group">
                <label class="form-label" for="reg-pass">Senha</label>
                <input id="reg-pass" type="password" class="form-input"
                       placeholder="mínimo 6 caracteres" autocomplete="new-password" required />
                <span class="form-error hidden" id="err-pass"></span>
              </div>

              <div id="reg-general-wrap" style="display:none" class="mb-2">
                <span class="form-error" id="err-general"></span>
              </div>

              <button type="submit" class="btn btn-primary btn-full btn-lg mt-3" id="reg-btn">
                Criar conta
              </button>
            </form>

            <p class="auth-link-row">
              Já tem conta? <a href="#/login">Entrar</a>
            </p>
          </div>
        </div>
      </div>
    `);

    this._bindEvents();
  },

  _bindEvents() {
    const form    = document.getElementById('reg-form');
    const btn     = document.getElementById('reg-btn');
    const errWrap = document.getElementById('reg-general-wrap');
    const errEl   = document.getElementById('err-general');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = document.getElementById('reg-username').value.trim();
      const email    = document.getElementById('reg-email').value.trim();
      const password = document.getElementById('reg-pass').value;

      let valid = true;
      if (!username) { this._setErr('err-username', 'Usuário é obrigatório'); valid = false; }
      else { this._clearErr('err-username'); }

      if (!email) { this._setErr('err-email', 'Email é obrigatório'); valid = false; }
      else { this._clearErr('err-email'); }

      if (!password || password.length < 6) {
        this._setErr('err-pass', 'Senha deve ter ao menos 6 caracteres'); valid = false;
      } else { this._clearErr('err-pass'); }

      if (!valid) return;

      btn.disabled    = true;
      btn.textContent = 'Criando conta…';
      errWrap.style.display = 'none';

      try {
        await auth.register(username, email, password);
        toast.success('Conta criada com sucesso!');
        router.go('/dashboard');
      } catch (err) {
        errEl.textContent     = err.message;
        errWrap.style.display = 'block';
      } finally {
        btn.disabled    = false;
        btn.textContent = 'Criar conta';
      }
    });
  },

  _setErr(id, msg) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('hidden');
  },
  _clearErr(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = '';
    el.classList.add('hidden');
  },
};
