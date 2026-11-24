// FLUJO: session.js usa estos helpers para leer y guardar preferencias del navegador.
/**
 * Acceso seguro a localStorage. Verifica disponibilidad del almacenamiento del navegador.
 */
(function (global) {
    'use strict';
    const app = global.BeatPass = global.BeatPass || {};

    function read(key) {
        try { return global.localStorage.getItem(key); }
        catch (error) { return null; }
    }

    function write(key, value) {
        try { global.localStorage.setItem(key, value); return true; }
        catch (error) { return false; }
    }

    function remove(key) {
        try { global.localStorage.removeItem(key); return true; }
        catch (error) { return false; }
    }

    function readJson(key, fallback = null) {
        const value = read(key);
        if (value === null) return fallback;
        try { return JSON.parse(value); }
        catch (error) { return fallback; }
    }

    app.storage = Object.freeze({ read, write, remove, readJson });
})(window);
