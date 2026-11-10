// FLUJO: Las páginas llaman api.*; request() lleva JSON y JWT hacia rutas backend/*.py.
/** Peticiones HTTP centralizadas; ninguna página necesita conocer fetch o URLs de Render. */
(function (global) {
  'use strict';
  const app = global.BeatPass = global.BeatPass || {};
  async function request(path, options = {}) {
    const base = app.config?.apiBaseUrl;
    if (!base) throw new Error('La API de BeatPass no está configurada.');
    const headers = { 'Content-Type': 'application/json' };
    if (options.auth !== false) {
      const token = app.session?.token();
      if (token) headers.Authorization = `Bearer ${token}`;
    }
    let response;
    try {
      response = await fetch(`${base}${path}`, {
        method: options.method || 'GET', headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        cache: 'no-store'
      });
    } catch (_error) {
      throw new Error('No se pudo conectar a BeatPass. Vuelve a intentarlo más tarde.');
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail;
      const message = typeof detail === 'string' ? detail :
        (Array.isArray(detail) ? 'Revisa la información introducida.' : 'La operación no pudo completarse.');
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return payload;
  }
  const api = {
    register: data => request('/auth/register', { method: 'POST', body: data, auth: false }),
    login: data => request('/auth/login', { method: 'POST', body: data, auth: false }),
    verifyEmail: token => request('/auth/verify-email', {method:'POST', body:{token}, auth:false}),
    resendVerification: email => request('/auth/resend-verification', {method:'POST', body:{email}, auth:false}),
    forgotPassword: email => request('/auth/forgot-password', {method:'POST', body:{email}, auth:false}),
    resetPassword: (token,password) => request('/auth/reset-password', {method:'POST', body:{token,password}, auth:false}),
    acceptAdminInvitation: (token,email,password) => request('/auth/accept-admin-invitation', {method:'POST', body:{token,email,password}, auth:false}),
    adminInvitations: () => request('/admin/invitations'),
    inviteAdmin: email => request('/admin/invitations', {method:'POST',body:{email}}),
    revokeAdminInvitation: id => request(`/admin/invitations/${encodeURIComponent(id)}/revoke`, {method:'POST'}),
    eventAvailability: id => request(`/events/${encodeURIComponent(id)}/availability`, {auth:false}),
    cart: () => request('/cart'),
    addToCart: (event_id,zone_index,quantity=1) => request('/cart/items', {method:'POST',body:{event_id,zone_index,quantity}}),
    updateCartItem: (itemId,quantity) => request(`/cart/items/${encodeURIComponent(itemId)}`, {method:'PATCH',body:{quantity}}),
    removeCartItem: itemId => request(`/cart/items/${encodeURIComponent(itemId)}`, {method:'DELETE'}),
    clearCart: () => request('/cart', {method:'DELETE'}),
    // FLUJO: carrito -> reserva temporal -> pedido -> boletos individuales.
    checkoutConfig: () => request('/checkout/config', {auth:false}),
    checkoutHold: () => request('/checkout/hold', {method:'POST'}),
    startSandboxPayment: id => request(`/orders/${encodeURIComponent(id)}/checkout-test`, {method:'POST'}),
    myOrders: () => request('/orders'),
    myOrder: id => request(`/orders/${encodeURIComponent(id)}`),
    cancelOrder: id => request(`/orders/${encodeURIComponent(id)}/cancel`, {method:'POST'}),
    confirmDemoOrder: id => request(`/orders/${encodeURIComponent(id)}/confirm-demo`, {method:'POST'}),
    myTickets: () => request('/tickets'),
    async ticketQr(id) {
      const token=app.session?.token();
      if (!token) throw new Error('Inicia sesión para consultar tu QR.');
      const response=await fetch(`${app.config.apiBaseUrl}/tickets/${encodeURIComponent(id)}/qr`,
        {headers:{Authorization:`Bearer ${token}`},cache:'no-store'});
      if (!response.ok) throw new Error('No fue posible cargar este QR.');
      return response.blob();
    },
    publicEvents: (params={}) => {
      const query=new URLSearchParams();
      for(const field of ['q','category','limit','offset']) {
        if(params[field] !== undefined && params[field] !== '') query.set(field,String(params[field]));
      }
      return request('/events' + (query.size ? `?${query}` : ''), {auth:false});
    },
    publicEvent: id => request(`/events/${encodeURIComponent(id)}`, {auth:false}),
    myEvents: () => request('/organizers/events'),
    myEvent: id => request(`/organizers/events/${encodeURIComponent(id)}`),
    createEvent: data => request('/organizers/events', {method:'POST', body:data}),
    updateEvent: (id,data) => request(`/organizers/events/${encodeURIComponent(id)}`, {method:'PUT', body:data}),
    submitEvent: id => request(`/organizers/events/${encodeURIComponent(id)}/submit`, {method:'POST', body:{}}),
    pendingEventReviews: () => request('/admin/events/reviews'),
    async eventRevisionCover(id) {
      const base=app.config?.apiBaseUrl,token=app.session?.token();
      if(!base || !token)throw new Error('Se requiere sesión de administración.');
      const response=await fetch(`${base}/admin/events/reviews/${encodeURIComponent(id)}/cover`,
        {headers:{Authorization:`Bearer ${token}`},cache:'no-store'});
      if(!response.ok)throw new Error('No se pudo cargar la portada para revisión.');
      return response.blob();
    },
    reviewEvent: (id,action,reason='') => request(`/admin/events/reviews/${encodeURIComponent(id)}/${action}`, {method:'POST', body:{reason}}),
    assetUrl: path => /^\/api\/events\/\d+\/cover(?:\?v=\d+)?$/.test(path||'')
      ? app.config.apiBaseUrl.replace(/\/api$/, '') + path : null,
    async eventCover(id) {
      const base = app.config?.apiBaseUrl;
      const token = app.session?.token();
      if (!base || !token) throw new Error('Debes iniciar sesión para descargar la portada.');
      const response = await fetch(`${base}/organizers/events/${encodeURIComponent(id)}/cover`,
        {headers:{Authorization:`Bearer ${token}`}, cache:'no-store'});
      if (!response.ok) throw new Error('No se pudo recuperar la portada del servidor.');
      return response.blob();
    },
    async uploadEventCover(id,blob) {
      const base=app.config?.apiBaseUrl, token=app.session?.token();
      if (!base || !token) throw new Error('Debes iniciar sesión para guardar la portada.');
      let response;
      try {response=await fetch(`${base}/organizers/events/${encodeURIComponent(id)}/cover`, {
        method:'POST', headers:{'Authorization':`Bearer ${token}`,'Content-Type':'image/jpeg'},
        body:blob, cache:'no-store'});}
      catch(_error){throw new Error('No se pudo enviar la portada. Comprueba la conexión.');}
      const content=await response.json().catch(()=>({}));
      if (!response.ok) throw new Error(content.detail||'La portada no se pudo guardar.');
      return content;
    },
    async removeEventCover(id) {
      const base=app.config?.apiBaseUrl, token=app.session?.token();
      if (!base || !token) throw new Error('Necesitas una sesión activa.');
      const response=await fetch(`${base}/organizers/events/${encodeURIComponent(id)}/cover`,
        {method:'DELETE',headers:{Authorization:`Bearer ${token}`}});
      if (!response.ok) {const json=await response.json().catch(()=>({}));throw new Error(json.detail||'No se pudo quitar la portada.');}
    },
    // Mi perfil: js/pages/profile.js -> backend/profile.py; el JWT va en request().
    profile: () => request('/profile'),
    updateProfile: fullname => request('/profile', {method:'PATCH', body:{fullname}}),
    changePassword: (current_password,new_password) => request('/profile/change-password',
      {method:'POST',body:{current_password,new_password}}),
    me: () => request('/auth/me'),
    organizerStatus: () => request('/organizers/me'),
    pendingApplications: () => request('/admin/applications'),
    reviewApplication: (id, action, reason = '') => request(`/admin/applications/${encodeURIComponent(id)}/${action}`,
      { method: 'POST', body: { reason } })
  };
  app.api = Object.freeze(api);
})(window);
