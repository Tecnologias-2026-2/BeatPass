"""Verifica la integración local de la nueva bienvenida con el proyecto."""
# FLUJO: Prueba aislada -> backend/main.py y rutas relacionadas; no modifica BD de usuario.
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.images = []
        self.ids = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'): self.ids.add(a['id'])
        if tag == 'img' and a.get('src'): self.images.append(a['src'])
        if tag == 'a' and a.get('href'): self.links.append(a['href'])

home = ROOT / 'index.html'
data = home.read_text(encoding='utf-8')
parsed = Assets(); parsed.feed(data)
assert 'welcome-hero' in data
assert {'main-content', 'quienes-somos', 'como-funciona'}.issubset(parsed.ids)
assert 'pages/destacados.html' in parsed.links
assert 'pages/login.html' in parsed.links
assert 'pages/register.html' in parsed.links
assert 'assets/logo-principal.svg' in parsed.images
assert len([src for src in parsed.images if src.startswith('assets/visuals/')]) == 3
assert 'logo-movil.svg' not in data
assert (ROOT/'css/pages/welcome.css').is_file()
assert (ROOT/'pages/destacados.html').is_file()
for link in parsed.links:
    if link.startswith(('#','mailto:','http:','https:')): continue
    path=link.split('#',1)[0].split('?',1)[0]
    assert (ROOT/path).is_file(), link
for asset in parsed.images:
    if asset.startswith(('http:','https:','data:')): continue
    assert (ROOT/asset).is_file(), asset
assert all((ROOT/'css'/css).is_file() for css in ['styles.css','catalog.css','login.css','register.css','tickets.css'])
print('OK: bienvenida, enlaces, anclas, logo único, ilustraciones locales y portada antigua conservada')
