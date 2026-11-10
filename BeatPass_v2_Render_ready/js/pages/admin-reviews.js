// FLUJO: reviews.html -> api.js -> backend/main.py aprueba o rechaza organizadores.
/** La revisión solicita y confirma permisos siempre en FastAPI. */
(function (global) {
  'use strict';
  const api = global.BeatPass.api;
  const status = document.getElementById('review-status');
  const list = document.getElementById('review-applications');
  const element = (tag, text, className = '') => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  };
  async function load() {
    status.textContent = 'Comprobando permisos y solicitudes...';
    list.replaceChildren();
    try {
      const me = await api.me();
      if (!me.roles.includes('administracion')) {
        status.textContent = 'Acceso restringido: se requiere rol de administración.'; return;
      }
      const applications = await api.pendingApplications();
      status.textContent = applications.length ? `${applications.length} solicitud(es) pendientes.` : 'No hay solicitudes pendientes.';
      applications.forEach(item => {
        const card = element('article', undefined, 'bp-review-card');
        card.append(element('h2', item.organization));
        card.append(element('p', `${item.fullname} · ${item.email} · ${item.city}`));
        card.append(element('p', item.description));
        const label = element('label', 'Motivo (obligatorio para rechazar)');
        const reason = element('textarea', undefined, 'bp-input');
        reason.maxLength = 500;
        label.append(reason);
        const actions = element('div', undefined, 'bp-review-actions');
        const approve = element('button', 'Aprobar organizador', 'bp-button bp-button--primary');
        const reject = element('button', 'Rechazar solicitud', 'bp-review-reject');
        approve.type = reject.type = 'button';
        async function send(action) {
          if (action === 'reject' && !reason.value.trim()) { status.textContent = 'Escribe un motivo para rechazar.'; reason.focus(); return; }
          approve.disabled = reject.disabled = true;
          try { await api.reviewApplication(item.id, action, reason.value.trim()); await load(); }
          catch (error) {status.textContent = error.message;approve.disabled = reject.disabled = false;}
        }
        approve.addEventListener('click', () => send('approve'));
        reject.addEventListener('click', () => send('reject'));
        actions.append(approve, reject);
        card.append(label, actions);
        list.append(card);
      });
    } catch (error) { status.textContent = error.message || 'No se pudo cargar la revisión.'; }
  }
  load();
})(window);
