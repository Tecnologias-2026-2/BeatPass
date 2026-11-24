"""Verificación estática de Fase 1.9 (carrusel CSS, tarjeta y precios)."""
# FLUJO: Prueba aislada -> backend/main.py y rutas relacionadas; no modifica BD de usuario.
from html.parser import HTMLParser
from pathlib import Path
import json, subprocess,sys
R=Path(__file__).resolve().parents[1]
E=json.loads((R/'data/demo-events.json').read_text(encoding='utf8'))
assert len(E)==4 and all(event['ticketTypes'] for event in E)
assert all(min(t['price'] for t in event['ticketTypes'])>0 for event in E)
script=(R/'js/core/demo-events.js').read_text(encoding='utf8')
assert 'Math.min(...ticketTypes.map' in script
featured=(R/'pages/destacados.html').read_text(encoding='utf8')
assert featured.count('class="bp-featured__slide')==4
assert featured.count('class="event-card bp-event-card"')==4
assert 'data-featured-toggle' not in featured and 'data-featured-prev' not in featured
assert 'js/pages/featured.js' not in featured
assert 'BEATPASS CAROUSEL START' in featured and 'BEATPASS CARDS START' in featured
assert 'Explorar eventos' in featured and 'Explorar evento' in featured
assert featured.index('featured-catalog-cta')>featured.index('BEATPASS CARDS START')
style=(R/'css/pages/featured.css').read_text(encoding='utf8')
assert '80s linear infinite' in style and '--slide-delay' in style
assert 'prefers-reduced-motion' in style and 'animation:none!important' in style
catalog=(R/'js/pages/catalog-demo.js').read_text(encoding='utf8')
assert 'app.eventCard' in catalog and 'api.publicEvents' in catalog
assert 'eventCard' in (R/'js/components/organisms/event-card.js').read_text(encoding='utf8')
assert 'item.minPrice' in (R/'js/components/organisms/event-card.js').read_text(encoding='utf8')
page=(R/'pages/event-detail.html').read_text(encoding='utf8')
assert 'event-detail-price-list' in page and 'Comprar entradas' in page
assert 'admin-gate.js' in (R/'pages/admin/dashboard.html').read_text(encoding='utf8')
assert 'admin-events.js' in (R/'js/pages/admin-gate.js').read_text(encoding='utf8')
assert 'admin-preview-link' not in (R/'pages/login.html').read_text(encoding='utf8')
for name in ('rock-clasico.webp','teatro-sombras.svg','orquesta.svg','arte.svg'):
 assert (R/'assets/visuals'/name).is_file()
assert subprocess.run([sys.executable,str(R/'tools/build_components.py'),'--check']).returncode==0
print('OK: carrusel automático 20s, enlaces de tarjeta, precios, panel 2B y componentes')
