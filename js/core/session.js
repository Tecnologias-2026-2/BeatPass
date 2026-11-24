// FLUJO: auth-ui.js guarda JWT; header.js y profile.js consultan sesión.
/**
 * Una única fuente para la sesión del frontend.
 * La información del cliente SOLO sirve para la interfaz;
 * la autorización real la hará siempre el backend.
 */
(function (global) {
    'use strict';
    const app = global.BeatPass = global.BeatPass || {};
    const TOKEN_KEY = 'beatpass_token';
    const USER_KEY = 'beatpass_user';

    function hasUnexpiredToken(token) {
        if (typeof token !== 'string') return false;
        try {
            const encoded = token.split('.')[1];
            if (!encoded) return false;
            const normalized = encoded.replace(/-/g, '+').replace(/_/g, '/');
            const claims = JSON.parse(global.atob(normalized));
            return Number.isFinite(claims.exp) && claims.exp > Date.now() / 1000;
        } catch (error) {
            return false;
        }
    }

    function currentUser() {
        const token = app.storage.read(TOKEN_KEY);
        if (!hasUnexpiredToken(token)) return null;
        const user = app.storage.readJson(USER_KEY);
        return user && typeof user.fullname === 'string' ? user : null;
    }

    function save(token, user) {
        if (!hasUnexpiredToken(token) || !user || typeof user.fullname !== 'string') {
            throw new Error('Respuesta de autenticación incompleta.');
        }
        const tokenSaved = app.storage.write(TOKEN_KEY, token);
        const userSaved = app.storage.write(USER_KEY, JSON.stringify(user));
        if (!tokenSaved || !userSaved) {
            app.storage.remove(TOKEN_KEY);
            app.storage.remove(USER_KEY);
            throw new Error('El navegador no permite guardar la sesión.');
        }
        global.dispatchEvent(new Event('beatpass:session-changed'));
    }

    function clear() {
        app.storage.remove(TOKEN_KEY);
        app.storage.remove(USER_KEY);
        // La cuenta y el carrito se consultan en el servidor.
        global.dispatchEvent(new Event('beatpass:session-changed'));
    }

    app.session = Object.freeze({ currentUser, save, clear, token: () => app.storage.read(TOKEN_KEY) });
})(window);
