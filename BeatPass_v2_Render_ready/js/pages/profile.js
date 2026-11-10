// FLUJO: profile.html -> api.js -> backend/profile.py; session.js actualiza el saludo.
/** Mi perfil: pages/profile.html -> js/core/api.js -> backend/profile.py -> SQLite.
 * Nunca confíes en un id de usuario enviado por la página: FastAPI valida el JWT.
 */
(function (global) {
  'use strict';
  const app = global.BeatPass;
  const $ = id => document.getElementById(id);
  const status = (id, text, state='info') => {
    const el = $(id); if (!el) return;
    el.textContent = text; el.dataset.state = state;
  };
  let loaded = false;
  function show(user) {
    loaded = true;
    $('profile-private').hidden = false;
    $('profile-guest').hidden = true;
    $('profile-owner').textContent = user.fullname;
    $('profile-avatar').textContent = user.fullname.trim().split(/\s+/).slice(0,2).map(s => s[0]?.toUpperCase() || '').join('');
    $('profile-email-display').textContent = user.email;
    $('profile-email').value = user.email;
    $('profile-name').value = user.fullname;
    $('profile-roles').textContent = (user.roles || []).join(' · ');
    $('profile-verification').textContent = user.email_verified ? 'Correo verificado' : 'Correo sin verificar';
    const orgPanel = $('profile-organization-panel');
    const org = user.organization;
    orgPanel.hidden = !org;
    if (org) {
      const labels = {pending:'Pendiente',approved:'Aprobado',rejected:'Rechazado'};
      $('profile-organization-info').textContent = `${org.name} · ${org.city} · ${labels[org.status] || org.status}`;
      $('profile-organizer-link').hidden = org.status !== 'approved';
    }
    status('profile-status', 'Datos obtenidos de tu cuenta en BeatPass.', 'success');
  }
  async function init() {
    if (!app.session?.token() || !app.session.currentUser()) {
      $('profile-guest').hidden = false;
      status('profile-status', 'No has iniciado sesión.'); return;
    }
    try {
      // No usamos los datos en caché para pintar el perfil: consultamos FastAPI.
      show(await app.api.profile());
    } catch (error) {
      if (error.status === 401) {app.session.clear();$('profile-guest').hidden = false;}
      status('profile-status', error.message || 'No fue posible cargar el perfil.', 'error');
    }
  }
  $('profile-name-form').addEventListener('submit', async event => {
    event.preventDefault(); if (!loaded || !event.target.reportValidity()) return;
    const button = $('profile-name-submit'); button.disabled = true;
    status('profile-name-message', 'Guardando nombre...');
    try {
      const {user, message} = await app.api.updateProfile($('profile-name').value.trim());
      // Sincronizamos el saludo del header con los datos confirmados por el backend.
      app.session.save(app.session.token(), user);
      show(await app.api.profile());
      status('profile-name-message', message, 'success');
    } catch (error) {status('profile-name-message', error.message || 'No se pudo guardar.', 'error');}
    finally {button.disabled = false;}
  });
  $('profile-password-form').addEventListener('submit', async event => {
    event.preventDefault(); if (!loaded || !event.target.reportValidity()) return;
    const current = $('profile-current-password').value;
    const next = $('profile-new-password').value;
    if (next !== $('profile-confirm-password').value) {
      status('profile-password-message', 'Las contraseñas nuevas no coinciden.', 'error');return;
    }
    const button = $('profile-password-submit'); button.disabled = true;
    status('profile-password-message', 'Actualizando contraseña...');
    try {
      const result = await app.api.changePassword(current, next);
      // FastAPI incrementa token_version; se elimina la credencial anterior.
      event.target.reset();app.session.clear();loaded = false;
      $('profile-private').hidden = true;$('profile-guest').hidden = false;
      status('profile-status', result.message, 'success');
    } catch (error) {status('profile-password-message', error.message || 'No se pudo cambiar la contraseña.', 'error');}
    finally {button.disabled = false;}
  });
  init();
})(window);
