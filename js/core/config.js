(function (global) {
  'use strict';
  const params = new URLSearchParams(global.location.search);
  const override = (params.get('api') || global.BEATPASS_API_BASE_URL || '').trim().replace(/\/+$/, '');
  const isFile = global.location.protocol === 'file:';
  const staticDevServer = isFile || ['5500', '8001'].includes(global.location.port);
  const host = global.location.hostname || '127.0.0.1';
  const isGithubPages = host.endsWith('.github.io');
  const defaultApi = staticDevServer
    ? `${isFile ? 'http:' : global.location.protocol}//${host}:8010/api`
    : (isGithubPages ? 'https://beatpass-1.onrender.com/api' : '/api');
  const app = global.BeatPass = global.BeatPass || {};
  app.config = Object.freeze({ apiBaseUrl: override || defaultApi });
})(window);
