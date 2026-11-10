// FLUJO: admin-events.js prepara portadas y api.js las envía a backend/events.py.
/** Optimiza imágenes en el navegador; admin-events.js las envía al servidor. */
(function (global) {
  'use strict';
  const MAX_FILE_SIZE = 8 * 1024 * 1024;
  const TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      const clean = () => URL.revokeObjectURL(url);
      img.onload = () => { clean(); resolve(img); };
      img.onerror = () => { clean(); reject(new Error('No pudimos abrir esta imagen. Selecciona otra fotografía.')); };
      img.src = url;
    });
  }

  async function prepare(file) {
    if (!file || !TYPES.has(file.type)) throw new Error('Usa una imagen JPG, PNG o WebP.');
    if (file.size > MAX_FILE_SIZE) throw new Error('La imagen supera los 8 MB permitidos.');
    if (file.size === 0) throw new Error('El archivo de imagen está vacío.');

    const img = await loadImage(file);
    const naturalWidth = img.naturalWidth, naturalHeight = img.naturalHeight;
    if (!naturalWidth || !naturalHeight || naturalWidth * naturalHeight > 40_000_000) {
      throw new Error('La resolución de la imagen no es compatible.');
    }
    const scale = Math.min(1, 1600 / Math.max(naturalWidth, naturalHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(naturalHeight * scale));
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('El navegador no puede preparar esta imagen.');
    // Una foto PNG transparente se verá con un fondo del color del panel, no negro.
    ctx.fillStyle = '#0e1e37';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.82));
    if (!blob) throw new Error('No fue posible preparar la fotografía.');
    return blob;
  }

  global.BeatPassCoverImages = Object.freeze({prepare});
})(window);
