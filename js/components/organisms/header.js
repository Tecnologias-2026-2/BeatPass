// FLUJO: header.html muestra sesión de session.js, carrito de api.js y enlace a profile.html.
/**
 * Organismo HEADER: mejora una cabecera HTML ya presente en la página.
 * No genera ni reemplaza el HTML: si JavaScript falla, la navegación
 * y el logo siguen visibles. Utiliza scripts clásicos.
 */
(function (global) {
    'use strict';

    function init() {
        const header = document.querySelector('.header');
        if (!header || header.dataset.enhanced === 'true') return;
        header.dataset.enhanced = 'true';

        const toggle = header.querySelector('#mobile-menu-toggle');
        const menu = header.querySelector('#mobile-menu');
        const authLink = header.querySelector('#header-login-link');
        const logoutButton = header.querySelector('#header-logout-btn');
        const mobileAuth = header.querySelector('#mobile-auth-link');
        const adminLink = header.querySelector('#header-admin-link');
        const mobileAdminLink = header.querySelector('#mobile-admin-link');
        const mobileProfile = header.querySelector('#mobile-profile-link');
        const desktopGreeting = header.querySelector('#header-user-greeting');
        const desktopFirstName = header.querySelector('#header-user-firstname');
        const mobileGreeting = header.querySelector('#header-mobile-user-greeting');
        const mobileFirstName = header.querySelector('#header-mobile-user-firstname');
        const session = global.BeatPass && global.BeatPass.session;
        const paths = global.BeatPass && global.BeatPass.paths;

        // Ante un fallo de carga parcial, la cabecera continúa visible.
        function currentUser() {
            try { return session ? session.currentUser() : null; }
            catch (error) { return null; }
        }

        function setMenuOpen(open) {
            if (!menu || !toggle) return;
            menu.hidden = !open;
            toggle.setAttribute('aria-expanded', String(open));
            toggle.setAttribute('aria-label', open ? 'Cerrar menú de navegación' : 'Abrir menú de navegación');
        }

        function refreshIdentity() {
            const user = currentUser();
            const canOrganize = Boolean(user && Array.isArray(user.roles) && user.roles.some(role => role === 'organizador' || role === 'administracion'));
            const firstName = user ? (user.fullname.trim().split(/\s+/)[0] || 'Usuario') : '';
            // El nombre viene de la sesión iniciada; solo es información visual.
            // FastAPI sigue decidiendo quién tiene permisos realmente.
            if (desktopGreeting) {
                desktopGreeting.hidden = !user;
                desktopGreeting.title = user ? `Sesión de ${user.fullname}` : '';
            }
            if (desktopFirstName) desktopFirstName.textContent = firstName;
            if (mobileGreeting) {
                mobileGreeting.hidden = !user;
                mobileGreeting.title = user ? `Sesión de ${user.fullname}` : '';
            }
            if (mobileFirstName) mobileFirstName.textContent = firstName;
            if (mobileProfile) mobileProfile.hidden = !user;
            if (adminLink) adminLink.hidden = !canOrganize;
            if (mobileAdminLink) mobileAdminLink.hidden = !canOrganize;
            if (authLink) authLink.hidden = Boolean(user);
            if (logoutButton) logoutButton.hidden = !user;
            if (mobileAuth) {
                mobileAuth.textContent = user ? 'Cerrar sesión' : 'Entrar';
                if (user) mobileAuth.removeAttribute('href');
                else if (paths) mobileAuth.setAttribute('href', paths.to('login'));
            }
        }

        // Indicador de entradas oficial, actualizado desde la API.
        async function refreshCartBadge() {
            const badge = header.querySelector('#header-cart-count');
            if (!badge) return;
            const api = global.BeatPass?.api;
            const currentToken = session?.token();
            if (!currentToken || !currentUser() || !api?.cart) {
                badge.hidden = true;badge.textContent = '';return;
            }
            try {
                const cart = await api.cart();
                if (session.token() !== currentToken) return;
                badge.textContent = String(cart.total_items);
                badge.hidden = cart.total_items === 0;
            } catch (_) {
                badge.hidden = true;
            }
        }

        function logout() {
            if (!session) return;
            session.clear();
            setMenuOpen(false);
            refreshIdentity();
            void refreshCartBadge();
        }

        if (toggle) toggle.addEventListener('click', () => setMenuOpen(Boolean(menu && menu.hidden)));
        if (menu) menu.querySelectorAll('.mobile-menu-link').forEach(link => {
            link.addEventListener('click', event => {
                if (link === mobileAuth && currentUser()) {
                    event.preventDefault();
                    logout();
                } else setMenuOpen(false);
            });
        });
        if (logoutButton) logoutButton.addEventListener('click', logout);
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') setMenuOpen(false);
        });
        document.addEventListener('click', event => {
            if (menu && !menu.hidden && !header.contains(event.target)) setMenuOpen(false);
        });
        global.addEventListener('beatpass:session-changed', () => { refreshIdentity(); void refreshCartBadge(); });
        global.addEventListener('beatpass:cart-updated', () => void refreshCartBadge());
        global.addEventListener('storage', event => {
            if (event.key === 'beatpass_token' || event.key === 'beatpass_user') { refreshIdentity(); void refreshCartBadge(); }
        });
        refreshIdentity();
        void refreshCartBadge();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})(window);
