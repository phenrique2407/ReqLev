/**
 * ReqLev – Client-Side Router
 *
 * Simple hash-based router (#/path).
 * Guards all authenticated routes – redirects to /login when needed.
 */

const router = (() => {
  // Track current view for cleanup
  let _currentView = null;

  const routes = [
    {
      pattern: /^\/login$/,
      render:  () => loginView.render(),
      public:  true,
    },
    {
      pattern: /^\/register$/,
      render:  () => registerView.render(),
      public:  true,
    },
    {
      pattern: /^\/dashboard$/,
      render:  () => dashboardView.render(),
      public:  false,
    },
    {
      pattern: /^\/project\/(\d+)$/,
      render:  (m) => projectView.render(m[1]),
      public:  false,
      view:    () => projectView,
    },
  ];

  async function navigate() {
    const hash = location.hash.replace(/^#/, '') || '/';

    // Unmount previous view if applicable
    if (_currentView && typeof _currentView.unmount === 'function') {
      _currentView.unmount();
    }
    _currentView = null;

    // Match route
    for (const route of routes) {
      const m = hash.match(route.pattern);
      if (!m) continue;

      // Auth guard
      if (!route.public && !auth.isLoggedIn()) {
        location.hash = '#/login';
        return;
      }
      // Already logged in → skip auth pages
      if (route.public && auth.isLoggedIn() && hash !== '/') {
        location.hash = '#/dashboard';
        return;
      }

      _currentView = route.view ? route.view() : null;
      await route.render(m);
      return;
    }

    // Default redirect
    if (auth.isLoggedIn()) {
      location.hash = '#/dashboard';
    } else {
      location.hash = '#/login';
    }
  }

  function go(path) {
    location.hash = `#${path}`;
  }

  // Bootstrap
  window.addEventListener('hashchange', navigate);
  window.addEventListener('load', navigate);

  // Also handle bare '/' → redirect
  if (!location.hash) {
    location.hash = auth.isLoggedIn() ? '#/dashboard' : '#/login';
  }

  return { go, navigate };
})();
