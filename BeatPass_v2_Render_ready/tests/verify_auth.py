"""Verificaciones estáticas: registro, verificación, recuperación e invitaciones."""
# FLUJO: Prueba aislada -> backend/main.py y rutas relacionadas; no modifica BD de usuario.
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['login', 'register', 'forgot-password', 'reset-password', 'verify-email', 'accept-invitation']

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set(); self.links=[]; self.forms=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if d.get('id'):
            assert d['id'] not in self.ids, f'ID duplicado: {d["id"]}'
            self.ids.add(d['id'])
        if tag=='a' and d.get('href'): self.links.append(d['href'])
        if tag=='form':self.forms+=1

for name in PAGES:
    path = ROOT/'pages'/f'{name}.html'
    data = path.read_text(encoding='utf-8')
    parser=PageParser();parser.feed(data)
    assert parser.forms == 1, (name, parser.forms)
    assert 'bp-auth-card' in data and 'bp-site-footer' in data
    assert '<!-- BEATPASS HEADER START -->' in data
    assert '<!-- BEATPASS SITE FOOTER START -->' in data
    assert '../js/pages/auth-ui.js' in data
    assert '../css/pages/auth.css' in data
    assert '../js/pages/pending.js' not in data
    assert 'logo-movil.svg' not in data
    for href in parser.links:
        if href.startswith(('http:','https:','mailto:','#')):continue
        local=href.split('?',1)[0].split('#',1)[0]
        assert (path.parent/local).is_file(), (name,href)
    print('OK:',name)
reg=(ROOT/'pages/register.html').read_text(encoding='utf-8')
assert 'organizer-fields' in reg and 'value="organizador"' in reg
assert 'value="administrador"' not in reg
assert 'aprobación' in reg
login=(ROOT/'pages/login.html').read_text(encoding='utf-8')
assert 'perfil=administracion' in login and 'forgot-password.html' in login
assert 'reset-password.html?demo=1' not in (ROOT/'pages/forgot-password.html').read_text(encoding='utf-8')
assert 'resend-form' in (ROOT/'pages/verify-email.html').read_text(encoding='utf-8')
assert 'accept-invitation-form' in (ROOT/'pages/accept-invitation.html').read_text(encoding='utf-8')
js=(ROOT/'js/pages/auth-ui.js').read_text(encoding='utf-8')
for forbidden in ['localStorage', 'sessionStorage', 'XMLHttpRequest', 'BeatPass.session.set']:
    assert forbidden not in js, forbidden
assert 'window.BeatPass.api.login' in js and 'window.BeatPass.api.register' in js
assert 'window.BeatPass.session.save' in js
print('OK: rutas, verificación y recuperación conectadas a API e invitaciones administrativas')
