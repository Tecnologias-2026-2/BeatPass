// FLUJO: event-detail.html -> api.js -> backend/events.py y cart.py.
/** Ficha pública: solo eventos aprobados y con capacidad pueden añadirse al carrito. */
(function (global) {
  'use strict';
  const $ = id => document.getElementById(id);
  const money = value => `$${Number(value).toLocaleString('es-CO')}`;
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };

  async function init() {
    const app = global.BeatPass;
    const selected = new URLSearchParams(location.search).get('id');
    const root = $('event-detail-content');
    if (!root) return;
    const real = /^live-\d+$/.test(selected || '');
    let event;
    try {
      event = real ? await app.api.publicEvent(Number(selected.slice(5)))
        : (app.demoEvents || []).find(item => item.id === selected);
      if (!event) throw new Error('Evento no encontrado o no publicado.');
    } catch (error) {
      root.replaceChildren();
      const box = el('article', undefined, 'bp-event-detail__card');
      const link = el('a', 'Volver al catálogo', 'btn btn-primary'); link.href = 'catalog.html';
      box.append(el('h1', 'Evento no disponible'), el('p', error.message), link);
      root.append(box); return;
    }

    const fields = {
      title: event.title, category: event.category, description: event.description,
      date: real ? event.date.split('-').reverse().join('/') : event.date,
      time: `${event.time}${real && event.timezone ? ' · ' + event.timezone : ''}`,
      venue: `${event.venue}${event.city ? ', ' + event.city : ''}${event.address ? ' · ' + event.address : ''}`,
      price: `Desde ${money(event.minPrice)}`
    };
    for (const [key, value] of Object.entries(fields)) {
      const node = $(`event-detail-${key}`);
      if (node) node.textContent = value;
    }
    const image = $('event-detail-image');
    if (image) {
      image.src = real ? (app.api.assetUrl(event.image_url) || '../assets/visuals/concierto.svg') : event.image;
      image.alt = `Portada de ${event.title}`;
    }
    const badge = document.querySelector('.bp-event-detail__badge');
    if (badge) badge.textContent = real ? 'EVENTO APROBADO · PUBLICADO' : 'EVENTO DE DEMOSTRACIÓN';
    const list = $('event-detail-price-list');
    const controls = $('event-detail-cart-controls');
    const select = $('event-detail-zone');
    const quantity = $('event-detail-quantity');
    const buy = $('event-detail-buy');
    const status = $('event-detail-purchase-status');
    const note = $('event-detail-demo-note');
    const description = document.querySelector('.bp-event-detail__prices-heading p');
    if (description) description.textContent = real ? 'Tarifas y cupos aprobados por BeatPass.' : 'Precios ilustrativos de demostración.';
    const prices = document.createDocumentFragment();
    for (const type of event.ticketTypes || []) {
      const row = el('li', undefined, 'bp-event-detail__price-row');
      const info = el('div');
      info.append(el('strong', type.name), el('small', type.description || 'Zona del evento'));
      row.append(info, el('span', money(type.price)));
      prices.append(row);
    }
    if (list) list.replaceChildren(prices);

    if (!real) {
      if (note) note.textContent = 'Este evento es un ejemplo visual. No tiene inventario ni venta disponible.';
      if (buy) buy.disabled = true;
      if (status) status.textContent = 'Las compras se habilitan únicamente para eventos reales aprobados.';
      return;
    }

    let availability;
    try {
      availability = await app.api.eventAvailability(event.id);
    } catch (error) {
      if (buy) buy.disabled = true;
      if (status) status.textContent = `No pudimos consultar la disponibilidad: ${error.message}`;
      return;
    }
    if (note) note.textContent = availability.notice;
    if (list) {
      [...list.children].forEach((row, i) => {
        const zone = availability.zones[i];
        if (zone) row.querySelector('small')?.append(` · ${zone.available} cupos informados`);
      });
    }
    if (controls) controls.hidden = false;
    if (select) {
      select.replaceChildren();
      for (const zone of availability.zones) {
        const option = el('option', `${zone.name} · ${money(zone.price)} · ${zone.available} disponibles`);
        option.value = String(zone.zone_index);
        option.disabled = zone.available === 0;
        select.append(option);
      }
      const first = availability.zones.find(z => z.available > 0);
      if (first) select.value = String(first.zone_index);
    }
    function refreshQuantityLimit() {
      const zone = availability.zones.find(z => z.zone_index === Number(select.value));
      const max = Math.min(10, zone?.available || 0);
      quantity.max = String(max || 1);
      if (Number(quantity.value) > max || Number(quantity.value) < 1) quantity.value = '1';
      if (buy) buy.disabled = !availability.reservable || !max;
    }
    if (select) select.addEventListener('change', refreshQuantityLimit);
    refreshQuantityLimit();
    if (!availability.reservable) {
      if (status) status.textContent = availability.seating === 'Asientos numerados'
        ? 'La selección de asientos numerados llegará en una siguiente fase.'
        : 'El evento ya no admite nuevas entradas.';
      return;
    }
    if (!availability.zones.some(z => z.available > 0)) {
      if (status) status.textContent = 'No quedan cupos configurados. El organizador debe actualizar el inventario.';
      return;
    }
    if (status) status.textContent = 'Selecciona una zona y cantidad. Agregar al carrito no reserva los cupos.';
    buy?.addEventListener('click', async () => {
      if (!app.session?.currentUser()) {
        if (status) status.textContent = 'Inicia sesión como cliente para añadir entradas.';
        // El login solo permite regresar a una ficha de evento validada.
        location.href = `login.html?next=${encodeURIComponent(`event-detail.html?id=live-${event.id}`)}`;
        return;
      }
      const count = Number(quantity.value);
      const zone = availability.zones.find(z => z.zone_index === Number(select.value));
      if (!zone || !Number.isInteger(count) || count < 1 || count > Math.min(10, zone.available)) {
        if (status) status.textContent = 'Selecciona entre 1 y 10 entradas sin superar los cupos disponibles.';
        return;
      }
      buy.disabled = true;
      if (status) status.textContent = 'Añadiendo entradas al carrito...';
      try {
        await app.api.addToCart(event.id, zone.zone_index, count);
        global.dispatchEvent(new Event('beatpass:cart-updated'));
        location.href = 'cart.html';
      } catch (error) {
        if (error.status === 401) app.session?.clear();
        if (status) status.textContent = error.message;
        buy.disabled = false;
      }
    });
    document.title = `${event.title} | BeatPass`;
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => void init());
  else void init();
})(window);
