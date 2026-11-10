// FLUJO: dashboard.html comprueba roles mediante api.me(); backend/main.py decide acceso real.
/** Protege el renderizado del panel hasta verificar sesión y rol EN EL SERVIDOR. */
(function (global) {
  'use strict';
  async function init() {
    const app = global.BeatPass;
    const view = document.querySelector('main.bp-admin');
    const placeholder = document.getElementById('admin-access');
    if (!view || !placeholder) return;
    function message(text, showLogin = false) {
      const target = placeholder.querySelector('[data-access-message]');
      if (target) target.textContent = text;
      const link = placeholder.querySelector('[data-access-login]');
      if (link) link.hidden = !showLogin;
    }
    try {
      const user = await app.api.me();
      if (!user.roles.includes('organizador') && !user.roles.includes('administracion')) {
        message(user.organizer_status === 'pending'
          ? 'Tu solicitud de organizador sigue pendiente de aprobación. Podrás crear eventos cuando sea aprobada.'
          : 'Tu cuenta no tiene permiso para acceder al panel de organización.', true);
        return;
      }
      const reviewsLink = document.getElementById('admin-review-link');
      if (reviewsLink) reviewsLink.hidden = !user.roles.includes('administracion');
      placeholder.hidden = true;
      view.hidden = false;
      // Evitamos inicializar el editor antes de confirmar el rol.
      const script = document.createElement('script');
      script.src = '../../js/pages/admin-events.js';
      script.onerror = () => message('No se pudo cargar el editor de eventos.');
      document.body.append(script);
    } catch (error) {
      if (error.status === 401) app.session?.clear();
      message(error.message || 'No se pudo comprobar tu sesión.', true);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})(window);
