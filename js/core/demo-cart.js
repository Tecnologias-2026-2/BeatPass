// FLUJO: event-detail.js -> demo-cart.js -> localStorage -> cart.js / header.js.
/** Carrito local para eventos de demostración: nunca envía datos al backend ni aparta cupos. */
(function (global) {
  'use strict';
  const app = global.BeatPass = global.BeatPass || {};
  const KEY = 'beatpass_demo_cart';
  const MAX = 10;

  function valid(value) {
    return Array.isArray(value) ? value.filter(item => item && item.demo && item.id && item.zone_name) : [];
  }

  function items() {
    const stored = app.storage ? app.storage.readJson(KEY, []) : null;
    return valid(stored);
  }

  function persist(rows) {
    const clean = valid(rows);
    if (app.storage) app.storage.write(KEY, JSON.stringify(clean));
    global.dispatchEvent(new Event('beatpass:demo-cart-updated'));
    global.dispatchEvent(new Event('beatpass:cart-updated'));
    return clean;
  }

  function add(event, zoneIndex, quantity) {
    const zone = (event.ticketTypes || [])[Number(zoneIndex)];
    if (!zone) throw new Error('Selecciona una zona válida.');
    const count = Math.max(1, Math.min(MAX, Number(quantity) || 1));
    const id = `${event.id}:${zoneIndex}`;
    const rows = items();
    const found = rows.find(row => row.id === id);
    if (found) {
      found.quantity = Math.min(MAX, Number(found.quantity) + count);
    } else {
      rows.push({
        id, demo: true, event_id: event.id, event_title: event.title,
        category: event.category || '', date: event.date || '', time: event.time || '',
        venue: event.venue || '', city: event.city || '', image_url: event.image || '',
        zone_index: Number(zoneIndex), zone_name: zone.name,
        unit_price: Number(zone.price) || 0, quantity: count,
        available: MAX, status: 'active'
      });
    }
    persist(rows);
    return rows.find(row => row.id === id);
  }

  function find(id) {
    return items().find(row => row.id === String(id));
  }

  function update(id, quantity) {
    const rows = items();
    const row = rows.find(item => item.id === String(id));
    if (!row) return null;
    const count = Math.max(1, Math.min(MAX, Number(quantity) || 1));
    row.quantity = count;
    persist(rows);
    return row;
  }

  function remove(id) {
    persist(items().filter(row => row.id !== String(id)));
  }

  function clear() {
    persist([]);
  }

  function count() {
    return items().reduce((total, row) => total + (Number(row.quantity) || 0), 0);
  }

  function subtotal() {
    return items().reduce((total, row) => total + row.quantity * row.unit_price, 0);
  }

  app.demoCart = Object.freeze({ KEY, MAX, items, add, find, update, remove, clear, count, subtotal });
})(window);
