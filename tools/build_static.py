"""Genera la web pública con API HTTPS y contenido aprobado exclusivamente."""
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH = ROOT / 'public'
API_BASE_URL = os.getenv('API_BASE_URL', '').strip().rstrip('/')
if not API_BASE_URL.startswith('https://') or not API_BASE_URL.endswith('/api'):
    raise SystemExit('API_BASE_URL debe utilizar HTTPS y terminar en /api.')
if PUBLISH.exists():
    shutil.rmtree(PUBLISH)
PUBLISH.mkdir()
shutil.copy2(ROOT / 'index.html', PUBLISH / 'index.html')
for directory in ['pages', 'assets', 'css', 'js']:
    shutil.copytree(ROOT / directory, PUBLISH / directory)
(PUBLISH / 'js/core/config.js').write_text(
    '(function(w){"use strict";const b=w.BeatPass=w.BeatPass||{};b.config=Object.freeze({apiBaseUrl:'
    + json.dumps(API_BASE_URL) + '});})(window);\n', encoding='utf-8'
)
# Los ejemplos del repositorio son fixtures de diseño, no ofertas disponibles al público.
(PUBLISH / 'js/core/demo-events.js').write_text(
    '(function(w){w.BeatPass=w.BeatPass||{};w.BeatPass.demoEvents=Object.freeze([]);})(window);\n',
    encoding='utf-8'
)
featured = PUBLISH / 'pages/destacados.html'
markup = featured.read_text(encoding='utf-8')
public_hero = """<section class="bp-public-hero" aria-labelledby="bp-public-hero-title">
  <div class="bp-public-hero__inner">
    <span class="featured-badge">BEATPASS · EXPERIENCIAS EN VIVO</span>
    <h1 id="bp-public-hero-title">Tu próximo evento comienza aquí</h1>
    <p>Descubre conciertos, teatro y experiencias culturales. Explora las publicaciones aprobadas por BeatPass.</p>
    <a href="catalog.html" class="btn btn-primary">Explorar eventos <span aria-hidden="true">→</span></a>
  </div>
</section>"""
markup, n = re.subn(r'<!-- BEATPASS CAROUSEL START -->.*?<!-- BEATPASS CAROUSEL END -->',
                    public_hero, markup, count=1, flags=re.S)
if n != 1:
    raise SystemExit('No se encontró el bloque de presentación en Destacados.')
markup, n = re.subn(r'<!-- BEATPASS CARDS START -->.*?<!-- BEATPASS CARDS END -->',
                    '', markup, count=1, flags=re.S)
if n != 1:
    raise SystemExit('No se encontró el bloque de tarjetas de muestra.')
markup = re.sub(r'<p class="featured-sample-note">.*?</p>', '', markup, count=1, flags=re.S)
markup = markup.replace('Seleccionamos cuatro experiencias de muestra para imaginar lo que viene en BeatPass.',
                        'Encuentra eventos publicados por organizadores aprobados.')
markup = markup.replace('Eventos destacados</h2>', 'Eventos publicados</h2>')
markup = markup.replace('Destacados de demostración', 'Eventos destacados')
featured.write_text(markup, encoding='utf-8')
print('Web pública lista para Render; API configurada y ejemplos no publicados.')
