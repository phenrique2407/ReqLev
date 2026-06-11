/**
 * ReqLev – Login View
 */

const loginView = {
  render() {
    mount(`
      <div class="auth-root">
        <div class="auth-brand">
          <img src="./assets/Logo.png" alt="ReqLev Logo" class="auth-brand-logo-img" />
          <p class="auth-brand-tag">
            Gerencie projetos e requisitos com colaboração
            em tempo real e rastreamento completo de atividades.
          </p>
        </div>
        <div class="auth-panel">
          <div class="auth-card">
            <h1 class="auth-title">Bem-vindo de volta</h1>
            <p class="auth-subtitle">Entre na sua conta para continuar</p>

            <form id="login-form" novalidate>
              <div class="form-group">
                <label class="form-label" for="login-email">Email</label>
                <input id="login-email" type="email" class="form-input"
                       placeholder="seu@email.com" autocomplete="email" required />
                <span class="form-error hidden" id="err-email"></span>
              </div>

              <div class="form-group">
                <label class="form-label" for="login-pass">Senha</label>
                <input id="login-pass" type="password" class="form-input"
                       placeholder="••••••••" autocomplete="current-password" required />
                <span class="form-error hidden" id="err-pass"></span>
              </div>

              <div class="form-group" id="login-general-err" style="display:none">
                <span class="form-error" id="err-general"></span>
              </div>

              <button type="submit" class="btn btn-primary btn-full btn-lg mt-3" id="login-btn">
                Entrar
              </button>
            </form>

            <p class="auth-link-row">
              Não tem conta?
              <a href="#/register">Criar conta</a>
            </p>
          </div>
        </div>
      </div>
    `);

    this._bindEvents();
  },

  _bindEvents() {
    const form   = document.getElementById('login-form');
    const btn    = document.getElementById('login-btn');
    const errEl  = document.getElementById('err-general');
    const errWrap = document.getElementById('login-general-err');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email    = document.getElementById('login-email').value.trim();
      const password = document.getElementById('login-pass').value;

      // Basic client-side validation
      let valid = true;
      if (!email) {
        this._setErr('err-email', 'Email é obrigatório');
        valid = false;
      } else {
        this._clearErr('err-email');
      }
      if (!password) {
        this._setErr('err-pass', 'Senha é obrigatória');
        valid = false;
      } else {
        this._clearErr('err-pass');
      }
      if (!valid) return;

      btn.disabled   = true;
      btn.textContent = 'Entrando…';
      errWrap.style.display = 'none';

      try {
        await auth.login(email, password);
        router.go('/dashboard');
      } catch (err) {
        errEl.textContent     = err.message;
        errWrap.style.display = 'block';
      } finally {
        btn.disabled    = false;
        btn.textContent = 'Entrar';
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
