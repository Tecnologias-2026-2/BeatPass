"""Compila componentes HTML estáticos y datos de eventos de demostración.

Conserva las plantillas fuente. build_static.py publica solo eventos aprobados.
Después de cambiar componentes/ o data/demo-events.json, ejecutar:
    python tools/build_components.py
    python tools/build_components.py --check
"""
# FLUJO: Lee components/ y data/demo-events.json; genera header, footer y eventos demo en HTML.
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HEADER = (ROOT / 'components/organisms/header.html').read_text(encoding='utf-8').strip()
BRAND = (ROOT / 'components/molecules/brand.html').read_text(encoding='utf-8').strip()
FOOTER = (ROOT / 'components/organisms/site-footer.html').read_text(encoding='utf-8').strip()
CAROUSEL = (ROOT / 'components/organisms/featured-carousel.html').read_text(encoding='utf-8').strip()
CARD = (ROOT / 'components/organisms/event-card.html').read_text(encoding='utf-8').strip()
EVENTS = json.loads((ROOT / 'data/demo-events.json').read_text(encoding='utf-8'))
PAGES = [ROOT / 'index.html', *sorted((ROOT / 'pages').rglob('*.html')), ROOT / 'style-guide.html']


def apply_file(path: Path, content: str, check: bool) -> bool:
    existing = path.read_text(encoding='utf-8') if path.is_file() else None
    if existing != content:
        if check:
            print('DESACTUALIZADO:', path.relative_to(ROOT))
            return False
        path.write_text(content, encoding='utf-8')
        print('GENERADO:', path.relative_to(ROOT))
    return True


def replace_block(source: str, name: str, value: str) -> str:
    start, end = f'<!-- BEATPASS {name} START -->', f'<!-- BEATPASS {name} END -->'
    pattern = re.escape(start)+r'.*?'+re.escape(end)
    updated, count = re.subn(pattern, lambda _: f'{start}\n{value}\n{end}', source, count=1, flags=re.S)
    assert count == 1, f'Bloque {name} ausente o duplicado'
    return updated


def build_header(page: Path) -> str:
    prefix = '../' * (len(page.relative_to(ROOT).parts)-1)
    value = HEADER.replace('{{BRAND}}', BRAND).replace('{{ROOT}}', prefix)
    current = page.stem
    value = re.sub(r'(data-target="'+re.escape(current)+r'"[^>]*)(>)',
                   r'\1 aria-current="page"\2', value)
    return value


def build_footer(page: Path) -> str:
    prefix = '../' * (len(page.relative_to(ROOT).parts)-1)
    return FOOTER.replace('{{ROOT}}', prefix)


def event_slides() -> str:
    result=[]
    for i, event in enumerate(EVENTS):
        get=lambda name: html.escape(str(event[name]),quote=True)
        cheapest=min(int(z['price']) for z in event['ticketTypes'])
        delay=0 if i==0 else -(len(EVENTS)-i)*20
        level='h1' if i==0 else 'h2'
        slide=f'''  <article class="bp-featured__slide bp-featured__slide--{i+1}" style="--slide-delay:{delay}s" aria-label="Evento destacado {i+1} de {len(EVENTS)}: {get('title')}">
    <img class="hero-background" src="{get('image')}" alt="" aria-hidden="true" {'fetchpriority="high"' if i==0 else 'loading="lazy"'}>
    <div class="hero-overlay" aria-hidden="true"></div>
    <div class="hero-content"><div class="hero-text-wrapper">
      <span class="featured-badge">EVENTO DESTACADO · {i+1} DE {len(EVENTS)}</span>
      <{level} class="hero-title">{get('title')}</{level}>
      <p class="hero-description">{get('short')}</p>
      <div class="event-details">
        <div class="detail-item"><span aria-hidden="true">◷</span><span class="detail-text">{get('date')} · {get('time')}</span></div>
        <div class="detail-item"><span aria-hidden="true">⌖</span><span class="detail-text">{get('venue')}</span></div>
      </div>
      <div class="hero-actions">
        <a class="btn btn-primary" href="event-detail.html?id={get('id')}">Explorar evento <span aria-hidden="true">→</span></a>
        <div class="price-section"><span class="price-label">Desde</span><span class="price-value">${cheapest}</span></div>
      </div>
    </div></div>
  </article>'''
        result.append(slide)
    return CAROUSEL.replace('{{SLIDES}}','\n'.join(result))


def event_cards() -> str:
    rendered=[]
    for event in EVENTS:
        values={
            'ID':event['id'],'TITLE':event['title'],'CATEGORY':event['category'],
            'IMAGE':event['image'],'DATE':event['date'],'TIME':event['time'],
            'VENUE':event['venue'],'PRICE':min(int(z['price']) for z in event['ticketTypes'])
        }
        markup=CARD
        for key,value in values.items():
            markup=markup.replace('{{'+key+'}}',html.escape(str(value),quote=True))
        rendered.append(markup)
    return '                    <div class="events-grid">\n'+'\n'.join(rendered)+'\n                    </div>'


def build_demo_js() -> str:
    return '''// FLUJO: data/demo-events.json -> build_components.py -> catalog-demo.js (solo ejemplo).
/** Eventos de DEMOSTRACIÓN. Fuente editable: data/demo-events.json. Sin datos de inventario real. */
(function (global) {
  'use strict';
  const app = global.BeatPass = global.BeatPass || {};
  const events = '''+json.dumps(EVENTS,ensure_ascii=False,indent=2)+''';
  const enriched = events.map(event => {
    const ticketTypes = Object.freeze(event.ticketTypes.map(type => Object.freeze(type)));
    const minPrice = Math.min(...ticketTypes.map(type => type.price));
    return Object.freeze({ ...event, ticketTypes, minPrice });
  });
  app.demoEvents = Object.freeze(enriched);
})(window);
'''


def compile_page(page: Path, check: bool) -> bool:
    content=page.read_text(encoding='utf-8')
    content=replace_block(content,'HEADER',build_header(page))
    content=replace_block(content,'SITE FOOTER',build_footer(page))
    if page.name=='destacados.html':
        content=replace_block(content,'CAROUSEL',event_slides())
        content=replace_block(content,'CARDS',event_cards())
    return apply_file(page,content,check)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    outcomes=[apply_file(ROOT/'js/core/demo-events.js',build_demo_js(),args.check)]
    outcomes.extend(compile_page(p,args.check) for p in PAGES)
    raise SystemExit(0 if all(outcomes) else 1)
