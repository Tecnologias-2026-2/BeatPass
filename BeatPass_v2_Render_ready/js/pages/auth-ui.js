// FLUJO: login/register/recuperación -> api.js -> backend/main.py -> models.py.
/**
 * BeatPass v2 — autenticación conectada a la API FastAPI.
 * Verificación y recuperación usan tokens del backend, nunca credenciales ficticias.
 */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const feedback = (message, state = 'info') => {
    const target = $('form-message');
    if (!target) return;
    target.dataset.state = state;
    target.textContent = message;
  };
  const params = new URLSearchParams(window.location.search);
  const usernameModes = Object.freeze({
    cliente: 'Acceso para quienes exploran eventos y administran sus boletos.',
    organizador: 'Acceso para organizadores aprobados. Sus eventos siguen sujetos a revisión.',
    administracion: 'Acceso exclusivo para el equipo autorizado de BeatPass. Esta opción no concede permisos.'
  });

  // Mejora progresiva: las páginas siguen visibles si este JS no se ejecuta.
  document.querySelectorAll('[data-toggle-password]').forEach(button => {
    const input = $(button.dataset.togglePassword);
    if (!input) return;
    button.addEventListener('click', () => {
      const visible = input.type === 'text';
      input.type = visible ? 'password' : 'text';
      button.textContent = visible ? 'Mostrar' : 'Ocultar';
      button.setAttribute('aria-label', visible ? 'Mostrar contraseña' : 'Ocultar contraseña');
    });
  });

  const login = $('login-form');
  if (login) {
    const selected = Object.hasOwn(usernameModes, params.get('perfil')) ? params.get('perfil') : 'cliente';
    document.querySelectorAll('[data-login-mode]').forEach(link => {
      if (link.dataset.loginMode === selected) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
    const modeDescription = $('login-mode-description');
    if (modeDescription) modeDescription.textContent = usernameModes[selected];
    const adminPreview = $('admin-preview-link');
    if (adminPreview) adminPreview.hidden = !['organizador','administracion'].includes(selected);
    login.addEventListener('submit', async event => {
      event.preventDefault();
      if (!login.reportValidity()) {
        feedback('Completa el correo y la contraseña.'); return;
      }
      const button = $('login-submit');
      button.disabled = true;
      feedback('Verificando tu cuenta...');
      try {
        const result = await window.BeatPass.api.login({
          email: $('email').value.trim(), password: $('password').value, profile: selected
        });
        window.BeatPass.session.save(result.access_token, result.user);
        $('password').value = '';
        feedback('¡Bienvenido! Redirigiendo...', 'success');
        // Solo se permiten destinos de navegación internos.
        const next = params.get('next');
        const safeNext = selected === 'cliente' && /^event-detail\.html\?id=live-\d+$/.test(next || '');
        window.location.href = safeNext ? next : (selected === 'cliente'
          ? window.BeatPass.paths.to('destacados')
          : window.BeatPass.paths.to('adminDashboard'));
      } catch (error) {
        feedback(error.message || 'No se pudo iniciar sesión.', 'error');
      } finally { button.disabled = false; }
    });
  }

  const register = $('register-form');
  if (register) {
    const radio = register.querySelector('input[name="profile"][value="organizador"]');
    if (params.get('perfil') === 'organizador' && radio) radio.checked = true;
    function updateRegisterMode() {
      const organizer = Boolean(radio && radio.checked);
      const extra = $('organizer-fields');
      if (extra) { extra.hidden = !organizer; extra.disabled = !organizer; }
      const note = $('register-role-note');
      if (note) note.textContent = organizer
        ? 'Solicitar una cuenta de organizador exige información adicional y aprobación de BeatPass. No es un alta de administrador general.'
        : 'La cuenta de cliente tendrá acceso estándar cuando la autenticación esté activa.';
      const submit = $('register-submit');
      if (submit) submit.textContent = organizer ? 'Solicitar cuenta de organizador' : 'Crear cuenta de cliente';
      const msg = $('form-message'); if (msg) msg.textContent = '';
    }
    register.querySelectorAll('input[name="profile"]').forEach(el => el.addEventListener('change', updateRegisterMode));
    updateRegisterMode();
    register.addEventListener('submit', async event => {
      event.preventDefault();
      if (!register.reportValidity()) {
        feedback('Completa los campos obligatorios.'); return;
      }
      if ($('password').value !== $('confirm-password').value) {
        feedback('Las contraseñas no coinciden.', 'error');
        $('confirm-password').focus(); return;
      }
      const organizer = Boolean(radio && radio.checked);
      const button = $('register-submit');
      button.disabled = true;
      feedback('Creando cuenta...');
      try {
        const result = await window.BeatPass.api.register({
          fullname: $('fullname').value.trim(), email: $('email').value.trim(),
          password: $('password').value, profile: organizer ? 'organizador' : 'cliente',
          organization: organizer ? $('organization').value.trim() : null,
          phone: organizer ? $('phone').value.trim() : null,
          city: organizer ? $('city').value.trim() : null,
          description: organizer ? $('description').value.trim() : null
        });
        $('password').value = ''; $('confirm-password').value = '';
        feedback(result.message, 'success');
        const link = document.createElement('a');
        link.href = window.BeatPass.paths.to('verifyEmail');
        link.textContent = ' ¿No recibiste el enlace? Solicitar reenvío';
        $('form-message').append(link);
      } catch (error) {
        feedback(error.message || 'No se pudo registrar la cuenta.', 'error');
      } finally { button.disabled = false; }
    });
  }

  const forgot = $('forgot-form');
  if (forgot) {
    forgot.addEventListener('submit', async event => {
      event.preventDefault();
      if (!forgot.reportValidity()) { feedback('Introduce un correo válido.', 'error'); return; }
      const button = forgot.querySelector('button[type="submit"]');
      button.disabled = true;
      feedback('Procesando solicitud...');
      try {
        const response = await window.BeatPass.api.forgotPassword($('email').value.trim());
        forgot.hidden = true;
        const preview = $('recovery-preview');
        if (preview) { preview.hidden = false; preview.querySelector('h2')?.focus?.(); }
        feedback(response.message, 'success');
      } catch (error) { feedback(error.message, 'error'); }
      finally { button.disabled = false; }
    });
  }

  const reset = $('reset-form');
  if (reset) {
    const token = params.get('token');
    if (token && history.replaceState) history.replaceState(null, '', location.pathname);
    if (!token) {
      feedback('Este enlace no incluye un token. Solicita una nueva recuperación.', 'error');
      reset.querySelector('button[type="submit"]').disabled = true;
    }
    reset.addEventListener('submit', async event => {
      event.preventDefault();
      if (!token) return;
      const first = $('password'), second = $('confirm-password');
      if (!reset.reportValidity() || first.value !== second.value) {
        feedback('Escribe al menos 12 caracteres e introduce dos veces la misma contraseña.', 'error');
        return;
      }
      const button = reset.querySelector('button[type="submit"]'); button.disabled = true;
      try {
        const response = await window.BeatPass.api.resetPassword(token, first.value);
        first.value = ''; second.value = '';
        if (window.BeatPass.session) window.BeatPass.session.clear();
        feedback(response.message, 'success');
        const link = document.createElement('a'); link.href = 'login.html'; link.textContent = ' Ir a iniciar sesión';
        $('form-message').append(link);
      } catch (error) { feedback(error.message, 'error'); button.disabled = false; }
    });
  }

  const verifyStatus = $('verify-status');
  if (verifyStatus) {
    const token = params.get('token');
    if (token) {
      verifyStatus.textContent = 'Comprobando enlace...';
      window.BeatPass.api.verifyEmail(token).then(response => {
        verifyStatus.textContent = response.message;
        verifyStatus.dataset.state = 'success';
        // Eliminamos el token del historial del navegador.
        if (history.replaceState) history.replaceState(null,'',location.pathname);
      }).catch(error => { verifyStatus.textContent = error.message; verifyStatus.dataset.state = 'error'; });
    } else verifyStatus.textContent = 'Introduce tu correo para solicitar un nuevo enlace.';
    const resend = $('resend-form');
    resend?.addEventListener('submit', async event => {
      event.preventDefault();
      if (!resend.reportValidity()) return;
      const button = resend.querySelector('button[type="submit"]'); button.disabled = true;
      try { const response = await window.BeatPass.api.resendVerification($('email').value.trim());
        verifyStatus.textContent = response.message; verifyStatus.dataset.state = 'success';
      } catch (error) { verifyStatus.textContent = error.message; verifyStatus.dataset.state = 'error'; }
      finally {button.disabled = false;}
    });
  }

  const invitation = $('accept-invitation-form');
  if (invitation) {
    const token = params.get('token');
    if (token && history.replaceState) history.replaceState(null, '', location.pathname);
    if (!token) {
      feedback('Falta la invitación. Abre el enlace del correo enviado por BeatPass.', 'error');
      invitation.querySelector('button[type="submit"]').disabled = true;
    }
    invitation.addEventListener('submit', async event => {
      event.preventDefault();
      if (!token || !invitation.reportValidity()) return;
      const button = invitation.querySelector('button[type="submit"]'); button.disabled = true;
      try {
        const response = await window.BeatPass.api.acceptAdminInvitation(token, $('email').value.trim(), $('password').value);
        $('password').value = '';
        feedback(response.message, 'success');
        if (history.replaceState) history.replaceState(null,'',location.pathname);
        const link = document.createElement('a'); link.href = 'login.html?perfil=administracion';
        link.textContent = ' Ir a Administración'; $('form-message').append(link);
      } catch (error) { feedback(error.message, 'error'); button.disabled = false; }
    });
  }
})();
