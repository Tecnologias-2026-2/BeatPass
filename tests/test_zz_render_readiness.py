"""Contrato de publicación pública y reserva TEST sin confirmación DEMO."""
import os
import subprocess
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from test_phase2d import account, published, add
from backend.main import app
from backend import payments, orders

ROOT = Path(__file__).resolve().parents[1]


def test_render_build_excludes_fake_events(tmp_path):
    env = {**os.environ, 'API_BASE_URL':'https://api-ejemplo.onrender.com/api'}
    result = subprocess.run([sys.executable,'tools/build_static.py'],cwd=ROOT,env=env,
        capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    published_html = (ROOT/'public/pages/destacados.html').read_text()
    assert 'Tu próximo evento comienza aquí' in published_html
    assert 'Noche de Rock Clásico' not in published_html
    assert 'sandbox_init_point' not in published_html
    js = (ROOT/'public/js/core/config.js').read_text()
    assert 'https://api-ejemplo.onrender.com/api' in js
    assert '127.0.0.1' not in js
    examples = (ROOT/'public/js/core/demo-events.js').read_text()
    assert 'Noche de Rock Clásico' not in examples
    assert not (ROOT/'public/style-guide.html').exists()


def test_payment_sandbox_can_reserve_when_demo_confirmation_disabled(monkeypatch):
    with TestClient(app) as client:
        event, _, _ = published(client, cap=2)
        _, buyer = account()
        add(client,buyer,event,1)
        monkeypatch.setattr(orders,'DEMO_CHECKOUT_ENABLED',False)
        monkeypatch.setattr(payments,'PAYMENT_MODE','mercadopago_sandbox')
        config=client.get('/api/checkout/config').json()
        assert not config['demo_enabled'] and config['sandbox_enabled']
        held=client.post('/api/checkout/hold',headers=buyer)
        assert held.status_code==201, held.text
        manual=client.post(f"/api/orders/{held.json()['id']}/confirm-demo",headers=buyer)
        assert manual.status_code==503


def test_bootstrap_not_enabled_by_default(monkeypatch):
    from backend.cli import bootstrap_render_admin
    monkeypatch.delenv('BEATPASS_BOOTSTRAP_ADMIN_ENABLED',raising=False)
    assert bootstrap_render_admin() is None
