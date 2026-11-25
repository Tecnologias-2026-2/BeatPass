(function (global) {
  'use strict';
  // Servidores estáticos de desarrollo (Live Server :5500, http.server :8001, file://)
  // no reenvían /api al backend: se apunta directamente a la API local.
  const params = new URLSearchParams(global.location.search);
  const override = (params.get('api') || global.BEATPASS_API_BASE_URL || '').trim().replace(/\/+$/, '');
  const isFile = global.location.protocol === 'file:';
  const staticDevServer = isFile || ['5500', '8001'].includes(global.location.port);
  const host = global.location.hostname || '127.0.0.1';
  const defaultApi = staticDevServer
    ? `${isFile ? 'http:' : global.location.protocol}//${host}:8010/api`
    : '/api';
  const app = global.BeatPass = global.BeatPass || {};
  app.config = Object.freeze({ apiBaseUrl: override || defaultApi });
})(window);
