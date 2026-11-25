"""Servidor de desarrollo de BeatPass: sirve la web y reenvía /api al backend.

Uso:
    python tools/serve_local.py
    python tools/serve_local.py --port 5500
    python tools/serve_local.py --api http://127.0.0.1:8000

La API debe estar en marcha con APP_ENV=local, por ejemplo:
    python -m uvicorn backend.main:app --reload --port 8010
"""
import argparse
import http.client
import mimetypes
import posixpath
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_PREFIXES = ('backend', 'tests', 'tools', 'migrations', '.git', '.github',
                    '.pytest_cache', '.playwright-mcp', '__pycache__')
HOP_BY_HOP = {'connection', 'keep-alive', 'transfer-encoding', 'content-encoding',
              'content-length', 'host', 'proxy-connection', 'upgrade'}


def parse_api(value: str) -> tuple[str, int, str]:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise SystemExit('La API debe ser una URL http(s), por ejemplo http://127.0.0.1:8010')
    prefix = parsed.path.rstrip('/')
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    return parsed.hostname, port, prefix


class Handler(SimpleHTTPRequestHandler):
    api_target = ('127.0.0.1', 8010, '')
    extensions_map = {**mimetypes.types_map, '.webp': 'image/webp', '.svg': 'image/svg+xml',
                      '.webmanifest': 'application/manifest+json'}

    def _is_blocked(self) -> bool:
        parts = [part for part in posixpath.normpath(self.path.split('?', 1)[0]).split('/') if part]
        return bool(parts) and parts[0] in BLOCKED_PREFIXES

    def _proxy(self) -> None:
        host, port, prefix = self.api_target
        parsed = urllib.parse.urlsplit(self.path)
        target = prefix + parsed.path + (f'?{parsed.query}' if parsed.query else '')
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else None
        headers = {key: value for key, value in self.headers.items()
                   if key.lower() not in HOP_BY_HOP}
        connection = http.client.HTTPConnection(host, port, timeout=120)
        try:
            connection.request(self.command, target, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read()
        except OSError:
            self.send_error(502, 'La API de BeatPass no responde. Arranca uvicorn en el puerto indicado.')
            return
        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in HOP_BY_HOP:
                self.send_header(key, value)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)
        connection.close()

    def _reject_static_write(self) -> None:
        self.send_error(405, 'Solo la API acepta este método; sirve la web con este script para /api.')

    def do_GET(self):
        if self.path.startswith('/api'):
            return self._proxy()
        if self._is_blocked():
            return self.send_error(404)
        return super().do_GET()

    def do_HEAD(self):
        if self.path.startswith('/api'):
            return self._proxy()
        if self._is_blocked():
            return self.send_error(404)
        return super().do_HEAD()

    def do_POST(self):
        return self._proxy() if self.path.startswith('/api') else self._reject_static_write()

    def do_PUT(self):
        return self._proxy() if self.path.startswith('/api') else self._reject_static_write()

    def do_PATCH(self):
        return self._proxy() if self.path.startswith('/api') else self._reject_static_write()

    def do_DELETE(self):
        return self._proxy() if self.path.startswith('/api') else self._reject_static_write()

    def do_OPTIONS(self):
        return self._proxy() if self.path.startswith('/api') else self._reject_static_write()

    def log_message(self, fmt, *args):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description='Sirve BeatPass en local y reenvía /api al backend.')
    parser.add_argument('--port', type=int, default=8080, help='puerto de la web (por defecto 8080)')
    parser.add_argument('--host', default='127.0.0.1', help='interfaz de escucha (por defecto 127.0.0.1)')
    parser.add_argument('--api', default='http://127.0.0.1:8010', help='URL base de la API')
    options = parser.parse_args()
    Handler.api_target = parse_api(options.api)
    server = ThreadingHTTPServer((options.host, options.port), partial(Handler, directory=str(ROOT)))
    print(f'BeatPass en http://{options.host}:{options.port}/index.html  (API -> {options.api})')
    print('Detén el servidor con Ctrl+C.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
