"""Adaptador Flask para o sistema Bomfim & Lacerda.

A lógica de rotas, banco, HTML e permissões permanece centralizada em app.py.
Este módulo apenas traduz o ciclo de requisição Flask para a interface usada
pelo Handler existente, preservando URLs, respostas, cookies e segurança.
"""
from __future__ import annotations

import mimetypes
import traceback
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, Response, request

import app


class FlaskHandler(app.Handler):
    """Facade de requisição/resposta sobre o Handler original."""

    def __init__(self):
        self._response = None
        self.path = request.full_path[:-1] if request.full_path.endswith('?') else request.full_path
        self.command = 'GET' if request.method == 'HEAD' else request.method
        self.headers = request.headers
        self.client_address = (request.remote_addr or '127.0.0.1', 0)
        self.server = None
        self.close_connection = True

    def read_post(self):
        length = request.content_length or 0
        if length > app.MAX_BODY:
            raise app.ValidationError('Arquivo ou formulário muito grande (limite: 12 MB).')
        fields = {key: value for key, value in request.form.items()}
        files = {}
        for key, storage in request.files.items():
            files[key] = (storage.filename or '', storage.read(), storage.mimetype or 'application/octet-stream')
        return fields, files

    def send(self, body, status=200, ctype='text/html; charset=utf-8', headers=None, cache=None):
        if self._response is not None:
            return
        if isinstance(body, str):
            body = body.encode()
        response_headers = app.security_headers()
        response_headers.update({'Content-Type': ctype, 'Content-Length': str(len(body)), 'Cache-Control': cache or 'no-store'})
        if self.is_https():
            response_headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        if headers:
            response_headers.update(headers)
        self._response = (body, status, response_headers)

    def send_file(self, path, ctype, download=None, cache=None):
        try:
            path = Path(path)
            stat = path.stat()
        except OSError:
            return self.send('Não encontrado', 404)
        etag = '"' + format(stat.st_mtime_ns, 'x') + '-' + format(stat.st_size, 'x') + '"'
        if self.headers.get('If-None-Match') == etag:
            return self.send(b'', 304, ctype=ctype, headers={'ETag': etag}, cache=cache)
        headers = {'ETag': etag}
        if download:
            headers['Content-Disposition'] = app.content_disposition(download)
        try:
            body = path.read_bytes()
        except OSError:
            return self.send('Não encontrado', 404)
        self.send(body, ctype=ctype, headers=headers, cache=cache)


flask_app = Flask(__name__, static_folder=None)
flask_app.config['MAX_CONTENT_LENGTH'] = app.MAX_BODY


@flask_app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'HEAD'])
@flask_app.route('/<path:path>', methods=['GET', 'POST', 'HEAD'])
def dispatch(path):
    handler = FlaskHandler()
    try:
        if request.method == 'POST':
            handler.do_POST()
        else:
            handler.do_GET()
        if handler._response is None:
            handler.send('Erro interno', 500)
    except Exception:
        traceback.print_exc()
        if handler._response is None:
            handler.send('Erro interno', 500)
    body, status, headers = handler._response
    if request.method == 'HEAD':
        body = b''
    response = Response(body, status=status)
    for key, value in headers.items():
        response.headers[key] = value
    return response


if __name__ == '__main__':
    app.init()
    host = app.os.getenv('HOST', '0.0.0.0')
    port = int(app.os.getenv('PORT', '8080'))
    print(f'AMBIENTE DE TESTES (Flask): http://127.0.0.1:{port}')
    print(f'Acesso na rede local: http://{app.local_network_ip()}:{port}')
    flask_app.run(host=host, port=port, debug=False, use_reloader=False)
