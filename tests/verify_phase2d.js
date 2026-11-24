// FLUJO: prueba rápida de integración frontend sin servidor ni credenciales.
const fs=require('node:fs');const assert=require('node:assert/strict');
const api=fs.readFileSync('js/core/api.js','utf8');
const cart=fs.readFileSync('js/pages/cart.js','utf8');
const ticketScript=fs.readFileSync('js/pages/tickets.js','utf8');
const page=fs.readFileSync('pages/tickets.html','utf8');
for(const name of ['checkoutHold','confirmDemoOrder','cancelOrder','myOrders','myTickets'])
  assert.match(api,new RegExp(name+'\\s*:'));
assert.match(api,/async\s+ticketQr\s*\(/);
assert.match(cart,/Reservar 15 minutos/);
assert.match(cart,/confirm-demo/);
assert.match(cart,/global\.location\.href='tickets\.html'/);
assert.match(ticketScript,/no válid|NO VÁLID/i);
assert.match(page,/js\/pages\/tickets\.js/);
assert.doesNotMatch(page,/<script[^>]+src="[^"]*pending\.js"/);
assert.match(page,/id="tickets-grid"/);
console.log('OK: carrito, reserva, confirmación demo y boletos conectados al frontend.');
