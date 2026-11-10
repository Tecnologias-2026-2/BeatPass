// FLUJO: Prueba estática de js/ y componentes; usa Node sin backend.
/** Prueba sin navegador de la identidad visible del header compartido. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');

function element() {
  return { hidden: false, title: '', textContent: '', dataset: {}, attrs: {}, listeners: {},
    addEventListener(name, callback) { this.listeners[name] = callback; },
    setAttribute(name, value) { this.attrs[name] = value; },
    removeAttribute(name) { delete this.attrs[name]; },
    querySelectorAll() { return []; } };
}
const names = [
  '#mobile-menu-toggle','#mobile-menu','#header-login-link','#header-logout-btn',
  '#mobile-auth-link','#header-admin-link','#mobile-admin-link','#mobile-profile-link',
  '#header-user-greeting','#header-user-firstname','#header-mobile-user-greeting',
  '#header-mobile-user-firstname','#header-cart-count'
];
const nodes = Object.fromEntries(names.map(name => [name, element()]));
const header = element();
header.querySelector = name => nodes[name] || null;
header.contains = () => true;
const document = { readyState: 'complete', querySelector: name => name === '.header' ? header : null,
  addEventListener() {} };
const listeners = {};
let current = null;
const session = {
  currentUser: () => current,
  token: () => current ? 'token' : null,
  clear: () => { current = null;listeners['beatpass:session-changed']?.(); }
};
const window = { BeatPass: { session, paths: {to: () => 'pages/login.html'} },
  addEventListener(name, fn) { listeners[name] = fn; } };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'js/components/organisms/header.js'), 'utf8'),
  {window, document, Event: class Event {constructor(type){this.type=type;} } });
const isHidden = name => nodes[name].hidden;
assert.ok(isHidden('#header-user-greeting'), 'No debe mostrar nombre sin sesión');
assert.ok(isHidden('#header-mobile-user-greeting'));
assert.ok(isHidden('#mobile-profile-link'));
current = {fullname: 'Laura Fernanda Ruiz', roles: ['cliente']};
listeners['beatpass:session-changed']();
assert.equal(nodes['#header-user-firstname'].textContent, 'Laura');
assert.equal(nodes['#header-mobile-user-firstname'].textContent, 'Laura');
assert.equal(isHidden('#header-user-greeting'), false);
assert.equal(isHidden('#header-mobile-user-greeting'), false);
assert.equal(isHidden('#mobile-profile-link'), false);
assert.equal(nodes['#mobile-auth-link'].textContent, 'Cerrar sesión');
assert.equal(isHidden('#header-login-link'), true);
nodes['#header-logout-btn'].listeners.click();
assert.ok(isHidden('#header-user-greeting'));
assert.ok(isHidden('#header-mobile-user-greeting'));
assert.ok(isHidden('#mobile-profile-link'));
assert.equal(nodes['#mobile-auth-link'].textContent, 'Entrar');
assert.equal(isHidden('#header-login-link'), false);
console.log('OK: saludo de usuario, sesión y cierre de sesión en header');
