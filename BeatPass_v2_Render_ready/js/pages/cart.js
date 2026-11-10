// FLUJO: cart.html -> api.js -> backend/cart.py -> inventory_models.py.
/** Carrito conectado con la API de inventario y reservas. */
(function (global) {
  'use strict';
  const app = global.BeatPass;
  const $ = id => document.getElementById(id);
  const money = n => Number(n).toLocaleString('es-CO');
  function node(tag, className, text) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }
  function control(label, action, id, disabled = false) {
    const button = node('button', 'qty-btn', label);
    button.type = 'button'; button.dataset.action = action; button.dataset.item = String(id);
    button.disabled = disabled; button.setAttribute('aria-label', `${label === '+' ? 'Aumentar' : label === '−' ? 'Disminuir' : 'Eliminar'} entrada`);
    return button;
  }
  function imageFor(row) {
    return app.api.assetUrl(row.image_url) || '../assets/visuals/concierto.svg';
  }
  function itemCard(item) {
    const card = node('article', 'cart-item'); card.setAttribute('role', 'listitem');
    const picture = node('div', 'cart-item-image');
    const img = node('img'); img.src = imageFor(item); img.alt = `Portada de ${item.event_title}`;
    img.loading = 'lazy'; picture.append(img);
    const content = node('div', 'cart-item-content');
    const header = node('div', 'cart-item-header');
    const info = node('div');
    const title = node('h3', 'cart-item-title', item.event_title);
    const zone = node('p', 'cart-item-category', `${item.category} · Zona ${item.zone_name}`);
    info.append(title, zone);
    const remove = control('×', 'remove', item.id);remove.className = 'cart-item-remove';remove.title = 'Eliminar del carrito';
    header.append(info, remove);
    const details = node('div', 'cart-item-details');
    details.append(node('span', '', `${item.date} · ${item.time}`), node('span', '', `${item.venue}, ${item.city}`));
    const footer = node('div', 'cart-item-footer');
    const prices = node('div');
    prices.append(node('div', 'cart-item-price', `$${money(item.line_total)}`),
                  node('small', '', `$${money(item.unit_price)} por entrada`));
    const quantity = node('div', 'quantity-selector');
    const editable = item.status === 'active';
    quantity.append(control('−', 'decrease', item.id, !editable || item.quantity <= 1),
                    node('span', 'qty-display', String(item.quantity)),
                    control('+', 'increase', item.id, !editable || item.quantity >= Math.min(10, item.available)));
    footer.append(prices, quantity);
    content.append(header, details, footer);
    if (!editable) {
      const reason = {outdated:'El organizador publicó una nueva versión: elimina este artículo y vuelve a seleccionarlo.',
                      closed:'Este evento ya comenzó o finalizó.', unavailable:'Esta cantidad o zona ya no está disponible.'};
      content.append(node('p', 'bp-cart__warning', reason[item.status] || 'Artículo no disponible.'));
    }
    card.append(picture, content); return card;
  }
  function init() {
    if (!$('cart-items-container')) return;
    const empty = $('empty-cart-state'); const filled = $('filled-cart-state');
    const entries = $('cart-items-container'); const summary = filled.querySelector('.cart-summary');
    const note = node('p', 'bp-cart__notice'); note.setAttribute('role', 'status');note.setAttribute('aria-live', 'polite');
    entries.before(note);
    const clear = node('button', 'bp-cart__clear', 'Vaciar carrito');
    clear.type = 'button'; clear.dataset.action = 'clear';
    entries.after(clear);
    const tax = $('tax');if (tax) tax.textContent = 'No disponibles';
    const checkout = $('checkout-btn');
    if (checkout) {
      checkout.disabled = true;
      checkout.textContent = 'Reservar 15 minutos';
      checkout.setAttribute('aria-label','Reservar temporalmente, sin pago real');
    }
    // FLUJO: botón de reserva -> api.checkoutHold() -> backend/orders.py.
    const holdBox = node('section','bp-cart__hold');
    holdBox.setAttribute('aria-live','polite');
    summary.append(holdBox);
    let activeOrder = null;
    let demoEnabled = false;
    let sandboxEnabled = false;
    function showHold() {
      holdBox.replaceChildren();
      if (!activeOrder) return;
      holdBox.append(node('strong','','Reserva temporal #'+activeOrder.id));
      const when = new Date(activeOrder.expires_at);
      holdBox.append(node('p','',`Hasta ${when.toLocaleString('es-CO')}. Confirma antes del vencimiento o libera los cupos.`));
      holdBox.append(node('p','bp-cart__warning','Boletos DEMO: ninguna confirmación de esta etapa autoriza ingreso físico.'));
      const actions = [];
      if(demoEnabled && !activeOrder.payment) actions.push(['Confirmar simulación (sin cobro)','confirm-demo']);
      if(sandboxEnabled) actions.push(['Pagar con Mercado Pago (solo TEST)','checkout-test']);
      actions.push(['Cancelar reserva','cancel-hold']);
      for (const [label,action] of actions) {
        const btn=node('button','bp-cart__hold-button',label);btn.type='button';btn.dataset.action=action;
        holdBox.append(btn);
      }
    }
    async function refreshHold() {
      const [orders,config] = await Promise.all([app.api.myOrders(),app.api.checkoutConfig()]);
      demoEnabled=Boolean(config.demo_enabled);
      sandboxEnabled=Boolean(config.sandbox_enabled);
      activeOrder=orders.find(item => item.status === 'reserved') || null;
      showHold();
      if (checkout) {
        checkout.disabled=!(demoEnabled || sandboxEnabled) || !!activeOrder || !rows.length || rows.some(item=>item.status !== 'active');
        checkout.textContent= !(demoEnabled || sandboxEnabled) ? 'Reservas no habilitadas' : activeOrder ? 'Ya tienes una reserva activa' : 'Reservar cupos 15 minutos';
      }
      entries.querySelectorAll('[data-action]').forEach(button=> {if(activeOrder) button.disabled=true;});
      clear.disabled=Boolean(activeOrder);
      return config;
    }
    let rows = []; let busy = false;
    async function refresh() {
      if (!app.session?.token()) {
        filled.style.display = 'none'; empty.style.display = 'flex';
        const title = empty.querySelector('.empty-cart-title');
        if (title) title.textContent = 'Inicia sesión para ver tu carrito';
        const desc = empty.querySelector('.empty-cart-description');
        if (desc) desc.textContent = 'Para guardar tus entradas necesitas una cuenta BeatPass. Puedes registrarte o iniciar sesión.';
        const link = empty.querySelector('.empty-cart-cta');
        if (link) {link.href = 'login.html';link.querySelector('span').textContent = 'Iniciar sesión';}
        return;
      }
      try {
        const result = await app.api.cart(); rows = result.items;
        empty.style.display = rows.length ? 'none' : 'flex';
        filled.style.display = rows.length ? 'grid' : 'none';
        entries.replaceChildren(...rows.map(itemCard));
        $('subtotal').textContent = money(result.subtotal);
        $('total').textContent = money(result.subtotal);
        note.textContent = result.has_issues
          ? 'Algunas entradas ya no están disponibles o cambiaron de versión. Elimínalas y vuelve a agregarlas. El subtotal no las incluye.'
          : result.notice;
        clear.hidden = rows.length === 0;
        await refreshHold();
        filled.style.display = rows.length || activeOrder ? 'grid' : 'none';
        empty.style.display = rows.length || activeOrder ? 'none' : 'flex';
        global.dispatchEvent(new Event('beatpass:cart-updated'));
      } catch (error) {
        note.textContent = error.message;
        if (error.status === 401) {
          app.session?.clear();await refresh();
        } else {
          empty.style.display = 'none'; filled.style.display = 'grid';
        }
      }
    }
    async function action(event) {
      const button = event.target.closest('[data-action]');
      if (!button || busy || activeOrder) return;
      const action = button.dataset.action;
      const item = rows.find(row => row.id === Number(button.dataset.item));
      if (action !== 'clear' && !item) return;
      busy = true; button.disabled = true; note.textContent = 'Actualizando carrito...';
      try {
        if (action === 'clear') {
          if (!global.confirm('¿Vaciar todos los artículos del carrito?')) return;
          await app.api.clearCart();
        } else if (action === 'remove') await app.api.removeCartItem(item.id);
        else if (action === 'increase') await app.api.updateCartItem(item.id, item.quantity + 1);
        else if (action === 'decrease') await app.api.updateCartItem(item.id, item.quantity - 1);
        await refresh();
      } catch (error) {
        note.textContent = error.message;
        if (error.status === 401) app.session?.clear();
      } finally {busy = false; button.disabled = false;}
    }
    filled.addEventListener('click', event => void action(event));
    if (checkout) checkout.addEventListener('click',async()=> {
      if(busy || !(demoEnabled || sandboxEnabled) || activeOrder) return;
      busy=true;checkout.disabled=true;note.textContent='Reservando cupos...';
      try {
        await app.api.checkoutHold();
        await refresh();
        note.textContent='Reserva creada. Revisa el tiempo límite y confirma la simulación.';
      } catch(error) {note.textContent=error.message;await refresh();}
      finally {busy=false;}
    });
    holdBox.addEventListener('click',async(event)=> {
      const button=event.target.closest('button[data-action]');
      if (!button || busy || !activeOrder) return;
      busy=true;button.disabled=true;
      const orderId=activeOrder.id;
      try {
        if(button.dataset.action==='checkout-test') {
          note.textContent='Conectando con Mercado Pago de pruebas...';
          const response=await app.api.startSandboxPayment(orderId);
          global.location.assign(response.checkout_url); // Solo URL HTTPS validada por payments.py.
        } else if(button.dataset.action==='confirm-demo') {
          if(!global.confirm('Confirmar compra de DEMOSTRACIÓN sin cobro real? Los boletos NO sirven para entrar a eventos.')) return;
          await app.api.confirmDemoOrder(orderId);
          await refresh();
          global.location.href='tickets.html';  // FLUJO: el usuario ve sus boletos tras la confirmación demo.
        } else {
          await app.api.cancelOrder(orderId);
          await refresh();note.textContent='Reserva cancelada y cupos liberados.';
        }
      } catch(error) {note.textContent=error.message;await refresh();}
      finally {busy=false;button.disabled=false;}
    });
    void refresh();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})(window);
