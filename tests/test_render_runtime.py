"""Contratos mínimos del despliegue en Render: orígenes y web servida por la API."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_produccion_autoriza_los_origenes_publicos():
    code = (ROOT / 'backend' / 'config.py').read_text(encoding='utf-8')
    assert 'https://tecnologias-2026-2.github.io' in code
    assert 'https://beatpass-1.onrender.com' in code
    assert 'https://beatpass-fvc6.onrender.com' in code


def test_api_sirve_la_web_generada_en_el_mismo_servicio():
    code = (ROOT / 'backend' / 'main.py').read_text(encoding='utf-8')
    assert 'StaticFiles' in code
    assert "app.mount('/', StaticFiles" in code


def test_build_de_render_genera_public():
    code = (ROOT / 'render.yaml').read_text(encoding='utf-8')
    assert 'python tools/build_static.py' in code
