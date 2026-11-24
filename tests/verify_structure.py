"""Revisa que no se rompan enlaces o CSS durante la reconstrucción."""
# FLUJO: Prueba aislada -> backend/main.py y rutas relacionadas; no modifica BD de usuario.
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]

class Dependencies(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.styles = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'script' and a.get('src'):
            self.scripts.append(a['src'])
        if tag == 'link' and a.get('rel') == 'stylesheet':
            self.styles.append(a['href'])

for page in list(ROOT.glob('*.html')) + list((ROOT / 'pages').rglob('*.html')):
    checker = Dependencies()
    checker.feed(page.read_text(encoding='utf-8'))
    for ref in checker.scripts + checker.styles:
        assert (page.parent / ref).is_file(), f'{page.relative_to(ROOT)} falta: {ref}'
    print(f'OK: {page.relative_to(ROOT)} ({len(checker.scripts)} scripts, {len(checker.styles)} CSS)')

for stylesheet in (ROOT / 'css').glob('*.css'):
    assert stylesheet.stat().st_size > 0
print('Dependencias locales: OK')
