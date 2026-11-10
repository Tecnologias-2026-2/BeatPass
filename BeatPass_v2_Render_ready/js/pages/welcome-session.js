// FLUJO: index.html -> api.me() y session.js; envía a destacados si está validado.
/** Quien ya inició sesión puede pasar directo de bienvenida a Destacados. */
(function (global) {
  'use strict';
  const app = global.BeatPass;
  if (!app?.session?.token()) return;
  app.api.me().then(() => {
    // Redirección solo después de que el backend valide el token.
    global.location.replace(app.paths.to('destacados'));
  }).catch(error => {
    // Error de red: mantener bienvenida, sin borrar una sesión potencialmente válida.
    if (error.status === 401) app.session.clear();
  });
})(window);
