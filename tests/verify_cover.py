"""Comprobaciones estáticas de la carga local de portadas (sin navegador ni backend)."""
# FLUJO: Prueba aislada -> backend/main.py y rutas relacionadas; no modifica BD de usuario.
from pathlib import Path
root = Path(__file__).resolve().parents[1]
html = (root / 'pages/admin/dashboard.html').read_text(encoding='utf-8')
css = (root / 'css/pages/admin.css').read_text(encoding='utf-8')
js = (root / 'js/pages/admin-events.js').read_text(encoding='utf-8')
helper = (root / 'js/core/cover-images.js').read_text(encoding='utf-8')
for name in ('event-cover-file', 'event-cover-status', 'admin-remove-cover', 'preview-image-placeholder'):
    assert f'id="{name}"' in html, name
assert 'type="file"' in html and 'accept="image/jpeg,image/png,image/webp"' in html
assert 'id="event-image"' not in html, 'No debe existir selector de portadas de prueba'
assert '../../js/core/cover-images.js' in html
assert 'BeatPassCoverImages' in js and 'BeatPassCoverImages' in helper
assert 'prepare(file)' in helper and 'createObjectURL' in js
assert '.bp-admin__preview-cover-empty' in css
assert 'api.uploadEventCover' in js
print('OK: portadas optimizadas, vista previa y guardado remoto seguro')
