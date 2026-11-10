"""Comprueba estructura de diseño atómico, header visible sin JS y logo único."""
# FLUJO: Prueba aislada -> backend/main.py y rutas relacionadas; no modifica BD de usuario.
from pathlib import Path
from html.parser import HTMLParser
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / 'index.html', *(ROOT / 'pages').rglob('*.html'), ROOT / 'style-guide.html']

class Check(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headers = []
        self.images = []
        self.references = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'header' and 'header' in a.get('class', '').split(): self.headers.append(a)
        if tag == 'img': self.images.append(a)
        if tag in ('img', 'script') and a.get('src'): self.references.append(a['src'])
        if tag == 'link' and a.get('href') and a.get('rel') in ('icon', 'stylesheet'): self.references.append(a['href'])

for page in PAGES:
    data = page.read_text(encoding='utf-8')
    check = Check(); check.feed(data)
    assert len(check.headers) == 1, (page, 'debe haber exactamente un header')
    assert not any('logo-movil' in src for src in check.references)
    assert any('logo-principal.svg' in img.get('src', '') for img in check.images), page
    assert 'id="header-placeholder"' not in data, page
    assert 'BEATPASS HEADER START' in data and 'BEATPASS HEADER END' in data, page
    for ref in check.references:
        if ref.startswith(('http:', 'https:', 'data:', '#')): continue
        assert (page.parent / ref).is_file(), (page, ref)
    print('OK:', page.relative_to(ROOT), 'tiene cabecera estática y recursos válidos')

assert not (ROOT / 'assets/logo-movil.svg').exists()
subprocess.run([sys.executable, str(ROOT / 'tools/build_components.py'), '--check'], check=True)
print('OK: única fuente SVG, componente compartido sincronizado')
