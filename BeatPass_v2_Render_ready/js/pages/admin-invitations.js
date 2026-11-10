// FLUJO: reviews.html -> api.js -> backend/main.py invita o revoca administradores.
/** Invitaciones por correo: solo el backend otorga permisos. */
(function () {
  'use strict';
  const api = window.BeatPass.api;
  const form = document.getElementById('admin-invite-form');
  const status = document.getElementById('admin-invitation-status');
  const list = document.getElementById('admin-invitation-list');
  if (!form || !list) return;

  async function refresh() {
    list.replaceChildren();
    try {
      const invitations = await api.adminInvitations();
      invitations.forEach(item => {
        const row = document.createElement('article'); row.className = 'bp-review-card';
        const title = document.createElement('p');
        title.textContent = `${item.email} · ${item.status} · Caduca: ${new Date(item.expires_at).toLocaleDateString('es')}`;
        row.append(title);
        if (item.status === 'pending') {
          const revoke = document.createElement('button');
          revoke.type = 'button'; revoke.textContent = 'Revocar invitación';
          revoke.className = 'bp-button bp-button--secondary';
          revoke.addEventListener('click', async () => {
            revoke.disabled = true;
            try { await api.revokeAdminInvitation(item.id); status.textContent = 'Invitación revocada.'; await refresh(); }
            catch (error) { status.textContent = error.message; revoke.disabled = false; }
          });
          row.append(revoke);
        }
        list.append(row);
      });
      if (!invitations.length) list.textContent = 'Aún no hay invitaciones.';
    } catch (error) { status.textContent = error.message; }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const button = form.querySelector('button[type="submit"]'); button.disabled = true;
    status.textContent = 'Enviando invitación...';
    try {
      const result = await api.inviteAdmin(document.getElementById('admin-invite-email').value.trim());
      status.textContent = result.message;
      form.reset();
      await refresh();
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
  refresh();
})();
