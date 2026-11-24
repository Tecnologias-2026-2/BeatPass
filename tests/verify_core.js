// FLUJO: Prueba estática de js/ y componentes; usa Node sin backend.
'use strict';
// Pruebas sin dependencias: se ejecutan en Node, aislando cada navegador falso.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

function createBrowser(pathname) {
    const items = new Map();
    const window = {
        location: { pathname },
        localStorage: {
            getItem: key => items.get(key) ?? null,
            setItem: (key, value) => items.set(key, value),
            removeItem: key => items.delete(key),
        },
        atob: value => Buffer.from(value, 'base64').toString('binary'),
        dispatchEvent: () => {},
    };
    const context = vm.createContext({ window, Date, Number, JSON, Object, Event: class Event { constructor(type) { this.type = type; } } });
    for (const file of ['storage.js', 'paths.js', 'session.js']) {
        vm.runInContext(fs.readFileSync(path.join(root, 'js/core', file), 'utf8'), context, { filename: file });
    }
    return window.BeatPass;
}

const home = createBrowser('/beatpass/index.html');
assert.equal(home.paths.to('catalog'), 'pages/catalog.html');
assert.equal(home.paths.currentPage(), 'welcome');
assert.equal(home.paths.to('home'), 'pages/destacados.html');
assert.equal(home.session.currentUser(), null);
assert.equal(home.storage.readJson('missing', 'fallback'), 'fallback');
home.storage.write('bad', 'not-json');
assert.equal(home.storage.readJson('bad', null), null);

const login = createBrowser('/beatpass/pages/login.html');
assert.equal(login.paths.to('home'), '../pages/destacados.html');
assert.equal(login.paths.to('welcome'), '../index.html');
assert.equal(login.paths.to('catalog'), '../pages/catalog.html');
assert.equal(login.paths.currentPage(), 'login');
assert.throws(() => login.paths.to('random-page'), /desconocida/);

// Token de test, firma inventada; solo comprueba estado del UI, NO autenticación.
const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
login.session.save(`header.${payload}.not-a-real-signature`, { fullname: 'Usuario Prueba' });
assert.equal(login.session.currentUser().fullname, 'Usuario Prueba');
login.session.clear();
assert.equal(login.session.currentUser(), null);
console.log('OK: rutas, JSON seguro y sesión UI');
