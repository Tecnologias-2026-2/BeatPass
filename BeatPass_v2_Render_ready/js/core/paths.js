// FLUJO: header.js y auth-ui.js construyen enlaces de páginas con paths.to().
/**
 * Rutas relativas a la raíz. No usa fetch() ni import/export:
 * se puede abrir index.html directamente desde el disco.
 */
(function (global) {
    'use strict';
    const app = global.BeatPass = global.BeatPass || {};
    const pages = Object.freeze({
        home: 'pages/destacados.html',
        welcome: 'index.html',
        catalog: 'pages/catalog.html',
        destacados: 'pages/destacados.html',
        cart: 'pages/cart.html',
        profile: 'pages/profile.html',
        tickets: 'pages/tickets.html',
        login: 'pages/login.html',
        register: 'pages/register.html',
        forgotPassword: 'pages/forgot-password.html',
        resetPassword: 'pages/reset-password.html',
        verifyEmail: 'pages/verify-email.html',
        acceptInvitation: 'pages/accept-invitation.html',
        adminDashboard: 'pages/admin/dashboard.html'
    });

    function rootPrefix() {
        const path = decodeURIComponent(global.location.pathname || '').replace(/\\/g, '/');
        const match = path.match(/\/pages\/(.+\.html)$/i);
        return match ? '../'.repeat(match[1].split('/').length) : '';
    }

    function to(page) {
        if (!Object.prototype.hasOwnProperty.call(pages, page)) {
            throw new Error(`Página desconocida: ${page}`);
        }
        return rootPrefix() + pages[page];
    }

    function currentPage() {
        const name = (global.location.pathname || '').split(/[/\\]/).pop().toLowerCase();
        return Object.keys(pages).filter(page => page !== 'home').find(page => pages[page].endsWith('/' + name) || pages[page] === name) || 'home';
    }

    app.paths = Object.freeze({ to, currentPage, rootPrefix });
})(window);
