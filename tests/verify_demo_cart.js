/** Prueba aislada del carrito demo: sin backend, sin DOM y sin red. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const store = new Map();
const events = [];
const win = {
  localStorage: {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key)
  },
  Event: class { constructor(type) { this.type = type; } },
  dispatchEvent: event => events.push(event.type),
  addEventListener: () => {}
};
win.BeatPass = {
  storage: {
    readJson: (key, fallback) => {
      const raw = win.localStorage.getItem(key);
      if (raw === null) return fallback;
      try { return JSON.parse(raw); } catch (_) { return fallback; }
    },
    write: (key, value) => win.localStorage.setItem(key, value)
  }
};
win.window = win;
vm.createContext(win);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'js/core/demo-cart.js'), 'utf8'), win);

const cart = win.BeatPass.demoCart;
const event = {
  id: 'rock-clasico', title: 'Noche de Rock', category: 'Musica',
  date: '15 jun 2027', time: '19:00', venue: 'Estadio', city: 'Bogota', image: '../rock.webp',
  ticketTypes: [{ name: 'General', price: 120 }, { name: 'VIP', price: 260 }]
};

cart.clear();
cart.add(event, 0, 2);
cart.add(event, 1, 1);
cart.add(event, 0, 3);
assert.strictEqual(cart.items().length, 2);
assert.strictEqual(cart.count(), 6);
assert.strictEqual(cart.subtotal(), 860);
assert.strictEqual(cart.find('rock-clasico:0').quantity, 5);

cart.update('rock-clasico:0', 3);
assert.strictEqual(cart.count(), 4);
assert.strictEqual(cart.subtotal(), 620);

cart.remove('rock-clasico:1');
assert.strictEqual(cart.count(), 3);
assert.strictEqual(cart.subtotal(), 360);
assert.ok(events.includes('beatpass:cart-updated'));

cart.add(event, 0, 99);
assert.strictEqual(cart.find('rock-clasico:0').quantity, 10, 'el máximo es 10');

cart.clear();
assert.strictEqual(cart.count(), 0);
assert.strictEqual(cart.items().length, 0);
console.log('OK: carrito demo agrega, fusiona, actualiza, elimina y respeta el máximo.');
