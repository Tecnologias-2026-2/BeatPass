// FLUJO: catalog-demo.js / featured-live.js -> este organismo -> tarjetas DOM.
/** Constructor visual compartido. Los datos y permisos vienen de api.js, no de esta tarjeta. */
(function (global) {
  'use strict';
  const app = global.BeatPass = global.BeatPass || {};
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function eventCard(item, opts = {}) {
    const demo = Boolean(opts.demo);
    const card = element('article', 'event-card bp-event-card' + (opts.catalog ? ' bp-catalog-card' : ''));
    card.setAttribute('role', 'listitem');
    const link = element('a', 'bp-event-card__link');
    link.href = `event-detail.html?id=${encodeURIComponent(demo ? item.id : 'live-' + item.id)}`;
    link.setAttribute('aria-label', `Consultar ${item.title}`);
    const cover = element('div', 'event-image-wrapper');
    const image = element('img', 'event-image');
    image.src = demo ? (item.image || '../assets/visuals/concierto.svg')
      : (app.api.assetUrl(item.image_url) || '../assets/visuals/concierto.svg');
    image.loading = 'lazy';
    image.alt = `Portada de ${item.title}`;
    cover.append(image, element('span', 'event-category', item.category));
    const content = element('div', 'event-card-content');
    content.append(element('h3', 'event-card-title', item.title));
    const details = element('div', 'event-card-details');
    details.append(element('p', 'card-detail', `📅 ${item.date} · ${item.time}`),
      element('p', 'card-detail', `📍 ${item.venue}, ${item.city || ''}`));
    content.append(details);
    const footer = element('div', 'event-card-footer');
    const price = element('span', 'bp-price-from');
    price.append(element('span', '', 'Desde'),
      element('strong', '', `$${Number(item.minPrice).toLocaleString('es-CO')}`));
    footer.append(price, element('span', 'bp-card-cta', 'Explorar evento →'));
    content.append(footer);
    link.append(cover, content);
    card.append(link);
    return card;
  }
  app.eventCard = eventCard;
})(window);
