import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse
import uuid

BASE_DIR = tempfile.mkdtemp(prefix='bomfim-lacerda-tests-')
os.environ['APP_DB'] = os.path.join(BASE_DIR, 'app.db')
os.environ['APP_UPLOADS'] = os.path.join(BASE_DIR, 'uploads')
os.environ['SCRYPT_N'] = '16384'
os.environ['COOKIE_SECURE'] = '0'
os.environ['ACCESS_LOG'] = '0'
os.environ['LOGIN_IP_LIMIT'] = '1000'
os.environ['LOGIN_EMAIL_LIMIT'] = '1000'
os.environ['CONTACT_LIMIT'] = '1000'
os.environ['REGISTER_LIMIT'] = '1000'
os.environ['SESSION_IDLE'] = '1800'
os.environ['SESSION_TTL'] = '43200'

import app


def unique_email(prefix):
    return prefix + '.' + uuid.uuid4().hex[:10] + '@example.test'


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.init()
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        shutil.rmtree(BASE_DIR, ignore_errors=True)

    def request(self, method, path, body=None, headers=None, cookie=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        request_headers = dict(headers or {})
        if cookie is not None:
            request_headers['Cookie'] = cookie if '=' in cookie else 'sid=' + cookie
        payload = body.encode() if isinstance(body, str) else body
        if payload is not None:
            request_headers.setdefault('Content-Type', 'application/x-www-form-urlencoded')
            request_headers['Content-Length'] = str(len(payload))
        connection.request(method, path, body=payload, headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        result = (response.status, dict(response.getheaders()), data)
        connection.close()
        return result

    def cookie(self, headers, name='sid'):
        match = re.search(name + r'=([^;]*)', headers.get('Set-Cookie', ''))
        return match.group(1) if match else None

    def add_user(self, name, password='SenhaSegura123', role='client', email=None, active=1, is_super=None):
        email = email or unique_email(name.lower().replace(' ', '.'))
        if is_super is None:
            is_super = 1 if role == 'admin' else 0
        with app.db() as connection:
            cursor = connection.execute('INSERT INTO users(name,email,password,role,active,is_super) VALUES(?,?,?,?,?,?)', (name, email, app.pwd(password), role, active, is_super))
            user_id = cursor.lastrowid
        return user_id, email

    def add_document(self, client_id, filename='nota.txt', data=b'conteudo', case_id=None, uploaded_by=None, source='escritório'):
        stored = uuid.uuid4().hex + '.txt'
        (app.UP / stored).write_bytes(data)
        with app.db() as connection:
            cursor = connection.execute('INSERT INTO documents(client_id,case_id,filename,stored,mime,size,source,uploaded_by) VALUES(?,?,?,?,?,?,?,?)', (client_id, case_id, filename, stored, 'text/plain', len(data), source, uploaded_by))
            return cursor.lastrowid

    def login(self, email, password):
        body = urllib.parse.urlencode({'email': email, 'password': password})
        status, headers, data = self.request('POST', '/entrar', body)
        return status, headers, data, self.cookie(headers)

    def csrf(self, path, cookie=None):
        status, headers, data = self.request('GET', path, cookie=cookie)
        match = re.search(rb'name="csrf" value="([^"]*)"', data)
        if not match:
            match = re.search(rb'<meta name="csrf-token" content="([^"]*)"', data)
        return status, data, (match.group(1).decode() if match else None)

    def multipart(self, fields, filename, data, content_type='application/octet-stream', field='file'):
        boundary = '----bomfim' + uuid.uuid4().hex
        chunks = []
        for key, value in fields.items():
            chunks.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="' + key + '"\r\n\r\n' + str(value) + '\r\n').encode())
        chunks.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="' + field + '"; filename="' + filename + '"\r\nContent-Type: ' + content_type + '\r\n\r\n').encode())
        chunks.append(data)
        chunks.append(('\r\n--' + boundary + '--\r\n').encode())
        return b''.join(chunks), {'Content-Type': 'multipart/form-data; boundary=' + boundary}

    def test_public_pages_and_security_headers(self):
        for path in ['/', '/escritorio', '/equipe', '/areas', '/conteudos', '/faq', '/contato', '/privacidade', '/termos', '/entrar']:
            status, headers, data = self.request('GET', path)
            self.assertEqual(status, 200, path)
            self.assertIn('X-Content-Type-Options', headers)
            self.assertIn('Content-Security-Policy', headers)
        status, headers, data = self.request('GET', '/')
        self.assertNotIn('Python', headers.get('Server', ''))
        self.assertIn(b'Pular para o conte', data)

    def test_static_cache_robots_sitemap_and_traversal(self):
        status, headers, data = self.request('GET', '/static/style.css')
        self.assertEqual(status, 200)
        self.assertIn('max-age', headers.get('Cache-Control', ''))
        self.assertEqual(self.request('GET', '/static/../app.py')[0], 404)
        status, headers, data = self.request('GET', '/robots.txt')
        self.assertEqual(status, 200)
        self.assertIn(b'Disallow: /admin', data)
        status, headers, data = self.request('GET', '/sitemap.xml')
        self.assertEqual(status, 200)
        self.assertIn(b'<urlset', data)

    def test_authentication_required(self):
        self.assertEqual(self.request('GET', '/admin')[0], 403)
        self.assertEqual(self.request('GET', '/cliente')[0], 403)
        self.assertEqual(self.request('GET', '/arquivo/1')[0], 403)
        self.assertEqual(self.request('GET', '/senha')[0], 303)

    def test_login_csrf_and_content_creation(self):
        _, email = self.add_user('Admin do Teste', role='admin')
        status, headers, data, cookie = self.login(email, 'SenhaSegura123')
        self.assertEqual(status, 303)
        self.assertIsNotNone(cookie)
        status, data = self.request('GET', '/admin', cookie=cookie)[0::2]
        self.assertEqual(status, 200)
        self.assertIn('Gestão do escritório'.encode(), data)
        self.assertNotIn(b'\x00csrf', data)
        body = urllib.parse.urlencode({'title': 'Sem CSRF', 'category': 'Teste', 'body': 'x'})
        self.assertEqual(self.request('POST', '/admin/post', body, cookie=cookie)[0], 403)
        _, _, token = self.csrf('/admin', cookie)
        self.assertTrue(token)
        title = 'Conteudo ' + uuid.uuid4().hex[:8]
        body = urllib.parse.urlencode({'csrf': token, 'title': title, 'category': 'Teste', 'body': 'Texto de teste', 'published': '1'})
        self.assertEqual(self.request('POST', '/admin/post', body, cookie=cookie)[0], 303)
        status, headers, data = self.request('GET', '/conteudos')
        self.assertEqual(status, 200)
        self.assertIn(title.encode(), data)

    def test_upload_validation_quota_and_isolation(self):
        _, email1 = self.add_user('Cliente Um')
        client1, _ = self.add_user('Cliente Dois')
        _, _, _, cookie = self.login(email1, 'SenhaSegura123')
        document2 = self.add_document(client1, 'segredo.txt', b'segredo')
        self.assertEqual(self.request('GET', '/arquivo/' + str(document2), cookie=cookie)[0], 403)
        _, _, token = self.csrf('/cliente', cookie)
        body, headers = self.multipart({'csrf': token}, 'falso.pdf', b'nao e pdf')
        self.assertEqual(self.request('POST', '/cliente/documento', body, headers, cookie)[0], 403)
        body, headers = self.multipart({'csrf': token}, 'nota.txt', b'ola mundo')
        self.assertEqual(self.request('POST', '/cliente/documento', body, headers, cookie)[0], 303)
        with app.db() as connection:
            row = connection.execute('SELECT * FROM documents WHERE filename=?', ('nota.txt',)).fetchone()
        self.assertIsNotNone(row)
        status, headers, data = self.request('GET', '/arquivo/' + str(row['id']), cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(data, b'ola mundo')
        self.assertIn('attachment', headers.get('Content-Disposition', ''))

    def test_contact_csrf_rate_limit_and_honeypot(self):
        status, data, token = self.csrf('/contato')
        self.assertEqual(status, 200)
        self.assertTrue(token)
        self.assertNotIn(b'\x00csrf', data)
        with app.db() as connection:
            before = connection.execute('SELECT COUNT(*) FROM contacts').fetchone()[0]
        origin = 'http://127.0.0.1:' + str(self.port)
        body = urllib.parse.urlencode({'csrf': 'invalido', 'name': 'Ana', 'email': 'ana@example.test', 'message': 'Oi', 'consent': '1'})
        self.assertEqual(self.request('POST', '/contato', body, {'Origin': origin})[0], 403)
        body = urllib.parse.urlencode({'csrf': token, 'name': 'Ana', 'email': 'ana@example.test', 'message': 'Oi', 'consent': '1'})
        self.assertEqual(self.request('POST', '/contato', body, {'Origin': origin})[0], 200)
        honeypot = urllib.parse.urlencode({'csrf': token, 'name': 'Bot', 'email': 'bot@example.test', 'message': 'spam', 'consent': '1', 'website': 'preenchido'})
        self.assertEqual(self.request('POST', '/contato', honeypot, {'Origin': origin})[0], 200)
        with app.db() as connection:
            after = connection.execute('SELECT COUNT(*) FROM contacts').fetchone()[0]
        self.assertEqual(after, before + 1)

    def test_password_reset_and_must_change(self):
        _, admin_email = self.add_user('Admin Reset', role='admin')
        client_id, client_email = self.add_user('Cliente Reset', password='SenhaInicial123')
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin', admin_cookie)
        body = urllib.parse.urlencode({'csrf': token, 'user_id': client_id, 'password': 'SenhaTemporaria123'})
        self.assertEqual(self.request('POST', '/admin/reset', body, cookie=admin_cookie)[0], 303)
        self.assertEqual(self.login(client_email, 'SenhaInicial123')[0], 401)
        status, headers, data, client_cookie = self.login(client_email, 'SenhaTemporaria123')
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/senha')
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/senha')
        _, _, token = self.csrf('/senha', client_cookie)
        body = urllib.parse.urlencode({'csrf': token, 'current': 'errada', 'new': 'OutraSenha12345', 'confirm': 'OutraSenha12345'})
        self.assertEqual(self.request('POST', '/senha', body, cookie=client_cookie)[0], 400)
        body = urllib.parse.urlencode({'csrf': token, 'current': 'SenhaTemporaria123', 'new': 'OutraSenha12345', 'confirm': 'OutraSenha12345'})
        self.assertEqual(self.request('POST', '/senha', body, cookie=client_cookie)[0], 303)
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Olá'.encode(), data)

    def test_staff_scope_and_permissions(self):
        staff_id, staff_email = self.add_user('Funcionario Escopo', role='staff')
        client_a, _ = self.add_user('Cliente Alfa')
        client_b, _ = self.add_user('Cliente Beta')
        with app.db() as connection:
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (staff_id, client_a))
        document_a = self.add_document(client_a, 'alfa.txt', b'alfa')
        document_b = self.add_document(client_b, 'beta.txt', b'beta')
        _, _, _, cookie = self.login(staff_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Painel do advogado'.encode(), data)
        self.assertIn(b'Cliente Alfa', self.request('GET', '/admin/clientes?q=Cliente+Alfa', cookie=cookie)[2])
        self.assertEqual(self.request('GET', '/arquivo/' + str(document_a), cookie=cookie)[0], 200)
        self.assertEqual(self.request('GET', '/arquivo/' + str(document_b), cookie=cookie)[0], 403)
        self.assertEqual(self.request('GET', '/admin/auditoria', cookie=cookie)[0], 403)
        _, _, token = self.csrf('/admin', cookie)
        body = urllib.parse.urlencode({'csrf': token, 'client_id': client_b, 'title': 'Tentativa', 'body': 'x'})
        self.assertEqual(self.request('POST', '/admin/update', body, cookie=cookie)[0], 403)
        body = urllib.parse.urlencode({'csrf': token, 'client_id': client_a, 'title': 'Permitido', 'body': 'x'})
        self.assertEqual(self.request('POST', '/admin/update', body, cookie=cookie)[0], 303)
        body = urllib.parse.urlencode({'csrf': token, 'user_id': client_a, 'password': 'SenhaTemporaria123'})
        self.assertEqual(self.request('POST', '/admin/reset', body, cookie=cookie)[0], 403)

    def test_employee_panel_is_scoped_and_blocks_reports(self):
        employee_id, email = self.add_user('Funcionario Operacional', role='staff')
        client_id, _ = self.add_user('Cliente Funcionario')
        other_client, _ = self.add_user('Cliente Fora Escopo')
        with app.db() as connection:
            connection.execute("UPDATE users SET staff_kind='employee' WHERE id=?", (employee_id,))
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (employee_id, client_id))
            own_case = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Caso do funcionario', employee_id)).lastrowid
            other_case = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (other_client, 'Caso fora do escopo', None)).lastrowid
            own_conversation = connection.execute('INSERT INTO conversations(client_id,case_id,title,visibility,created_by) VALUES(?,?,?,?,?)', (client_id, own_case, 'Conversa do funcionario', 'client', employee_id)).lastrowid
            other_conversation = connection.execute('INSERT INTO conversations(client_id,case_id,title,visibility,created_by) VALUES(?,?,?,?,?)', (other_client, other_case, 'Conversa fora do escopo', 'client', employee_id)).lastrowid
            connection.execute("INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,body) VALUES(?,?,?,?,?,?,?)", (client_id, own_case, own_conversation, client_id, 'client', 'client', 'Mensagem do caso atribuído'))
            connection.execute("INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,body) VALUES(?,?,?,?,?,?,?)", (other_client, other_case, other_conversation, other_client, 'client', 'client', 'Mensagem fora do escopo'))
        _, _, _, cookie = self.login(email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/admin', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Painel do funcionário'.encode(), data)
        self.assertIn(b'Conversa do funcionario', data)
        self.assertNotIn(b'Conversa fora do escopo', data)
        self.assertNotIn(b'/admin/relatorios', data)
        status, _, cases_page = self.request('GET', '/admin/casos', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'Caso do funcionario', cases_page)
        self.assertNotIn(b'Caso fora do escopo', cases_page)
        self.assertEqual(self.request('GET', '/admin/relatorios', cookie=cookie)[0], 403)
        self.assertEqual(self.request('GET', '/admin/caso/historico?case_id=' + str(own_case), cookie=cookie)[0], 200)
        self.assertEqual(self.request('GET', '/admin/caso/historico?case_id=' + str(other_case), cookie=cookie)[0], 403)

    def test_admin_paginated_pages(self):
        _, email = self.add_user('Admin Paginas', role='admin')
        _, _, _, cookie = self.login(email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/auditoria?page=1', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'Auditoria', data)
        status, headers, data = self.request('GET', '/admin/auditoria?page=999', cookie=cookie)
        self.assertEqual(status, 200)
        status, headers, data = self.request('GET', '/admin/contatos?page=1', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Mensagens de contato'.encode(), data)

    def test_client_registration_messages_and_notifications(self):
        status, data, token = self.csrf('/cadastro')
        self.assertEqual(status, 200)
        self.assertIn('Criar conta'.encode(), data)
        email = unique_email('cliente.registro')
        origin = 'http://127.0.0.1:' + str(self.port)
        body = urllib.parse.urlencode({'csrf': token, 'name': 'Cliente Registro', 'email': email, 'password': 'SenhaRegistro123', 'confirm': 'SenhaRegistro123', 'consent': '1'})
        status, headers, data = self.request('POST', '/cadastro', body, {'Origin': origin})
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/cliente')
        cookie = self.cookie(headers)
        self.assertIsNotNone(cookie)
        status, headers, data = self.request('GET', '/cliente', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Conversas recentes'.encode(), data)
        self.assertIn('Mensagens não lidas'.encode(), data)
        _, _, client_csrf = self.csrf('/cliente', cookie)
        body = urllib.parse.urlencode({'csrf': client_csrf, 'body': 'Gostaria de informações sobre o processo.'})
        self.assertEqual(self.request('POST', '/cliente/mensagem', body, cookie=cookie)[0], 303)
        body = urllib.parse.urlencode({'csrf': token, 'name': 'Outro Cliente', 'email': email, 'password': 'SenhaRegistro123', 'confirm': 'SenhaRegistro123', 'consent': '1'})
        self.assertEqual(self.request('POST', '/cadastro', body, {'Origin': origin})[0], 400)
        body = urllib.parse.urlencode({'csrf': token, 'name': 'Senha Fraca', 'email': unique_email('senha.fraca'), 'password': '123', 'confirm': '123', 'consent': '1'})
        self.assertEqual(self.request('POST', '/cadastro', body, {'Origin': origin})[0], 400)
        body = urllib.parse.urlencode({'csrf': token, 'name': 'Sem Consentimento', 'email': unique_email('sem.consentimento'), 'password': 'SenhaRegistro123', 'confirm': 'SenhaRegistro123'})
        self.assertEqual(self.request('POST', '/cadastro', body, {'Origin': origin})[0], 400)
        body = urllib.parse.urlencode({'name': 'Sem CSRF', 'email': unique_email('sem.csrf'), 'password': 'SenhaRegistro123', 'confirm': 'SenhaRegistro123', 'consent': '1'})
        self.assertEqual(self.request('POST', '/cadastro', body, {'Origin': origin})[0], 403)
        _, admin_email = self.add_user('Admin Mensagens', role='admin')
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/mensagens', cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Cliente Registro'.encode(), data)
        self.assertIn('Gostaria de informações sobre o processo.'.encode(), data)
        _, _, admin_csrf = self.csrf('/admin/mensagens', admin_cookie)
        with app.db() as connection:
            client_id = connection.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
        body = urllib.parse.urlencode({'csrf': admin_csrf, 'client_id': client_id, 'body': 'Recebemos sua mensagem e retornaremos em breve.'})
        self.assertEqual(self.request('POST', '/admin/mensagem', body, cookie=admin_cookie)[0], 303)
        status, headers, data = self.request('GET', '/cliente', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Recebemos sua mensagem e retornaremos em breve.'.encode(), data)
        self.assertIn(b'data-unread-count>1</span>', data)

    def test_super_admin_management_and_audit(self):
        super_id, super_email = self.add_user('Super Admin Teste', role='admin')
        regular_id, regular_email = self.add_user('Admin Operacional', role='admin', is_super=0)
        target_id, target_email = self.add_user('Usuario Editavel', role='staff')
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/usuarios', cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Usuários'.encode(), data)
        _, _, csrf_token = self.csrf('/admin/usuarios', super_cookie)
        new_email = unique_email('editado')
        body = urllib.parse.urlencode({'csrf': csrf_token, 'user_id': target_id, 'name': 'Usuario Editado', 'email': new_email, 'role': 'staff', 'active': '1'})
        self.assertEqual(self.request('POST', '/admin/user/edit', body, cookie=super_cookie)[0], 303)
        with app.db() as connection:
            row = connection.execute('SELECT * FROM users WHERE id=?', (target_id,)).fetchone()
            audit_row = connection.execute("SELECT * FROM audit WHERE entity='user' AND action='editar usuário' ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(row['name'], 'Usuario Editado')
        self.assertEqual(row['email'], new_email)
        self.assertIsNotNone(audit_row)
        self.assertTrue(audit_row['before'])
        self.assertTrue(audit_row['after'])
        body = urllib.parse.urlencode({'csrf': csrf_token, 'user_id': super_id, 'name': 'Super Admin Teste', 'email': super_email, 'role': 'admin', 'is_super': '1'})
        self.assertEqual(self.request('POST', '/admin/user/edit', body, cookie=super_cookie)[0], 400)
        _, _, _, regular_cookie = self.login(regular_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/admin/usuarios', cookie=regular_cookie)[0], 403)
        self.assertEqual(self.request('GET', '/admin/auditoria', cookie=regular_cookie)[0], 403)
        self.assertEqual(self.request('GET', '/admin', cookie=regular_cookie)[0], 200)

    def test_cases_and_internal_reports_identity(self):
        staff_id, staff_email = self.add_user('Advogado Caso', role='staff')
        client_id, client_email = self.add_user('Cliente Caso')
        other_client_id, _ = self.add_user('Cliente Fora')
        with app.db() as connection:
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (staff_id, client_id))
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        _, _, csrf_token = self.csrf('/admin/casos', staff_cookie)
        case_title = 'Caso Teste ' + uuid.uuid4().hex[:6]
        body = urllib.parse.urlencode({'csrf': csrf_token, 'client_id': client_id, 'title': case_title, 'case_number': '0001234-56.2026', 'area': 'Direito Civil', 'status': 'Em andamento', 'description': 'Descrição do caso de teste.', 'responsible_id': staff_id})
        self.assertEqual(self.request('POST', '/admin/caso', body, cookie=staff_cookie)[0], 303)
        with app.db() as connection:
            case_row = connection.execute('SELECT * FROM cases WHERE title=?', (case_title,)).fetchone()
        self.assertIsNotNone(case_row)
        case_id = case_row['id']
        self.assertEqual(case_row['responsible_id'], staff_id)
        body = urllib.parse.urlencode({'csrf': csrf_token, 'client_id': other_client_id, 'title': 'Caso Proibido', 'status': 'Em andamento'})
        self.assertEqual(self.request('POST', '/admin/caso', body, cookie=staff_cookie)[0], 403)
        body = urllib.parse.urlencode({'csrf': csrf_token, 'case_id': case_id, 'title': case_title, 'case_number': '0001234-56.2026', 'area': 'Direito Civil', 'status': 'Aguardando cliente', 'description': 'Atualizado.', 'responsible_id': staff_id})
        self.assertEqual(self.request('POST', '/admin/caso/editar', body, cookie=staff_cookie)[0], 303)
        with app.db() as connection:
            updated = connection.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
            case_audit = connection.execute("SELECT * FROM audit WHERE entity='case' AND action='editar caso' ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(updated['status'], 'Aguardando cliente')
        self.assertIsNotNone(case_audit)
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertIn(case_title.encode(), data)
        _, _, staff_csrf = self.csrf('/admin/mensagens', staff_cookie)
        internal_body = 'Relato interno ' + uuid.uuid4().hex[:8]
        body = urllib.parse.urlencode({'csrf': staff_csrf, 'client_id': client_id, 'case_id': case_id, 'visibility': 'internal', 'body': internal_body})
        self.assertEqual(self.request('POST', '/admin/mensagem', body, cookie=staff_cookie)[0], 303)
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertNotIn(internal_body.encode(), data)
        super_email = unique_email('super.caso')
        self.add_user('Super Caso', role='admin', email=super_email)
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/mensagens', cookie=super_cookie)
        self.assertIn(internal_body.encode(), data)
        _, _, super_csrf = self.csrf('/admin/mensagens', super_cookie)
        visible_body = 'Mensagem visível ' + uuid.uuid4().hex[:8]
        body = urllib.parse.urlencode({'csrf': super_csrf, 'client_id': client_id, 'case_id': case_id, 'visibility': 'client', 'body': visible_body})
        self.assertEqual(self.request('POST', '/admin/mensagem', body, cookie=super_cookie)[0], 303)
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertIn(visible_body.encode(), data)
        with app.db() as connection:
            visible_conversation = connection.execute('SELECT conversation_id FROM messages WHERE body=?', (visible_body,)).fetchone()[0]
        self.assertIn('Suporte do escritório'.encode(), self.request('GET', '/conversas/' + str(visible_conversation), cookie=client_cookie)[2])
        revealed_body = 'Mensagem identificada ' + uuid.uuid4().hex[:8]
        body = urllib.parse.urlencode({'csrf': super_csrf, 'client_id': client_id, 'case_id': case_id, 'visibility': 'client', 'reveal_identity': '1', 'body': revealed_body})
        self.assertEqual(self.request('POST', '/admin/mensagem', body, cookie=super_cookie)[0], 303)
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertIn(revealed_body.encode(), data)
        with app.db() as connection:
            revealed_conversation = connection.execute('SELECT conversation_id FROM messages WHERE body=?', (revealed_body,)).fetchone()[0]
        self.assertIn('Super Caso'.encode(), self.request('GET', '/conversas/' + str(revealed_conversation), cookie=client_cookie)[2])

    def test_case_file_access_isolation(self):
        staff_id, staff_email = self.add_user('Advogado Arquivo', role='staff')
        client_a, _ = self.add_user('Cliente Arquivo A')
        client_b, _ = self.add_user('Cliente Arquivo B')
        with app.db() as connection:
            case_a = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_a, 'Caso A', staff_id)).lastrowid
            case_b = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_b, 'Caso B', None)).lastrowid
        doc_a = self.add_document(client_a, 'arquivo-a.txt', b'arquivo a', case_id=case_a, uploaded_by=staff_id)
        doc_b = self.add_document(client_b, 'arquivo-b.txt', b'arquivo b', case_id=case_b, uploaded_by=None)
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/arquivos', cookie=staff_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'arquivo-a.txt', data)
        self.assertIn(b'arquivo-b.txt', data)
        self.assertEqual(self.request('GET', '/arquivo/' + str(doc_a), cookie=staff_cookie)[0], 200)
        self.assertEqual(self.request('GET', '/arquivo/' + str(doc_b), cookie=staff_cookie)[0], 200)
        super_email = unique_email('super.arquivo')
        self.add_user('Super Arquivo', role='admin', email=super_email)
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/arquivos', cookie=super_cookie)
        self.assertIn(b'arquivo-a.txt', data)
        self.assertIn(b'arquivo-b.txt', data)
        status, headers, data = self.request('GET', '/admin/arquivos?client_id=' + str(client_b), cookie=super_cookie)
        self.assertIn(b'arquivo-b.txt', data)
        self.assertNotIn(b'arquivo-a.txt', data)

    def test_staff_client_ownership_permissions_and_settings(self):
        super_id, super_email = self.add_user('Super Etapa Um', role='admin')
        staff1_id, staff1_email = self.add_user('Advogado Um', role='staff')
        staff2_id, staff2_email = self.add_user('Advogado Dois', role='staff')
        _, _, _, staff1_cookie = self.login(staff1_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/clientes?q=Cliente+do+Advogado', cookie=staff1_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Cadastrar cliente'.encode(), data)
        _, _, staff1_csrf = self.csrf('/admin/clientes', staff1_cookie)
        client_email = unique_email('cliente.advogado')
        body = urllib.parse.urlencode({'csrf': staff1_csrf, 'name': 'Cliente do Advogado', 'email': client_email, 'phone': '(88) 99999-0000', 'password': 'SenhaCliente123', 'confirm': 'SenhaCliente123'})
        self.assertEqual(self.request('POST', '/admin/cliente', body, cookie=staff1_cookie)[0], 303)
        with app.db() as connection:
            client_row = connection.execute('SELECT * FROM users WHERE email=?', (client_email,)).fetchone()
            assignment = connection.execute('SELECT * FROM assignments WHERE client_id=? AND staff_id=?', (client_row['id'], staff1_id)).fetchone()
        self.assertIsNotNone(client_row)
        self.assertEqual(client_row['role'], 'client')
        self.assertEqual(client_row['owner_staff_id'], staff1_id)
        self.assertEqual(client_row['created_by'], staff1_id)
        self.assertIsNotNone(assignment)
        client_id = client_row['id']
        status, headers, data = self.request('GET', '/admin/clientes?q=Cliente+do+Advogado', cookie=staff1_cookie)
        self.assertIn(b'Cliente do Advogado', data)
        _, _, _, staff2_login_cookie = self.login(staff2_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/clientes?q=Cliente+do+Advogado', cookie=staff2_login_cookie)
        self.assertIn(b'Cliente do Advogado', data)
        _, _, staff2_csrf = self.csrf('/admin/clientes', staff2_login_cookie)
        body = urllib.parse.urlencode({'csrf': staff2_csrf, 'client_id': client_id, 'name': 'Invasao', 'phone': '', 'active': '1'})
        self.assertEqual(self.request('POST', '/admin/cliente/editar', body, cookie=staff2_login_cookie)[0], 403)
        body = urllib.parse.urlencode({'csrf': staff1_csrf, 'client_id': client_id, 'name': 'Cliente Editado', 'phone': '(88) 98888-1111', 'active': '1'})
        self.assertEqual(self.request('POST', '/admin/cliente/editar', body, cookie=staff1_cookie)[0], 303)
        with app.db() as connection:
            edited = connection.execute('SELECT * FROM users WHERE id=?', (client_id,)).fetchone()
        self.assertEqual(edited['name'], 'Cliente Editado')
        self.assertEqual(edited['phone'], '(88) 98888-1111')
        status, headers, data, client_cookie = self.login(client_email, 'SenhaCliente123')
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/senha')
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/admin/permissoes', cookie=staff1_cookie)[0], 403)
        status, headers, data = self.request('GET', '/admin/permissoes', cookie=super_cookie)
        self.assertEqual(status, 200)
        _, _, permissions_csrf = self.csrf('/admin/permissoes', super_cookie)
        body = urllib.parse.urlencode({'csrf': permissions_csrf, 'user_id': staff1_id, 'manage_cases': '1', 'send_messages': '1', 'manage_documents': '1'})
        self.assertEqual(self.request('POST', '/admin/permissoes', body, cookie=super_cookie)[0], 303)
        _, _, _, staff1_cookie = self.login(staff1_email, 'SenhaSegura123')
        _, _, staff1_csrf = self.csrf('/admin/clientes', staff1_cookie)
        body = urllib.parse.urlencode({'csrf': staff1_csrf, 'name': 'Cliente Negado', 'email': unique_email('negado'), 'phone': '', 'password': 'SenhaCliente123', 'confirm': 'SenhaCliente123'})
        self.assertEqual(self.request('POST', '/admin/cliente', body, cookie=staff1_cookie)[0], 403)
        self.assertEqual(self.request('GET', '/admin/configuracoes', cookie=staff1_cookie)[0], 403)
        status, headers, data = self.request('GET', '/admin/configuracoes', cookie=super_cookie)
        self.assertEqual(status, 200)
        _, _, settings_csrf = self.csrf('/admin/configuracoes', super_cookie)
        body = urllib.parse.urlencode({'csrf': settings_csrf, 'unread_hours': '24', 'stale_hours': '48', 'appointment_reminder_hours': '12', 'email_notifications': '1'})
        self.assertEqual(self.request('POST', '/admin/configuracoes', body, cookie=super_cookie)[0], 303)
        with app.db() as connection:
            reminder = connection.execute("SELECT value FROM settings WHERE key='appointment_reminder_hours'").fetchone()[0]
            email_notifications = connection.execute("SELECT value FROM settings WHERE key='email_notifications'").fetchone()[0]
        self.assertEqual(reminder, '12')
        self.assertEqual(email_notifications, '1')
        new_email = unique_email('cliente.admin')
        body = urllib.parse.urlencode({'csrf': permissions_csrf, 'client_id': client_id, 'name': 'Cliente Editado', 'email': new_email, 'phone': '(88) 98888-1111', 'active': '1', 'owner_staff_id': staff1_id})
        self.assertEqual(self.request('POST', '/admin/cliente/editar', body, cookie=super_cookie)[0], 303)
        with app.db() as connection:
            final_client = connection.execute('SELECT * FROM users WHERE id=?', (client_id,)).fetchone()
        self.assertEqual(final_client['email'], new_email)
        self.assertEqual(app.schema_version(), app.SCHEMA_VERSION)

    def test_status_colors_notifications_and_alerts(self):
        super_id, super_email = self.add_user('Super Alerta', role='admin')
        staff_id, staff_email = self.add_user('Advogado Alerta', role='staff')
        client_id, client_email = self.add_user('Cliente Alerta')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title,status,responsible_id,last_activity_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)', (client_id, 'Caso Alerta', 'Em andamento', staff_id)).lastrowid
            connection.execute('INSERT INTO case_assignments(case_id,staff_id) VALUES(?,?)', (case_id, staff_id))
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (staff_id, client_id))
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        _, _, client_csrf = self.csrf('/cliente', client_cookie)
        body = urllib.parse.urlencode({'csrf': client_csrf, 'case_id': case_id, 'body': 'Mensagem para alerta.'})
        self.assertEqual(self.request('POST', '/cliente/mensagem', body, cookie=client_cookie)[0], 303)
        with app.db() as connection:
            staff_notifications = connection.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND type='message'", (staff_id,)).fetchone()[0]
            super_notifications = connection.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND type='message'", (super_id,)).fetchone()[0]
        self.assertGreaterEqual(staff_notifications, 1)
        self.assertGreaterEqual(super_notifications, 1)
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/notificacoes', cookie=staff_cookie)
        payload = json.loads(data.decode('utf-8'))
        self.assertEqual(status, 200)
        self.assertGreaterEqual(payload['unread'], 1)
        self.assertTrue(any('mensagem' in item['title'].lower() for item in payload['items']))
        _, _, staff_csrf = self.csrf('/admin', staff_cookie)
        body = urllib.parse.urlencode({'csrf': staff_csrf, 'all': '1'})
        self.assertEqual(self.request('POST', '/notificacoes/ler', body, cookie=staff_cookie)[0], 200)
        status, headers, data = self.request('GET', '/notificacoes', cookie=staff_cookie)
        self.assertEqual(json.loads(data.decode('utf-8'))['unread'], 0)
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        _, _, super_csrf = self.csrf('/admin', super_cookie)
        body = urllib.parse.urlencode({'csrf': super_csrf, 'client_id': client_id, 'case_id': case_id, 'visibility': 'client', 'body': 'Resposta do escritório para o cliente.'})
        self.assertEqual(self.request('POST', '/admin/mensagem', body, cookie=super_cookie)[0], 303)
        status, headers, data = self.request('GET', '/notificacoes', cookie=client_cookie)
        client_payload = json.loads(data.decode('utf-8'))
        self.assertTrue(any(item['type'] == 'message' for item in client_payload['items']))
        with app.db() as connection:
            connection.execute("UPDATE cases SET status='Em andamento', last_activity_at='2020-01-01 00:00:00' WHERE id=?", (case_id,))
        self.request('GET', '/notificacoes', cookie=super_cookie)
        with app.db() as connection:
            stale_count = connection.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND type='stale_case'", (super_id,)).fetchone()[0]
        self.assertGreaterEqual(stale_count, 1)
        self.request('GET', '/notificacoes', cookie=super_cookie)
        with app.db() as connection:
            stale_count_again = connection.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND type='stale_case'", (super_id,)).fetchone()[0]
        self.assertEqual(stale_count, stale_count_again)
        with app.db() as connection:
            connection.execute("UPDATE cases SET status='Aguardando cliente', last_activity_at='2020-01-01 00:00:00' WHERE id=?", (case_id,))
        self.request('GET', '/notificacoes', cookie=client_cookie)
        with app.db() as connection:
            waiting = connection.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND type='waiting_client'", (client_id,)).fetchone()[0]
        self.assertGreaterEqual(waiting, 1)
        self.assertEqual(app.status_color('Em andamento'), 'yellow')
        self.assertEqual(app.status_color('Aguardando cliente'), 'blue')
        self.assertEqual(app.status_color('Concluído'), 'green')
        self.assertEqual(app.status_color('Informativo'), 'gray')
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertIn(b'status-badge status-blue', data)

    def test_client_new_case_rename_history_and_distribution(self):
        super_id, super_email = self.add_user('Super Caso Novo', role='admin')
        staff_id, staff_email = self.add_user('Advogado Caso Novo', role='staff')
        client_id, client_email = self.add_user('Cliente Caso Novo')
        other_client_id, other_client_email = self.add_user('Cliente Sem Caso')
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Novo atendimento'.encode(), data)
        _, _, client_csrf = self.csrf('/cliente', client_cookie)
        original_subject = 'Revisão de contrato ' + uuid.uuid4().hex[:6]
        description = 'Preciso de orientação sobre um contrato de prestação de serviços.'
        body = urllib.parse.urlencode({'csrf': client_csrf, 'subject': original_subject, 'description': description})
        self.assertEqual(self.request('POST', '/cliente/novo', body, cookie=client_cookie)[0], 303)
        with app.db() as connection:
            case_row = connection.execute('SELECT * FROM cases WHERE title=?', (original_subject,)).fetchone()
            initial_message = connection.execute('SELECT * FROM messages WHERE case_id=?', (case_row['id'],)).fetchone()
            created_event = connection.execute("SELECT * FROM case_events WHERE case_id=? AND event_type='created'", (case_row['id'],)).fetchone()
            admin_notice = connection.execute("SELECT * FROM notifications WHERE user_id=? AND type='case'", (super_id,)).fetchone()
        self.assertIsNotNone(case_row)
        case_id = case_row['id']
        self.assertEqual(case_row['original_title'], original_subject)
        self.assertEqual(case_row['created_by'], client_id)
        self.assertEqual(case_row['source'], 'cliente')
        self.assertIsNone(case_row['responsible_id'])
        self.assertIsNotNone(initial_message)
        self.assertEqual(initial_message['visibility'], 'client')
        self.assertIsNotNone(created_event)
        self.assertIsNotNone(admin_notice)
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/casos', cookie=staff_cookie)
        self.assertIn(original_subject.encode(), data)
        self.assertIn('Consulta disponível'.encode(), data)
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/casos', cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn(original_subject.encode(), data)
        self.assertIn('Sem responsável'.encode(), data)
        _, _, super_csrf = self.csrf('/admin/casos', super_cookie)
        body = urllib.parse.urlencode({'csrf': super_csrf, 'case_id': case_id, 'title': original_subject, 'case_number': '', 'area': '', 'status': 'Em andamento', 'description': description, 'responsible_id': staff_id})
        self.assertEqual(self.request('POST', '/admin/caso/editar', body, cookie=super_cookie)[0], 303)
        with app.db() as connection:
            assigned = connection.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
            assignment_event = connection.execute("SELECT * FROM case_events WHERE case_id=? AND event_type='assignment'", (case_id,)).fetchone()
            staff_notice = connection.execute("SELECT * FROM notifications WHERE user_id=? AND type='case'", (staff_id,)).fetchone()
        self.assertEqual(assigned['responsible_id'], staff_id)
        self.assertIsNotNone(assignment_event)
        self.assertIsNotNone(staff_notice)
        status, headers, data = self.request('GET', '/admin/casos', cookie=staff_cookie)
        self.assertIn(original_subject.encode(), data)
        _, _, staff_csrf = self.csrf('/admin/casos', staff_cookie)
        renamed_title = 'Contrato revisado ' + uuid.uuid4().hex[:6]
        body = urllib.parse.urlencode({'csrf': staff_csrf, 'case_id': case_id, 'title': renamed_title, 'case_number': '', 'area': 'Civil', 'status': 'Aguardando cliente', 'description': description, 'responsible_id': staff_id})
        self.assertEqual(self.request('POST', '/admin/caso/editar', body, cookie=staff_cookie)[0], 303)
        with app.db() as connection:
            renamed = connection.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
            rename_event = connection.execute("SELECT * FROM case_events WHERE case_id=? AND event_type='rename'", (case_id,)).fetchone()
            status_event = connection.execute("SELECT * FROM case_events WHERE case_id=? AND event_type='status'", (case_id,)).fetchone()
        self.assertEqual(renamed['title'], renamed_title)
        self.assertEqual(renamed['original_title'], original_subject)
        self.assertIsNotNone(rename_event)
        self.assertEqual(rename_event['visible_to_client'], 0)
        self.assertIsNotNone(status_event)
        self.assertEqual(status_event['visible_to_client'], 1)
        status, headers, data = self.request('GET', '/admin/caso/historico?case_id=' + str(case_id), cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Título original'.encode(), data)
        self.assertIn('Título alterado'.encode(), data)
        status, headers, data = self.request('GET', '/cliente/atendimento/' + str(case_id), cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertIn(renamed_title.encode(), data)
        self.assertIn(description.encode(), data)
        self.assertNotIn('Título alterado'.encode(), data)
        self.assertNotIn('Responsável alterado'.encode(), data)
        _, _, _, other_cookie = self.login(other_client_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/cliente/atendimento/' + str(case_id), cookie=other_cookie)[0], 403)

    def test_client_space_profile_and_pendencies(self):
        super_id, super_email = self.add_user('Super Pendencia', role='admin')
        staff_id, staff_email = self.add_user('Advogado Pendencia', role='staff')
        client_id, client_email = self.add_user('Cliente Pendencia')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title,status,responsible_id,last_activity_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)', (client_id, 'Caso Pendencia', 'Em andamento', staff_id)).lastrowid
            connection.execute('INSERT INTO case_assignments(case_id,staff_id) VALUES(?,?)', (case_id, staff_id))
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (staff_id, client_id))
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertIn('MEU ESPAÇO'.encode(), data)
        self.assertIn('Novo atendimento'.encode(), data)
        self.assertIn('Conversas recentes'.encode(), data)
        for path in ['/cliente/atendimentos', '/cliente/mensagens', '/cliente/documentos', '/cliente/compromissos', '/cliente/atualizacoes', '/cliente/novo', '/cliente/perfil', '/cliente/pendencias']:
            self.assertEqual(self.request('GET', path, cookie=client_cookie)[0], 200, path)
        _, _, profile_csrf = self.csrf('/cliente/perfil', client_cookie)
        body = urllib.parse.urlencode({'csrf': profile_csrf, 'name': 'Cliente Perfil Editado', 'phone': '(88) 97777-1111'})
        self.assertEqual(self.request('POST', '/cliente/perfil', body, cookie=client_cookie)[0], 303)
        with app.db() as connection:
            profile = connection.execute('SELECT * FROM users WHERE id=?', (client_id,)).fetchone()
        self.assertEqual(profile['name'], 'Cliente Perfil Editado')
        self.assertEqual(profile['phone'], '(88) 97777-1111')
        self.assertEqual(profile['email'], client_email)
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/pendencias', cookie=staff_cookie)
        self.assertEqual(status, 200)
        _, _, staff_csrf = self.csrf('/admin/pendencias', staff_cookie)
        pendency_title = 'Enviar RG ' + uuid.uuid4().hex[:6]
        body = urllib.parse.urlencode({'csrf': staff_csrf, 'client_id': client_id, 'case_id': case_id, 'title': pendency_title, 'description': 'Envie uma cópia legível do documento.', 'due_at': '2026-12-31'})
        self.assertEqual(self.request('POST', '/admin/pendencia', body, cookie=staff_cookie)[0], 303)
        with app.db() as connection:
            pendency = connection.execute('SELECT * FROM pendencies WHERE title=?', (pendency_title,)).fetchone()
            client_notice = connection.execute("SELECT * FROM notifications WHERE user_id=? AND type='pendency'", (client_id,)).fetchone()
        self.assertIsNotNone(pendency)
        self.assertEqual(pendency['status'], 'Aberta')
        self.assertIsNotNone(client_notice)
        status, headers, data = self.request('GET', '/cliente', cookie=client_cookie)
        self.assertIn(pendency_title.encode(), data)
        status, headers, data = self.request('GET', '/cliente/pendencias', cookie=client_cookie)
        self.assertIn(pendency_title.encode(), data)
        self.assertIn('Aberta'.encode(), data)
        _, _, pendency_csrf = self.csrf('/cliente/pendencias', client_cookie)
        upload_body, upload_headers = self.multipart({'csrf': pendency_csrf, 'pendency_id': pendency['id']}, 'rg.txt', b'RG digitalizado')
        self.assertEqual(self.request('POST', '/cliente/documento', upload_body, upload_headers, client_cookie)[0], 303)
        with app.db() as connection:
            received = connection.execute('SELECT * FROM pendencies WHERE id=?', (pendency['id'],)).fetchone()
            uploaded_doc = connection.execute('SELECT * FROM documents WHERE id=?', (received['document_id'],)).fetchone()
            staff_notice = connection.execute("SELECT * FROM notifications WHERE user_id=? AND type='pendency'", (staff_id,)).fetchone()
        self.assertEqual(received['status'], 'Recebida')
        self.assertIsNotNone(uploaded_doc)
        self.assertEqual(uploaded_doc['case_id'], case_id)
        self.assertIsNotNone(staff_notice)
        status, headers, data = self.request('GET', '/admin/pendencias', cookie=staff_cookie)
        self.assertIn(pendency_title.encode(), data)
        _, _, staff_csrf = self.csrf('/admin/pendencias', staff_cookie)
        body = urllib.parse.urlencode({'csrf': staff_csrf, 'pendency_id': pendency['id'], 'status': 'Atendida', 'review_notes': 'Documento aprovado.'})
        self.assertEqual(self.request('POST', '/admin/pendencia/status', body, cookie=staff_cookie)[0], 303)
        with app.db() as connection:
            attended = connection.execute('SELECT * FROM pendencies WHERE id=?', (pendency['id'],)).fetchone()
        self.assertEqual(attended['status'], 'Atendida')
        self.assertEqual(attended['reviewed_by'], staff_id)
        status, headers, data = self.request('GET', '/cliente/pendencias', cookie=client_cookie)
        self.assertIn('Atendida'.encode(), data)
        self.assertIn('Documento aprovado.'.encode(), data)

    def test_document_status_and_appointment_reminders(self):
        super_id, super_email = self.add_user('Super Etapa Seis', role='admin')
        staff_id, staff_email = self.add_user('Advogado Etapa Seis', role='staff')
        client_id, client_email = self.add_user('Cliente Etapa Seis')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title,status,responsible_id,last_activity_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)', (client_id, 'Caso Etapa Seis', 'Em andamento', staff_id)).lastrowid
            connection.execute('INSERT INTO case_assignments(case_id,staff_id) VALUES(?,?)', (case_id, staff_id))
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (staff_id, client_id))
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        _, _, documents_csrf = self.csrf('/cliente/documentos', client_cookie)
        upload_body, upload_headers = self.multipart({'csrf': documents_csrf}, 'documento-cliente.txt', b'conteudo do cliente')
        self.assertEqual(self.request('POST', '/cliente/documento', upload_body, upload_headers, client_cookie)[0], 303)
        with app.db() as connection:
            document = connection.execute('SELECT * FROM documents WHERE client_id=? ORDER BY id DESC LIMIT 1', (client_id,)).fetchone()
        self.assertEqual(document['status'], 'aguardando_analise')
        status, headers, data = self.request('GET', '/cliente/documentos', cookie=client_cookie)
        self.assertIn('Aguardando análise'.encode(), data)
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/documento?doc_id=' + str(document['id']), cookie=staff_cookie)
        self.assertEqual(status, 200)
        _, _, document_csrf = self.csrf('/admin/documento?doc_id=' + str(document['id']), staff_cookie)
        body = urllib.parse.urlencode({'csrf': document_csrf, 'doc_id': document['id'], 'status': 'complementacao', 'analysis_notes': 'Envie o documento complementar.'})
        self.assertEqual(self.request('POST', '/admin/documento/status', body, cookie=staff_cookie)[0], 303)
        with app.db() as connection:
            analysed = connection.execute('SELECT * FROM documents WHERE id=?', (document['id'],)).fetchone()
            document_notice = connection.execute("SELECT * FROM notifications WHERE user_id=? AND type='document' ORDER BY id DESC LIMIT 1", (client_id,)).fetchone()
        self.assertEqual(analysed['status'], 'complementacao')
        self.assertEqual(analysed['reviewed_by'], staff_id)
        self.assertIn('Envie o documento complementar.', analysed['analysis_notes'])
        self.assertIsNotNone(document_notice)
        status, headers, data = self.request('GET', '/cliente/documentos', cookie=client_cookie)
        self.assertIn('Complementação'.encode(), data)
        self.assertIn('Envie o documento complementar.'.encode(), data)
        with app.db() as connection:
            appointment_id = connection.execute("INSERT INTO appointments(client_id,case_id,title,when_at,notes,created_by,status,reminder_at,reminder_sent) VALUES(?,?,?,?,?,?,'pendente','2020-01-01 00:00',0)", (client_id, case_id, 'Audiência de teste', '2030-01-01 10:00', 'Levar documentos', staff_id)).lastrowid
        status, headers, data = self.request('GET', '/notificacoes', cookie=client_cookie)
        payload = json.loads(data.decode('utf-8'))
        self.assertTrue(any(item['title'] == 'Lembrete de compromisso' for item in payload['items']))
        with app.db() as connection:
            reminder_count = connection.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND title='Lembrete de compromisso'", (client_id,)).fetchone()[0]
            reminder_sent = connection.execute('SELECT reminder_sent FROM appointments WHERE id=?', (appointment_id,)).fetchone()[0]
        self.assertGreaterEqual(reminder_count, 1)
        self.assertEqual(reminder_sent, 1)
        self.request('GET', '/notificacoes', cookie=client_cookie)
        with app.db() as connection:
            reminder_count_again = connection.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND title='Lembrete de compromisso'", (client_id,)).fetchone()[0]
        self.assertEqual(reminder_count, reminder_count_again)
        status, headers, data = self.request('GET', '/admin/compromissos', cookie=staff_cookie)
        self.assertIn(b'Pendente', data)
        _, _, appointment_csrf = self.csrf('/admin/compromissos', staff_cookie)
        body = urllib.parse.urlencode({'csrf': appointment_csrf, 'appointment_id': appointment_id, 'status': 'realizado'})
        self.assertEqual(self.request('POST', '/admin/compromisso/status', body, cookie=staff_cookie)[0], 303)
        with app.db() as connection:
            appointment = connection.execute('SELECT * FROM appointments WHERE id=?', (appointment_id,)).fetchone()
        self.assertEqual(appointment['status'], 'realizado')
        status, headers, data = self.request('GET', '/cliente/compromissos', cookie=client_cookie)
        self.assertIn('Realizado'.encode(), data)
        self.assertIn('Audiência de teste'.encode(), data)

    def test_soft_delete_restore_purge_reports_audit_permissions(self):
        super_id, super_email = self.add_user('Super Lixeira', role='admin')
        staff_id, staff_email = self.add_user('Advogado Lixeira', role='staff')
        client_id, client_email = self.add_user('Cliente Lixeira')
        with app.db() as connection:
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (staff_id, client_id))
            cursor = connection.execute("INSERT INTO cases(client_id,title,original_title,status,description,responsible_id,created_by,source,last_activity_at) VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)", (client_id, 'Caso Lixeira Teste', 'Caso Lixeira Teste', 'Em andamento', 'Descricao', staff_id, super_id, 'interno'))
            case_id = cursor.lastrowid
        document_id = self.add_document(client_id, 'lixeira.txt', b'conteudo lixeira', case_id=case_id, uploaded_by=super_id)
        with app.db() as connection:
            stored = connection.execute('SELECT stored FROM documents WHERE id=?', (document_id,)).fetchone()[0]
        stored_path = app.UP / stored
        self.assertTrue(stored_path.is_file())
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/relatorios?from=2000-01-01&to=2100-01-01', cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Resposta média às solicitações'.encode(), data)
        status, headers, data = self.request('GET', '/admin/relatorios?from=2000-01-01&to=2100-01-01&export=csv', cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn('text/csv', headers.get('Content-Type', ''))
        self.assertIn(b'Caso Lixeira Teste', data)
        self.assertEqual(self.request('GET', '/admin/relatorios', cookie=staff_cookie)[0], 200)
        self.assertEqual(self.request('GET', '/admin/mensagens', cookie=staff_cookie)[0], 200)
        self.assertEqual(self.request('GET', '/admin/arquivos', cookie=staff_cookie)[0], 200)
        _, _, csrf_token = self.csrf('/admin/casos', super_cookie)
        body = urllib.parse.urlencode({'csrf': csrf_token, 'entity': 'case', 'record_id': case_id})
        self.assertEqual(self.request('POST', '/admin/delete', body, cookie=super_cookie)[0], 303)
        with app.db() as connection:
            deleted_case = connection.execute('SELECT deleted_at FROM cases WHERE id=?', (case_id,)).fetchone()
            delete_audit = connection.execute("SELECT * FROM audit WHERE action='mover para lixeira' AND entity='case' ORDER BY id DESC LIMIT 1").fetchone()
        self.assertTrue(deleted_case['deleted_at'])
        self.assertIsNotNone(delete_audit)
        status, headers, data = self.request('GET', '/admin/lixeira', cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Caso Lixeira Teste'.encode(), data)
        status, headers, data = self.request('GET', '/cliente/atendimentos', cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertNotIn('Caso Lixeira Teste'.encode(), data)
        _, _, trash_csrf = self.csrf('/admin/lixeira', super_cookie)
        body = urllib.parse.urlencode({'csrf': trash_csrf, 'entity': 'case', 'record_id': case_id})
        self.assertEqual(self.request('POST', '/admin/restore', body, cookie=super_cookie)[0], 303)
        status, headers, data = self.request('GET', '/cliente/atendimentos', cookie=client_cookie)
        self.assertIn('Caso Lixeira Teste'.encode(), data)
        body = urllib.parse.urlencode({'csrf': trash_csrf, 'entity': 'document', 'record_id': document_id})
        self.assertEqual(self.request('POST', '/admin/delete', body, cookie=super_cookie)[0], 303)
        self.assertEqual(self.request('GET', '/arquivo/' + str(document_id), cookie=client_cookie)[0], 403)
        status, headers, data = self.request('GET', '/cliente/documentos', cookie=client_cookie)
        self.assertNotIn(b'lixeira.txt', data)
        body = urllib.parse.urlencode({'csrf': trash_csrf, 'entity': 'document', 'record_id': document_id})
        self.assertEqual(self.request('POST', '/admin/restore', body, cookie=super_cookie)[0], 303)
        self.assertEqual(self.request('GET', '/arquivo/' + str(document_id), cookie=client_cookie)[0], 200)
        body = urllib.parse.urlencode({'csrf': trash_csrf, 'entity': 'document', 'record_id': document_id})
        self.assertEqual(self.request('POST', '/admin/delete', body, cookie=super_cookie)[0], 303)
        body = urllib.parse.urlencode({'csrf': trash_csrf, 'entity': 'document', 'record_id': document_id, 'confirm': 'NAO'})
        self.assertEqual(self.request('POST', '/admin/purge', body, cookie=super_cookie)[0], 400)
        body = urllib.parse.urlencode({'csrf': trash_csrf, 'entity': 'document', 'record_id': document_id, 'confirm': 'EXCLUIR'})
        self.assertEqual(self.request('POST', '/admin/purge', body, cookie=super_cookie)[0], 303)
        with app.db() as connection:
            self.assertIsNone(connection.execute('SELECT id FROM documents WHERE id=?', (document_id,)).fetchone())
        self.assertFalse(stored_path.exists())
        status, headers, data = self.request('GET', '/admin/auditoria?entity=case&from=2000-01-01&to=2100-01-01', cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'mover para lixeira', data)
        status, headers, data = self.request('GET', '/admin/auditoria?entity=case&export=csv', cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn('text/csv', headers.get('Content-Type', ''))
        self.assertIn(b'mover para lixeira', data)
        _, _, client_csrf = self.csrf('/admin/clientes', super_cookie)
        body = urllib.parse.urlencode({'csrf': client_csrf, 'entity': 'client', 'record_id': client_id})
        self.assertEqual(self.request('POST', '/admin/delete', body, cookie=super_cookie)[0], 303)
        self.assertEqual(self.login(client_email, 'SenhaSegura123')[0], 401)
        self.assertEqual(self.request('GET', '/cliente', cookie=client_cookie)[0], 403)
        body = urllib.parse.urlencode({'csrf': trash_csrf, 'entity': 'client', 'record_id': client_id})
        self.assertEqual(self.request('POST', '/admin/restore', body, cookie=super_cookie)[0], 303)
        self.assertEqual(self.login(client_email, 'SenhaSegura123')[0], 303)
        _, _, permission_csrf = self.csrf('/admin/permissoes', super_cookie)
        body = urllib.parse.urlencode({'csrf': permission_csrf, 'user_id': staff_id})
        self.assertEqual(self.request('POST', '/admin/permissoes', body, cookie=super_cookie)[0], 303)
        status, _, restricted_cases = self.request('GET', '/admin/casos', cookie=staff_cookie)
        self.assertEqual(status, 200)
        self.assertNotIn(b'action="/admin/caso/editar"', restricted_cases)
        self.assertEqual(self.request('GET', '/admin/relatorios', cookie=staff_cookie)[0], 403)
        body = urllib.parse.urlencode({'csrf': client_csrf, 'entity': 'client', 'record_id': client_id})
        self.assertEqual(self.request('POST', '/admin/delete', body, cookie=super_cookie)[0], 303)
        body = urllib.parse.urlencode({'csrf': trash_csrf, 'entity': 'client', 'record_id': client_id, 'confirm': 'EXCLUIR'})
        self.assertEqual(self.request('POST', '/admin/purge', body, cookie=super_cookie)[0], 303)
        with app.db() as connection:
            self.assertIsNone(connection.execute('SELECT id FROM users WHERE id=?', (client_id,)).fetchone())
            self.assertIsNone(connection.execute('SELECT id FROM cases WHERE client_id=?', (client_id,)).fetchone())
            self.assertIsNone(connection.execute('SELECT id FROM documents WHERE client_id=?', (client_id,)).fetchone())
            purge_audit = connection.execute("SELECT * FROM audit WHERE action='excluir definitivamente' AND entity='user' ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(purge_audit)

    def test_mfa_totp_recovery_and_reset(self):
        super_id, super_email = self.add_user('Super MFA', role='admin')
        _, _, _, cookie = self.login(super_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/admin/seguranca', cookie=cookie)[0], 200)
        _, _, token = self.csrf('/admin/seguranca', cookie)
        body = urllib.parse.urlencode({'csrf': token})
        self.assertEqual(self.request('POST', '/admin/seguranca/iniciar', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            account = connection.execute('SELECT totp_secret,totp_enabled FROM users WHERE id=?', (super_id,)).fetchone()
        self.assertTrue(account['totp_secret'])
        self.assertEqual(account['totp_enabled'], 0)
        secret = account['totp_secret']
        code = app.totp_code(secret, app.totp_step())
        body = urllib.parse.urlencode({'csrf': token, 'code': code})
        status, headers, data = self.request('POST', '/admin/seguranca/confirmar', body, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Códigos de recuperação'.encode(), data)
        recovery_matches = re.findall(rb'[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}', data)
        self.assertGreaterEqual(len(recovery_matches), 2)
        recovery_code = recovery_matches[0].decode()
        second_recovery_code = recovery_matches[1].decode()
        with app.db() as connection:
            account = connection.execute('SELECT totp_enabled,recovery_codes FROM users WHERE id=?', (super_id,)).fetchone()
        self.assertEqual(account['totp_enabled'], 1)
        self.assertEqual(len(json.loads(account['recovery_codes'])), 8)
        self.assertEqual(self.request('GET', '/sair', cookie=cookie)[0], 303)
        status, headers, data, _ = self.login(super_email, 'SenhaSegura123')
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/entrar/mfa')
        mfa_token = self.cookie(headers, 'mfa')
        self.assertTrue(mfa_token)
        status, data, mfa_csrf = self.csrf('/entrar/mfa', 'mfa=' + mfa_token)
        self.assertEqual(status, 200)
        body = urllib.parse.urlencode({'csrf': mfa_csrf, 'code': 'abcdef'})
        self.assertEqual(self.request('POST', '/entrar/mfa', body, cookie='mfa=' + mfa_token)[0], 401)
        code = app.totp_code(secret, app.totp_step())
        body = urllib.parse.urlencode({'csrf': mfa_csrf, 'code': code})
        status, headers, data = self.request('POST', '/entrar/mfa', body, cookie='mfa=' + mfa_token)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/admin')
        sid = self.cookie(headers)
        self.assertTrue(sid)
        self.assertEqual(self.request('GET', '/sair', cookie=sid)[0], 303)
        status, headers, data, _ = self.login(super_email, 'SenhaSegura123')
        mfa_token = self.cookie(headers, 'mfa')
        status, data, mfa_csrf = self.csrf('/entrar/mfa', 'mfa=' + mfa_token)
        body = urllib.parse.urlencode({'csrf': mfa_csrf, 'code': recovery_code})
        status, headers, data = self.request('POST', '/entrar/mfa', body, cookie='mfa=' + mfa_token)
        self.assertEqual(status, 303)
        recovery_sid = self.cookie(headers)
        self.assertTrue(recovery_sid)
        with app.db() as connection:
            remaining = len(json.loads(connection.execute('SELECT recovery_codes FROM users WHERE id=?', (super_id,)).fetchone()[0]))
        self.assertEqual(remaining, 7)
        self.assertEqual(self.request('GET', '/sair', cookie=recovery_sid)[0], 303)
        status, headers, data, _ = self.login(super_email, 'SenhaSegura123')
        mfa_token = self.cookie(headers, 'mfa')
        status, data, mfa_csrf = self.csrf('/entrar/mfa', 'mfa=' + mfa_token)
        body = urllib.parse.urlencode({'csrf': mfa_csrf, 'code': recovery_code})
        self.assertEqual(self.request('POST', '/entrar/mfa', body, cookie='mfa=' + mfa_token)[0], 401)
        status, headers, data, _ = self.login(super_email, 'SenhaSegura123')
        mfa_token = self.cookie(headers, 'mfa')
        status, data, mfa_csrf = self.csrf('/entrar/mfa', 'mfa=' + mfa_token)
        body = urllib.parse.urlencode({'csrf': mfa_csrf, 'code': second_recovery_code})
        status, headers, data = self.request('POST', '/entrar/mfa', body, cookie='mfa=' + mfa_token)
        self.assertEqual(status, 303)
        reset_sid = self.cookie(headers)
        self.assertTrue(reset_sid)
        _, _, users_csrf = self.csrf('/admin/usuarios', reset_sid)
        body = urllib.parse.urlencode({'csrf': users_csrf, 'user_id': super_id})
        self.assertEqual(self.request('POST', '/admin/user/mfa-reset', body, cookie=reset_sid)[0], 303)
        with app.db() as connection:
            reset_account = connection.execute('SELECT totp_enabled,totp_secret,recovery_codes FROM users WHERE id=?', (super_id,)).fetchone()
            reset_audit = connection.execute("SELECT * FROM audit WHERE action='redefinir MFA' ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(reset_account['totp_enabled'], 0)
        self.assertEqual(reset_account['totp_secret'], '')
        self.assertEqual(reset_account['recovery_codes'], '')
        self.assertIsNotNone(reset_audit)
        status, headers, data, _ = self.login(super_email, 'SenhaSegura123')
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/admin')

    def test_lgpd_export_client_and_admin(self):
        super_id, super_email = self.add_user('Super LGPD', role='admin')
        staff_id, staff_email = self.add_user('Advogado LGPD', role='staff')
        client_id, client_email = self.add_user('Cliente LGPD')
        with app.db() as connection:
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (staff_id, client_id))
            cursor = connection.execute("INSERT INTO cases(client_id,title,original_title,status,description,responsible_id,created_by,source,last_activity_at) VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)", (client_id, 'Caso LGPD Exportacao', 'Caso LGPD Exportacao', 'Em andamento', 'Descricao do caso', staff_id, super_id, 'interno'))
            case_id = cursor.lastrowid
            connection.execute("INSERT INTO messages(client_id,case_id,sender_id,sender_role,visibility,reveal_identity,body,read_by_client,read_by_staff) VALUES(?,?,?,?,?,?,?,1,1)", (client_id, case_id, client_id, 'client', 'client', 0, 'Mensagem visivel LGPD'))
            connection.execute("INSERT INTO messages(client_id,case_id,sender_id,sender_role,visibility,reveal_identity,body,read_by_client,read_by_staff) VALUES(?,?,?,?,?,?,?,1,1)", (client_id, case_id, super_id, 'admin', 'internal', 0, 'Relato interno secreto LGPD'))
        self.add_document(client_id, 'lgpd.txt', b'documento lgpd', case_id=case_id, uploaded_by=super_id)
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/cliente/exportar', cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertIn('application/json', headers.get('Content-Type', ''))
        self.assertIn('attachment', headers.get('Content-Disposition', ''))
        payload = json.loads(data.decode())
        self.assertEqual(payload['titular']['email'], client_email)
        self.assertNotIn('password', payload['titular'])
        self.assertEqual(payload['casos'][0]['title'], 'Caso LGPD Exportacao')
        self.assertTrue(any(item['corpo'] == 'Mensagem visivel LGPD' for item in payload['mensagens']))
        self.assertEqual(payload['documentos'][0]['filename'], 'lgpd.txt')
        self.assertNotIn('Relato interno secreto LGPD'.encode(), data)
        self.assertEqual(self.request('GET', '/admin/cliente/exportar?client_id=' + str(client_id), cookie=client_cookie)[0], 403)
        self.assertEqual(self.request('GET', '/admin/cliente/exportar?client_id=' + str(client_id))[0], 403)
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/admin/cliente/exportar?client_id=' + str(client_id), cookie=staff_cookie)[0], 403)
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        status, headers, data = self.request('GET', '/admin/cliente/exportar?client_id=' + str(client_id), cookie=super_cookie)
        self.assertEqual(status, 200)
        admin_payload = json.loads(data.decode())
        self.assertEqual(admin_payload['titular']['email'], client_email)
        self.assertEqual(admin_payload['casos'][0]['id'], case_id)
        self.assertNotIn('Relato interno secreto LGPD'.encode(), data)

    def test_staff_actionable_document_filter_respects_case_permissions(self):
        staff_id, email = self.add_user('Advogado Arquivos Painel', role='staff')
        other_id, _ = self.add_user('Outro Responsavel Arquivos', role='staff')
        client_id, _ = self.add_user('Cliente Arquivos Painel')
        with app.db() as connection:
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (staff_id, client_id))
            own_case = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Caso próprio', staff_id)).lastrowid
            other_case = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Outro caso', other_id)).lastrowid
        self.add_document(client_id, 'proprio-para-analise.txt', b'proprio', case_id=own_case, source='cliente')
        self.add_document(client_id, 'outro-para-analise.txt', b'outro', case_id=other_case, source='cliente')
        _, _, _, cookie = self.login(email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/admin/arquivos?status=aguardando_analise&acao=meus', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'proprio-para-analise.txt', data)
        self.assertNotIn(b'outro-para-analise.txt', data)
        all_documents = self.request('GET', '/admin/arquivos?status=aguardando_analise&q=para-analise', cookie=cookie)[2]
        self.assertIn(b'outro-para-analise.txt', all_documents)

    def test_report_explains_response_metric_without_data(self):
        _, email = self.add_user('Advogado Relatorio Vazio', role='staff')
        _, _, _, cookie = self.login(email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/admin/relatorios', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Resposta média às solicitações (horas)'.encode(), data)
        self.assertIn('não inclui conversas'.encode(), data)
        self.assertIn('—'.encode(), data)

    def test_public_contact_queue_and_responsible(self):
        super_id, super_email = self.add_user('Super Contatos', role='admin')
        _, regular_email = self.add_user('Admin Sem Fila', role='admin', is_super=0)
        responsible_id, _ = self.add_user('Responsavel Contatos', role='admin')
        _, _, token = self.csrf('/contato')
        email = unique_email('visitante')
        body = urllib.parse.urlencode({'csrf': token, 'name': 'Visitante Contato', 'email': email, 'message': 'Dúvida sobre atendimento', 'consent': '1'})
        self.assertEqual(self.request('POST', '/contato', body, {'Origin': 'http://127.0.0.1:' + str(self.port)})[0], 200)
        with app.db() as connection:
            contact = connection.execute('SELECT * FROM contacts WHERE email=?', (email,)).fetchone()
            self.assertEqual(contact['status'], 'novo')
            self.assertTrue(connection.execute("SELECT 1 FROM notifications WHERE user_id=? AND type='contact'", (super_id,)).fetchone())
        _, _, _, cookie = self.login(super_email, 'SenhaSegura123')
        _, _, _, regular_cookie = self.login(regular_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/admin/contatos', cookie=regular_cookie)[0], 403)
        status, _, data = self.request('GET', '/admin/contatos?status=novo&q=Visitante', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(email.encode(), data)
        self.assertIn(b'mailto:', data)
        _, _, csrf_token = self.csrf('/admin/contatos', cookie)
        _, _, regular_csrf = self.csrf('/admin', regular_cookie)
        update = urllib.parse.urlencode({'csrf': csrf_token, 'contact_id': contact['id'], 'status': 'respondido', 'responsible_id': responsible_id})
        denied = urllib.parse.urlencode({'csrf': regular_csrf, 'contact_id': contact['id'], 'status': 'respondido', 'responsible_id': responsible_id})
        self.assertEqual(self.request('POST', '/admin/contato/status', denied, cookie=regular_cookie)[0], 403)
        self.assertEqual(self.request('POST', '/admin/contato/status', update, cookie=cookie)[0], 303)
        with app.db() as connection:
            updated = connection.execute('SELECT status,responsible_id FROM contacts WHERE id=?', (contact['id'],)).fetchone()
            self.assertEqual((updated['status'], updated['responsible_id']), ('respondido', responsible_id))
        self.assertNotIn(email.encode(), self.request('GET', '/admin/contatos?status=novo&q=Visitante', cookie=cookie)[2])
        self.assertIn(email.encode(), self.request('GET', '/admin/contatos?status=respondido&q=Visitante', cookie=cookie)[2])

    def test_administrative_filters_and_pagination(self):
        admin_id, admin_email = self.add_user('Admin Filtros', role='admin')
        client_a, _ = self.add_user('Cliente Filtro Alfa')
        client_b, _ = self.add_user('Cliente Filtro Beta')
        with app.db() as connection:
            case_a = connection.execute('INSERT INTO cases(client_id,title,status) VALUES(?,?,?)', (client_a, 'Caso Filtro Alfa', 'Em andamento')).lastrowid
            case_b = connection.execute('INSERT INTO cases(client_id,title,status,responsible_id) VALUES(?,?,?,?)', (client_b, 'Caso Filtro Beta', 'Em andamento', admin_id)).lastrowid
            conversation_a = app.create_conversation(connection, client_a, case_a, 'Assunto Filtro Alfa', 'client', client_a)
            conversation_b = app.create_conversation(connection, client_b, case_b, 'Assunto Filtro Beta', 'internal', admin_id)
            connection.execute('INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,body,read_by_client,read_by_staff) VALUES(?,?,?,?,?,?,?,?,?)', (client_a, case_a, conversation_a, client_a, 'client', 'client', 'Não lida Alfa', 1, 0))
            connection.execute('INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,body,read_by_client,read_by_staff) VALUES(?,?,?,?,?,?,?,?,?)', (client_b, case_b, conversation_b, admin_id, 'admin', 'internal', 'Relato Beta', 1, 1))
            connection.execute('INSERT INTO pendencies(client_id,case_id,title,status) VALUES(?,?,?,?)', (client_a, case_a, 'Pendência Filtro Alfa', 'Recebida'))
            connection.execute('INSERT INTO pendencies(client_id,case_id,title,status) VALUES(?,?,?,?)', (client_b, case_b, 'Pendência Filtro Beta', 'Atendida'))
            connection.execute('INSERT INTO appointments(client_id,case_id,title,when_at,status) VALUES(?,?,?,?,?)', (client_a, case_a, 'Agenda Filtro Alfa', '2099-01-01 10:00', 'pendente'))
            connection.execute('INSERT INTO appointments(client_id,case_id,title,when_at,status) VALUES(?,?,?,?,?)', (client_b, case_b, 'Agenda Filtro Beta', '2099-02-01 10:00', 'cancelado'))
        doc_a = self.add_document(client_a, 'filtro-alfa.txt', b'alfa', case_id=case_a, source='cliente')
        doc_b = self.add_document(client_b, 'filtro-beta.txt', b'beta', case_id=case_b, source='cliente')
        with app.db() as connection:
            connection.execute("UPDATE documents SET status='aceito' WHERE id=?", (doc_b,))
        _, _, _, cookie = self.login(admin_email, 'SenhaSegura123')
        def page(path):
            status, _, data = self.request('GET', path, cookie=cookie)
            self.assertEqual(status, 200, path)
            return data
        self.assertIn(b'Cliente Filtro Alfa', page('/admin/clientes?q=Filtro+Alfa'))
        self.assertNotIn(b'Caso Filtro Beta', page('/admin/casos?q=Filtro+Alfa'))
        self.assertIn(b'Caso Filtro Alfa', page('/admin/casos?responsavel=sem&q=Filtro+Alfa'))
        unread = page('/admin/mensagens?filtro=nao_lidas&q=Filtro+Alfa')
        self.assertIn(b'Assunto Filtro Alfa', unread)
        self.assertNotIn(b'Assunto Filtro Beta', unread)
        docs = page('/admin/arquivos?status=aguardando_analise&q=filtro-')
        self.assertIn(b'filtro-alfa.txt', docs)
        self.assertNotIn(b'filtro-beta.txt', docs)
        pending = page('/admin/pendencias?status=Recebida&q=Filtro')
        self.assertIn('Pendência Filtro Alfa'.encode(), pending)
        self.assertNotIn('Pendência Filtro Beta'.encode(), pending)
        agenda = page('/admin/compromissos?status=cancelado&q=Filtro')
        self.assertIn(b'Agenda Filtro Beta', agenda)
        self.assertNotIn(b'Agenda Filtro Alfa', agenda)
        with app.db() as connection:
            connection.executemany('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)', [('Cliente Paginado %02d' % n, 'paginado%02d@example.test' % n, 'x', 'client') for n in range(17)])
        self.assertIn(b'Paginado 16', page('/admin/clientes?q=Paginado&page=2'))
        self.assertNotIn(b'Paginado 16', page('/admin/clientes?q=Paginado&page=1'))

    def test_contextual_case_actions_preserve_context_and_permissions(self):
        _, admin_email = self.add_user('Admin Acoes', role='admin')
        owner_id, _ = self.add_user('Responsavel Acoes', role='staff')
        _, viewer_email = self.add_user('Consultor Acoes', role='staff')
        client_id, _ = self.add_user('Cliente Acoes')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Caso Acoes', owner_id)).lastrowid
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, _, viewer_cookie = self.login(viewer_email, 'SenhaSegura123')
        target = '/admin/caso/historico?case_id=' + str(case_id)
        status, _, data = self.request('GET', target, cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'Solicitar documento', data)
        self.assertIn(b'Editar dados e respons', data)
        viewer_page = self.request('GET', target, cookie=viewer_cookie)[2]
        self.assertNotIn(b'Solicitar documento', viewer_page)
        params = urllib.parse.urlencode({'client_id': client_id, 'case_id': case_id, 'novo': '1'})
        status, _, page = self.request('GET', '/admin/pendencias?' + params, cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn(('value="' + str(client_id) + '" selected').encode(), page)
        self.assertIn(('value="' + str(case_id) + '" data-client-id="' + str(client_id) + '" selected').encode(), page)
        _, _, csrf_token = self.csrf('/admin', admin_cookie)
        fields = urllib.parse.urlencode({'csrf': csrf_token, 'client_id': client_id, 'case_id': case_id, 'title': 'Documento contextual', 'return_to': target})
        status, headers, _ = self.request('POST', '/admin/pendencia', fields, cookie=admin_cookie)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), target)
        self.assertIn(b'Documento contextual', self.request('GET', target, cookie=admin_cookie)[2])
        self.assertEqual(app.safe_admin_return({'client_id': str(client_id), 'return_to': 'https://example.test'}, '/admin'), '/admin')

    def test_case_form_preserves_administrator_responsible(self):
        _, editor_email = self.add_user('Admin Editor Responsavel', role='admin')
        responsible_id, _ = self.add_user('Admin Responsavel Caso', role='admin')
        client_id, _ = self.add_user('Cliente Responsavel Caso')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Caso Responsavel Admin', responsible_id)).lastrowid
        _, _, _, cookie = self.login(editor_email, 'SenhaSegura123')
        page = self.request('GET', '/admin/caso/historico?case_id=' + str(case_id), cookie=cookie)[2]
        self.assertIn(('value="' + str(responsible_id) + '" selected').encode(), page)
        _, _, csrf_token = self.csrf('/admin', cookie)
        fields = urllib.parse.urlencode({'csrf': csrf_token, 'case_id': case_id, 'title': 'Caso Atualizado', 'status': 'Em andamento', 'responsible_id': responsible_id})
        self.assertEqual(self.request('POST', '/admin/caso/editar', fields, cookie=cookie)[0], 303)
        with app.db() as connection:
            self.assertEqual(connection.execute('SELECT responsible_id FROM cases WHERE id=?', (case_id,)).fetchone()[0], responsible_id)

    def test_editing_preserves_other_assignments(self):
        _, admin_email = self.add_user('Admin Atribuicoes', role='admin')
        first_id, _ = self.add_user('Advogado Principal', role='staff')
        second_id, _ = self.add_user('Advogado Colaborador', role='staff')
        client_id, client_email = self.add_user('Cliente Atribuicoes')
        with app.db() as connection:
            connection.execute('UPDATE users SET owner_staff_id=? WHERE id=?', (first_id, client_id))
            connection.executemany('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', [(first_id, client_id), (second_id, client_id)])
            case_id = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Caso Atribuicoes', first_id)).lastrowid
            connection.executemany('INSERT INTO case_assignments(case_id,staff_id) VALUES(?,?)', [(case_id, first_id), (case_id, second_id)])
        _, _, _, cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, csrf_token = self.csrf('/admin', cookie)
        client_edit = urllib.parse.urlencode({'csrf': csrf_token, 'client_id': client_id, 'name': 'Cliente Editado', 'email': client_email, 'phone': '', 'active': '1', 'owner_staff_id': first_id})
        self.assertEqual(self.request('POST', '/admin/cliente/editar', client_edit, cookie=cookie)[0], 303)
        case_edit = urllib.parse.urlencode({'csrf': csrf_token, 'case_id': case_id, 'title': 'Caso Editado', 'status': 'Em andamento', 'responsible_id': first_id})
        self.assertEqual(self.request('POST', '/admin/caso/editar', case_edit, cookie=cookie)[0], 303)
        with app.db() as connection:
            self.assertEqual({row[0] for row in connection.execute('SELECT staff_id FROM assignments WHERE client_id=?', (client_id,))}, {first_id, second_id})
            self.assertEqual({row[0] for row in connection.execute('SELECT staff_id FROM case_assignments WHERE case_id=?', (case_id,))}, {first_id, second_id})
        case_team = urllib.parse.urlencode({'csrf': csrf_token, 'case_id': case_id, 'staff_id': second_id, 'operation': 'remove', 'return_to': '/admin/caso/historico?case_id=' + str(case_id)})
        status, headers, _ = self.request('POST', '/admin/caso/equipe', case_team, cookie=cookie)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get('Location'), '/admin/caso/historico?case_id=' + str(case_id))
        denied = urllib.parse.urlencode({'csrf': csrf_token, 'case_id': case_id, 'staff_id': first_id, 'operation': 'remove'})
        self.assertEqual(self.request('POST', '/admin/caso/equipe', denied, cookie=cookie)[0], 400)
        add = urllib.parse.urlencode({'csrf': csrf_token, 'case_id': case_id, 'staff_id': second_id, 'operation': 'add'})
        self.assertEqual(self.request('POST', '/admin/caso/equipe', add, cookie=cookie)[0], 303)
        with app.db() as connection:
            second_assignment = connection.execute('SELECT id FROM assignments WHERE client_id=? AND staff_id=?', (client_id, second_id)).fetchone()[0]
            primary_assignment = connection.execute('SELECT id FROM assignments WHERE client_id=? AND staff_id=?', (client_id, first_id)).fetchone()[0]
        remove = urllib.parse.urlencode({'csrf': csrf_token, 'client_id': client_id, 'assignment_id': second_assignment, 'return_to': '/admin/cliente?client_id=' + str(client_id)})
        self.assertEqual(self.request('POST', '/admin/unassign', remove, cookie=cookie)[1]['Location'], '/admin/cliente?client_id=' + str(client_id))
        denied = urllib.parse.urlencode({'csrf': csrf_token, 'client_id': client_id, 'assignment_id': primary_assignment})
        self.assertEqual(self.request('POST', '/admin/unassign', denied, cookie=cookie)[0], 400)

    def test_conversation_migration_preserves_legacy_messages(self):
        with tempfile.TemporaryDirectory(prefix='bomfim-conversation-migration-') as directory:
            env = dict(os.environ, APP_DB=os.path.join(directory, 'legacy.db'), APP_UPLOADS=os.path.join(directory, 'uploads'))
            script = '''
import app
app.init()
with app.db() as c:
    client = c.execute("INSERT INTO users(name,email,password,role) VALUES('Cliente','legacy@example.test','x','client')").lastrowid
    admin = c.execute("INSERT INTO users(name,email,password,role) VALUES('Admin','admin@example.test','x','admin')").lastrowid
    message = c.execute("INSERT INTO messages(client_id,sender_id,sender_role,visibility,body,read_by_client,read_by_staff) VALUES(?,?,'admin','client','Mensagem preservada',0,1)", (client,admin)).lastrowid
    app.notify(c, client, 'message', 'Aviso legado', '', '/cliente', client, None, 'message-' + str(message) + '-client')
    c.execute("INSERT INTO contacts(name,email,message) VALUES('Contato antigo','contato@example.test','Mensagem preservada')")
    c.execute('DELETE FROM schema_migrations')
    c.execute('INSERT INTO schema_migrations(version) VALUES(7)')
app.init()
app.init()
with app.db() as c:
    row = c.execute('SELECT m.body,cv.id,cv.status FROM messages m JOIN conversations cv ON cv.id=m.conversation_id').fetchone()
    assert row['body'] == 'Mensagem preservada' and row['status'] == 'legacy'
    assert c.execute('SELECT COUNT(*) FROM conversations').fetchone()[0] == 1
    assert c.execute('SELECT url FROM notifications').fetchone()[0] == '/conversas/' + str(row['id'])
    assert c.execute('SELECT status FROM contacts').fetchone()[0] == 'nao_classificado'
assert list((app.DB.parent / 'backups').glob('app-v7-to-v*.db'))
'''
            result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_lawyers_can_view_other_cases_without_editing(self):
        owner_id, _ = self.add_user('Responsável Caso Visível', role='staff')
        _, viewer_email = self.add_user('Consultor Caso Visível', role='staff')
        client_id, _ = self.add_user('Cliente Caso Visível')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Caso para consulta', owner_id)).lastrowid
        doc_id = self.add_document(client_id, 'consulta.txt', b'consulta', case_id=case_id)
        _, _, _, cookie = self.login(viewer_email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/admin/casos', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'Caso para consulta', data)
        self.assertEqual(self.request('GET', '/admin/caso/historico?case_id=' + str(case_id), cookie=cookie)[0], 200)
        self.assertEqual(self.request('GET', '/arquivo/' + str(doc_id), cookie=cookie)[0], 200)
        _, _, csrf_token = self.csrf('/admin/casos', cookie)
        edit = urllib.parse.urlencode({'csrf': csrf_token, 'case_id': case_id, 'title': 'Alteração indevida', 'status': 'Em andamento'})
        self.assertEqual(self.request('POST', '/admin/caso/editar', edit, cookie=cookie)[0], 403)
        with app.db() as connection:
            self.assertEqual(connection.execute('SELECT title FROM cases WHERE id=?', (case_id,)).fetchone()[0], 'Caso para consulta')

    def test_client_home_only_requests_action_and_shows_future_appointments(self):
        client_id, client_email = self.add_user('Cliente Resumo')
        with app.db() as connection:
            connection.execute('INSERT INTO pendencies(client_id,title,status) VALUES(?,?,?)', (client_id, 'Documento recebido', 'Recebida'))
            connection.execute('INSERT INTO pendencies(client_id,title,status) VALUES(?,?,?)', (client_id, 'Documento necessário', 'Aberta'))
            connection.execute('INSERT INTO appointments(client_id,title,when_at,status) VALUES(?,?,?,?)', (client_id, 'Consulta antiga', '2020-01-01 10:00', 'realizado'))
            connection.execute('INSERT INTO appointments(client_id,title,when_at,status) VALUES(?,?,?,?)', (client_id, 'Consulta futura', '2099-01-01 10:00', 'pendente'))
        _, _, _, cookie = self.login(client_email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/cliente', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Documento necessário'.encode(), data)
        self.assertNotIn('Documento recebido'.encode(), data)
        self.assertIn('Consulta futura'.encode(), data)
        self.assertNotIn('Consulta antiga'.encode(), data)

    def test_notification_list_prioritizes_unread_older_items(self):
        client_id, email = self.add_user('Cliente Avisos Antigos')
        with app.db() as connection:
            app.notify(connection, client_id, 'message', 'Aviso antigo não lido')
            for index in range(25):
                app.notify(connection, client_id, 'update', 'Aviso lido ' + str(index))
            connection.execute("UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND title LIKE 'Aviso lido %'", (client_id,))
        _, _, _, cookie = self.login(email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/notificacoes', cookie=cookie)
        payload = json.loads(data.decode())
        self.assertEqual(status, 200)
        self.assertEqual(payload['unread'], 1)
        self.assertEqual(payload['items'][0]['title'], 'Aviso antigo não lido')

    def test_reading_does_not_mark_later_messages(self):
        admin_id, admin_email = self.add_user('Admin Leitura Parcial', role='admin')
        client_id, client_email = self.add_user('Cliente Leitura Parcial')
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        _, _, client_csrf = self.csrf('/cliente', client_cookie)
        _, _, admin_csrf = self.csrf('/admin', admin_cookie)
        self.assertEqual(self.request('POST', '/cliente/mensagem', urllib.parse.urlencode({'csrf': client_csrf, 'subject': 'Assunto', 'body': 'Primeira'}), cookie=client_cookie)[0], 303)
        with app.db() as connection:
            conversation_id = connection.execute('SELECT id FROM conversations WHERE client_id=?', (client_id,)).fetchone()[0]
            first_id = connection.execute('SELECT id FROM messages WHERE conversation_id=?', (conversation_id,)).fetchone()[0]
        self.assertEqual(self.request('GET', '/conversas/' + str(conversation_id), cookie=admin_cookie)[0], 200)
        self.assertEqual(self.request('POST', '/conversas/responder', urllib.parse.urlencode({'csrf': client_csrf, 'conversation_id': conversation_id, 'body': 'Chegou depois'}), cookie=client_cookie)[0], 303)
        mark = urllib.parse.urlencode({'csrf': admin_csrf, 'conversation_id': conversation_id, 'last_message_id': first_id})
        status, _, payload = self.request('POST', '/conversas/ler', mark, {'Accept': 'application/json'}, admin_cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)['conversation_unread'], 1)
        with app.db() as connection:
            self.assertEqual(app.conversation_unread(connection, {'id': admin_id}, conversation_id), 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND type='message' AND read_at=''", (admin_id,)).fetchone()[0], 1)

    def test_conversation_lifecycle_and_individual_reading(self):
        admin_id, admin_email = self.add_user('Admin Conversa', role='admin')
        other_admin_id, other_admin_email = self.add_user('Outra Admin Conversa', role='admin')
        client_id, client_email = self.add_user('Cliente Conversa')
        _, stranger_email = self.add_user('Outro Cliente Conversa')
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, _, other_admin_cookie = self.login(other_admin_email, 'SenhaSegura123')
        _, _, _, stranger_cookie = self.login(stranger_email, 'SenhaSegura123')
        _, _, client_csrf = self.csrf('/cliente', client_cookie)
        _, _, admin_csrf = self.csrf('/admin', admin_cookie)
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title) VALUES(?,?)', (client_id, 'Caso da conversa')).lastrowid
        body = urllib.parse.urlencode({'csrf': client_csrf, 'case_id': case_id, 'subject': 'Meu primeiro assunto', 'body': 'Primeira mensagem'})
        self.assertEqual(self.request('POST', '/cliente/mensagem', body, cookie=client_cookie)[0], 303)
        with app.db() as connection:
            conversation = connection.execute('SELECT * FROM conversations WHERE client_id=? ORDER BY id DESC', (client_id,)).fetchone()
            conversation_id = conversation['id']
            first_message_id = connection.execute('SELECT id FROM messages WHERE conversation_id=?', (conversation_id,)).fetchone()[0]
            self.assertEqual(conversation['status'], 'open')
            self.assertEqual(app.conversation_unread(connection, {'id': admin_id}, conversation_id), 1)
            self.assertEqual(app.conversation_unread(connection, {'id': other_admin_id}, conversation_id), 1)
        self.assertEqual(self.request('GET', '/conversas/' + str(conversation_id), cookie=stranger_cookie)[0], 403)
        self.assertEqual(self.request('GET', '/admin/mensagens', cookie=admin_cookie)[0], 200)
        with app.db() as connection:
            self.assertEqual(app.conversation_unread(connection, {'id': admin_id}, conversation_id), 1)
        mark = urllib.parse.urlencode({'csrf': admin_csrf, 'conversation_id': conversation_id, 'last_message_id': first_message_id})
        self.assertEqual(self.request('POST', '/conversas/ler', mark, {'Accept': 'application/json'}, admin_cookie)[0], 200)
        with app.db() as connection:
            self.assertEqual(app.conversation_unread(connection, {'id': admin_id}, conversation_id), 0)
            self.assertEqual(app.conversation_unread(connection, {'id': other_admin_id}, conversation_id), 1)
            self.assertTrue(connection.execute("SELECT read_at FROM notifications WHERE user_id=? AND type='message' ORDER BY id DESC", (admin_id,)).fetchone()[0])
            self.assertFalse(connection.execute("SELECT read_at FROM notifications WHERE user_id=? AND type='message' ORDER BY id DESC", (other_admin_id,)).fetchone()[0])
        reply = urllib.parse.urlencode({'csrf': admin_csrf, 'conversation_id': conversation_id, 'body': 'Resposta do escritório'})
        self.assertEqual(self.request('POST', '/conversas/responder', reply, cookie=admin_cookie)[0], 303)
        self.assertEqual(self.request('GET', '/cliente', cookie=client_cookie)[0], 200)
        with app.db() as connection:
            self.assertEqual(app.conversation_unread(connection, {'id': client_id}, conversation_id), 1)
        self.assertEqual(self.request('POST', '/conversas/encerrar', urllib.parse.urlencode({'csrf': client_csrf, 'conversation_id': conversation_id}), cookie=client_cookie)[0], 403)
        self.assertEqual(self.request('POST', '/conversas/encerrar', mark, cookie=admin_cookie)[0], 303)
        self.assertEqual(self.request('POST', '/conversas/responder', urllib.parse.urlencode({'csrf': client_csrf, 'conversation_id': conversation_id, 'body': 'Tentativa após encerramento'}), cookie=client_cookie)[0], 403)
        self.assertEqual(self.request('POST', '/cliente/mensagem', urllib.parse.urlencode({'csrf': client_csrf, 'case_id': case_id, 'subject': 'Novo contato', 'body': 'Nova conversa'}), cookie=client_cookie)[0], 303)
        with app.db() as connection:
            rows = connection.execute('SELECT * FROM conversations WHERE client_id=? ORDER BY id', (client_id,)).fetchall()
            self.assertEqual([row['status'] for row in rows], ['closed', 'open'])
            self.assertEqual([row['case_id'] for row in rows], [case_id, case_id])
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=?', (conversation_id,)).fetchone()[0], 2)
        self.assertEqual(self.request('GET', '/conversas/' + str(conversation_id), cookie=client_cookie)[0], 200)
        self.assertEqual(self.request('GET', '/conversas/' + str(conversation_id), cookie=other_admin_cookie)[0], 200)

    def test_login_rate_limit(self):
        app.RL.clear()
        original = app.LOGIN_EMAIL_LIMIT
        app.LOGIN_EMAIL_LIMIT = 3
        try:
            _, email = self.add_user('Usuario Limite')
            for _ in range(3):
                self.assertEqual(self.login(email, 'SenhaErrada123')[0], 401)
            self.assertEqual(self.login(email, 'SenhaErrada123')[0], 429)
        finally:
            app.LOGIN_EMAIL_LIMIT = original
            app.RL.clear()

    def test_session_expiry_and_logout(self):
        _, email = self.add_user('Admin Sessao', role='admin')
        _, _, _, cookie = self.login(email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/admin', cookie=cookie)[0], 200)
        with app.SESS_LOCK:
            app.SESS[cookie]['last'] -= app.SESSION_IDLE + 1
        self.assertEqual(self.request('GET', '/admin', cookie=cookie)[0], 403)
        _, _, _, cookie = self.login(email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/sair', cookie=cookie)[0], 303)
        self.assertEqual(self.request('GET', '/admin', cookie=cookie)[0], 403)


    def test_tasks_scope_creation_and_status_permissions(self):
        admin_id, admin_email = self.add_user('Admin Tarefas', role='admin')
        employee_id, employee_email = self.add_user('Funcionario Tarefas', role='staff')
        lawyer_id, _ = self.add_user('Advogado Tarefas', role='staff')
        client_id, client_email = self.add_user('Cliente Tarefas')
        other_client, _ = self.add_user('Cliente Fora Tarefas')
        with app.db() as connection:
            connection.execute("UPDATE users SET staff_kind='employee' WHERE id=?", (employee_id,))
            connection.execute('INSERT INTO assignments(staff_id,client_id) VALUES(?,?)', (employee_id, client_id))
            own_case = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Caso Tarefa Escopo', employee_id)).lastrowid
            other_case = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (other_client, 'Caso Tarefa Fora', lawyer_id)).lastrowid
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, admin_csrf = self.csrf('/admin/tarefas', admin_cookie)
        body = urllib.parse.urlencode({'csrf': admin_csrf, 'title': 'Protocolar contestação', 'description': 'Prazo interno.', 'client_id': client_id, 'case_id': own_case, 'assigned_to': employee_id, 'due_at': '2020-01-01T10:00', 'priority': 'urgente'})
        self.assertEqual(self.request('POST', '/admin/tarefa', body, cookie=admin_cookie)[0], 303)
        body = urllib.parse.urlencode({'csrf': admin_csrf, 'title': 'Revisar documento externo', 'client_id': other_client, 'case_id': other_case, 'assigned_to': lawyer_id, 'priority': 'normal'})
        self.assertEqual(self.request('POST', '/admin/tarefa', body, cookie=admin_cookie)[0], 303)
        _, _, _, employee_cookie = self.login(employee_email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/admin/tarefas', cookie=employee_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Protocolar contestação'.encode(), data)
        self.assertIn(b'Atrasada', data)
        self.assertNotIn(b'Revisar documento externo', data)
        _, _, employee_csrf = self.csrf('/admin/tarefas', employee_cookie)
        task_id = 0
        with app.db() as connection:
            task_id = connection.execute("SELECT id FROM tasks WHERE title='Protocolar contestação'").fetchone()[0]
        body = urllib.parse.urlencode({'csrf': employee_csrf, 'task_id': task_id, 'status': 'concluida'})
        self.assertEqual(self.request('POST', '/admin/tarefa/status', body, cookie=employee_cookie)[0], 303)
        with app.db() as connection:
            self.assertEqual(connection.execute('SELECT status FROM tasks WHERE id=?', (task_id,)).fetchone()[0], 'concluida')
        body = urllib.parse.urlencode({'csrf': employee_csrf, 'title': 'Tarefa fora do escopo', 'client_id': other_client, 'assigned_to': lawyer_id})
        self.assertEqual(self.request('POST', '/admin/tarefa', body, cookie=employee_cookie)[0], 403)
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/admin/tarefas', cookie=client_cookie)[0], 403)

    def test_internal_documents_scope_and_client_denied(self):
        admin_id, admin_email = self.add_user('Admin Documentos Internos', role='admin')
        employee_id, employee_email = self.add_user('Funcionario Documentos Internos', role='staff')
        client_id, client_email = self.add_user('Cliente Documentos Internos')
        with app.db() as connection:
            connection.execute("UPDATE users SET staff_kind='employee' WHERE id=?", (employee_id,))
            case_id = connection.execute('INSERT INTO cases(client_id,title) VALUES(?,?)', (client_id, 'Caso Documento Interno')).lastrowid
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, admin_csrf = self.csrf('/admin/documentos-internos', admin_cookie)
        upload_body, upload_headers = self.multipart({'csrf': admin_csrf, 'title': 'Parecer interno', 'category': 'Parecer', 'visibility': 'equipe'}, 'parecer.txt', b'parecer interno')
        self.assertEqual(self.request('POST', '/admin/documento-interno', upload_body, upload_headers, admin_cookie)[0], 303)
        with app.db() as connection:
            document = connection.execute("SELECT * FROM internal_documents WHERE title='Parecer interno'").fetchone()
        self.assertIsNotNone(document)
        self.assertEqual(self.request('GET', '/interno/' + str(document['id']), cookie=admin_cookie)[0], 200)
        _, _, _, employee_cookie = self.login(employee_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/interno/' + str(document['id']), cookie=employee_cookie)[0], 200)
        _, _, employee_csrf = self.csrf('/admin/documentos-internos', employee_cookie)
        upload_body, upload_headers = self.multipart({'csrf': employee_csrf, 'title': 'Documento restrito ao caso', 'visibility': 'caso', 'client_id': client_id, 'case_id': case_id}, 'restrito.txt', b'restrito')
        self.assertEqual(self.request('POST', '/admin/documento-interno', upload_body, upload_headers, employee_cookie)[0], 403)
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/interno/' + str(document['id']), cookie=client_cookie)[0], 403)
        self.assertEqual(self.request('GET', '/admin/documentos-internos', cookie=client_cookie)[0], 403)

    def test_appointment_kind_owner_and_conversation_workspace(self):
        admin_id, admin_email = self.add_user('Admin Agenda Nova', role='admin')
        staff_id, _ = self.add_user('Advogado Agenda Nova', role='staff')
        client_id, client_email = self.add_user('Cliente Agenda Nova')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title) VALUES(?,?)', (client_id, 'Caso Agenda Nova')).lastrowid
            conversation_id = connection.execute('INSERT INTO conversations(client_id,case_id,title,visibility,created_by) VALUES(?,?,?,?,?)', (client_id, case_id, 'Conversa Agenda Nova', 'client', admin_id)).lastrowid
            connection.execute("INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,body) VALUES(?,?,?,?,?,?,?)", (client_id, case_id, conversation_id, client_id, 'client', 'client', 'Mensagem da conversa nova'))
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, admin_csrf = self.csrf('/admin/compromissos', admin_cookie)
        body = urllib.parse.urlencode({'csrf': admin_csrf, 'client_id': client_id, 'case_id': case_id, 'title': 'Audiência de instrução', 'kind': 'audiencia', 'when_at': '2099-02-10T09:30', 'location': 'Fórum de Fortaleza', 'owner_id': staff_id, 'notes': 'Levar documentos.'})
        self.assertEqual(self.request('POST', '/admin/appointment', body, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            appointment = connection.execute("SELECT * FROM appointments WHERE title='Audiência de instrução'").fetchone()
        self.assertEqual(appointment['kind'], 'audiencia')
        self.assertEqual(appointment['owner_id'], staff_id)
        self.assertEqual(appointment['location'], 'Fórum de Fortaleza')
        status, _, data = self.request('GET', '/admin/compromissos', cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Audiência de instrução'.encode(), data)
        self.assertIn('Fórum de Fortaleza'.encode(), data)
        status, _, data = self.request('GET', '/admin/mensagens', cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'conversation-workspace', data)
        self.assertIn(b'?conversa=', data)
        self.assertIn(b'Mensagem da conversa nova', data)
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/cliente/mensagens', cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'conversation-workspace', data)
        self.assertIn(b'Mensagem da conversa nova', data)


    def test_calendar_month_view(self):
        admin_id, admin_email = self.add_user('Admin Calendario', role='admin')
        staff_id, _ = self.add_user('Advogado Calendario', role='staff')
        client_id, _ = self.add_user('Cliente Calendario')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title) VALUES(?,?)', (client_id, 'Caso Calendario')).lastrowid
            connection.execute("INSERT INTO appointments(client_id,case_id,title,when_at,notes,created_by,status,kind,owner_id,location) VALUES(?,?,?,?,?,?,'pendente','audiencia',?,?)", (client_id, case_id, 'Audiência do calendário', '2026-12-10 09:30', 'Levar documentos.', admin_id, staff_id, 'Fórum'))
            connection.execute("INSERT INTO tasks(title,description,client_id,case_id,assigned_to,created_by,due_at,priority,status) VALUES(?,?,?,?,?,?,?,?,?)", ('Prazo no calendário', 'Tarefa integrada.', client_id, case_id, staff_id, admin_id, '2026-12-15 18:00', 'alta', 'pendente'))
        _, _, _, cookie = self.login(admin_email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/admin/compromissos?visao=mes&mes=2026-12', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'calendar-grid', data)
        self.assertIn('Dezembro de 2026'.encode(), data)
        self.assertIn('Audiência do calendário'.encode(), data)
        self.assertIn('Prazo no calendário'.encode(), data)
        status, _, data = self.request('GET', '/admin/compromissos', cookie=cookie)
        self.assertIn('Calendário'.encode(), data)

    def test_task_edit_delete_and_history(self):
        admin_id, admin_email = self.add_user('Admin Edicao Tarefa', role='admin')
        _, _, _, cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin/tarefas', cookie)
        body = urllib.parse.urlencode({'csrf': token, 'title': 'Tarefa editável', 'description': 'Inicial', 'due_at': '2099-01-01T10:00', 'priority': 'normal'})
        self.assertEqual(self.request('POST', '/admin/tarefa', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            task_id = connection.execute("SELECT id FROM tasks WHERE title='Tarefa editável'").fetchone()[0]
        status, _, data = self.request('GET', '/admin/tarefa?task_id=' + str(task_id), cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Editar tarefa'.encode(), data)
        self.assertIn('Histórico'.encode(), data)
        body = urllib.parse.urlencode({'csrf': token, 'task_id': task_id, 'title': 'Tarefa revisada', 'description': 'Revisada', 'due_at': '2099-01-02T11:00', 'priority': 'alta', 'status': 'em_andamento'})
        self.assertEqual(self.request('POST', '/admin/tarefa/editar', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            task = connection.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        self.assertEqual(task['title'], 'Tarefa revisada')
        self.assertEqual(task['priority'], 'alta')
        self.assertEqual(task['status'], 'em_andamento')
        body = urllib.parse.urlencode({'csrf': token, 'task_id': task_id})
        self.assertEqual(self.request('POST', '/admin/tarefa/excluir', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            task = connection.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        self.assertTrue(task['deleted_at'])
        status, _, data = self.request('GET', '/admin/tarefas', cookie=cookie)
        self.assertNotIn('Tarefa revisada'.encode(), data)
        status, _, audit_data = self.request('GET', '/admin/auditoria?entity=task', cookie=cookie)
        self.assertIn('editar tarefa'.encode(), audit_data)

    def test_internal_document_edit_delete_and_history(self):
        admin_id, admin_email = self.add_user('Admin Edicao Interno', role='admin')
        _, _, _, cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin/documentos-internos', cookie)
        upload_body, upload_headers = self.multipart({'csrf': token, 'title': 'Modelo editável', 'category': 'Modelo', 'visibility': 'equipe'}, 'modelo.txt', b'modelo')
        self.assertEqual(self.request('POST', '/admin/documento-interno', upload_body, upload_headers, cookie)[0], 303)
        with app.db() as connection:
            document = connection.execute("SELECT * FROM internal_documents WHERE title='Modelo editável'").fetchone()
        status, _, data = self.request('GET', '/admin/documento-interno?doc_id=' + str(document['id']), cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Editar informações'.encode(), data)
        body = urllib.parse.urlencode({'csrf': token, 'doc_id': document['id'], 'title': 'Modelo revisado', 'category': 'Modelo revisado', 'visibility': 'equipe'})
        self.assertEqual(self.request('POST', '/admin/documento-interno/editar', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            updated = connection.execute('SELECT * FROM internal_documents WHERE id=?', (document['id'],)).fetchone()
        self.assertEqual(updated['title'], 'Modelo revisado')
        body = urllib.parse.urlencode({'csrf': token, 'doc_id': document['id']})
        self.assertEqual(self.request('POST', '/admin/documento-interno/excluir', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            deleted = connection.execute('SELECT * FROM internal_documents WHERE id=?', (document['id'],)).fetchone()
        self.assertTrue(deleted['deleted_at'])
        self.assertEqual(self.request('GET', '/interno/' + str(document['id']), cookie=cookie)[0], 403)

    def test_conversation_attachment_upload_and_download(self):
        admin_id, admin_email = self.add_user('Admin Anexo Conversa', role='admin')
        client_id, client_email = self.add_user('Cliente Anexo Conversa')
        other_id, other_email = self.add_user('Cliente Fora Anexo')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title) VALUES(?,?)', (client_id, 'Caso Anexo')).lastrowid
            conversation_id = connection.execute('INSERT INTO conversations(client_id,case_id,title,visibility,created_by) VALUES(?,?,?,?,?)', (client_id, case_id, 'Conversa com anexo', 'client', admin_id)).lastrowid
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        _, _, token = self.csrf('/cliente/mensagens', client_cookie)
        body, headers = self.multipart({'csrf': token, 'conversation_id': conversation_id, 'body': 'Segue o documento.'}, 'anexo.txt', b'conteudo anexado')
        self.assertEqual(self.request('POST', '/conversas/responder', body, headers, client_cookie)[0], 303)
        with app.db() as connection:
            attachment = connection.execute("SELECT * FROM message_attachments WHERE filename='anexo.txt'").fetchone()
        self.assertIsNotNone(attachment)
        status, _, data = self.request('GET', '/anexo/' + str(attachment['id']), cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertEqual(data, b'conteudo anexado')
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/anexo/' + str(attachment['id']), cookie=admin_cookie)[0], 200)
        _, _, _, other_cookie = self.login(other_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/anexo/' + str(attachment['id']), cookie=other_cookie)[0], 403)
        status, _, data = self.request('GET', '/cliente/mensagens', cookie=client_cookie)
        self.assertIn(b'/anexo/', data)
        self.assertIn(b'anexo.txt', data)


    def test_guest_chat_contact_replies_and_close(self):
        super_id, super_email = self.add_user('Super Visitante', role='admin')
        regular_id, regular_email = self.add_user('Admin Visitante Regular', role='admin', is_super=0)
        _, _, token = self.csrf('/contato')
        origin = 'http://127.0.0.1:' + str(self.port)
        body = urllib.parse.urlencode({'csrf': token, 'name': 'Visitante Chat', 'email': 'visitante.chat@example.test', 'phone': '(88) 99999-0000', 'message': 'Olá, preciso de orientação.', 'consent': '1'})
        status, _, data = self.request('POST', '/contato', body, {'Origin': origin})
        self.assertEqual(status, 200)
        match = re.search(rb'/atendimento/([A-Za-z0-9_-]{20,100})', data)
        self.assertIsNotNone(match)
        public_token = match.group(1).decode()
        with app.db() as connection:
            guest = connection.execute('SELECT * FROM guest_sessions WHERE token_hash=?', (app.guest_token_hash(public_token),)).fetchone()
            self.assertEqual(guest['phone'], '(88) 99999-0000')
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM guest_messages WHERE guest_id=?', (guest['id'],)).fetchone()[0], 1)
        status, _, page = self.request('GET', '/atendimento/' + public_token)
        self.assertEqual(status, 200)
        self.assertIn('Olá, preciso de orientação.'.encode(), page)
        self.assertIn(b'Enviar mensagem', page)
        _, _, guest_csrf = self.csrf('/atendimento/' + public_token)
        reply = urllib.parse.urlencode({'csrf': guest_csrf, 'token': public_token, 'body': 'Continuo aguardando o retorno.'})
        self.assertEqual(self.request('POST', '/atendimento/responder', reply, {'Origin': origin})[0], 303)
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        status, _, contacts = self.request('GET', '/admin/contatos?status=todos&q=Visitante+Chat', cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'Abrir conversa e responder', contacts)
        status, _, admin_page = self.request('GET', '/admin/atendimento-visitante?guest_id=' + str(guest['id']), cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'Continuo aguardando o retorno.', admin_page)
        _, _, admin_csrf = self.csrf('/admin/atendimento-visitante?guest_id=' + str(guest['id']), super_cookie)
        staff_reply = urllib.parse.urlencode({'csrf': admin_csrf, 'guest_id': guest['id'], 'body': 'Olá! Já estamos verificando.'})
        self.assertEqual(self.request('POST', '/admin/atendimento-visitante/responder', staff_reply, cookie=super_cookie)[0], 303)
        with app.db() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM guest_messages WHERE guest_id=? AND sender_role='staff'", (guest['id'],)).fetchone()[0], 1)
        status, _, public_page = self.request('GET', '/atendimento/' + public_token)
        self.assertIn('Olá! Já estamos verificando.'.encode(), public_page)
        _, _, _, regular_cookie = self.login(regular_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/admin/atendimento-visitante?guest_id=' + str(guest['id']), cookie=regular_cookie)[0], 200)
        close_body = urllib.parse.urlencode({'csrf': admin_csrf, 'guest_id': guest['id']})
        self.assertEqual(self.request('POST', '/admin/atendimento-visitante/encerrar', close_body, cookie=super_cookie)[0], 303)
        with app.db() as connection:
            self.assertEqual(connection.execute('SELECT status FROM guest_sessions WHERE id=?', (guest['id'],)).fetchone()[0], 'closed')
        status, _, closed_page = self.request('GET', '/atendimento/' + public_token)
        self.assertIn('Atendimento encerrado'.encode(), closed_page)
        self.assertNotIn(b'Enviar mensagem', closed_page)


    def test_floating_chat_widget_guest_client_and_offline(self):
        super_id, super_email = self.add_user('Super Widget', role='admin')
        client_id, client_email = self.add_user('Cliente Widget')
        with app.SESS_LOCK:
            app.SESS.clear()
        status, data, _ = self.csrf('/')
        self.assertEqual(status, 200)
        self.assertIn(b'chat-widget', data)
        self.assertIn(b'data-chat-online="0"', data)
        csrf_token = re.search(rb'name="csrf-token" content="([^"]+)"', data).group(1).decode()
        origin = 'http://127.0.0.1:' + str(self.port)
        start = urllib.parse.urlencode({'csrf': csrf_token, 'name': 'Visitante Widget', 'email': 'visitante.widget@example.test', 'phone': '(88) 98888-0000', 'consent': '1'})
        status, headers, data = self.request('POST', '/chat/iniciar', start, {'Origin': origin})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)['session'])
        guest_cookie = 'bl_chat=' + self.cookie(headers, 'bl_chat')
        status, _, data = self.request('GET', '/chat/status', cookie=guest_cookie)
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(data)['online'])
        self.assertTrue(json.loads(data)['session'])
        message = urllib.parse.urlencode({'csrf': csrf_token, 'body': 'Mensagem pelo balão do site.'})
        self.assertEqual(self.request('POST', '/chat/mensagem', message, {'Origin': origin}, guest_cookie)[0], 200)
        status, _, data = self.request('GET', '/chat/mensagens', cookie=guest_cookie)
        self.assertIn('Mensagem pelo balão do site.'.encode(), data)
        with app.db() as connection:
            guest = connection.execute("SELECT * FROM guest_sessions WHERE email='visitante.widget@example.test'").fetchone()
            self.assertIsNotNone(guest['contact_id'])
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/chat/status', cookie=guest_cookie)
        self.assertTrue(json.loads(data)['online'])
        status, _, data = self.request('GET', '/admin/chats', cookie=super_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'Visitante Widget', data)
        status, _, data = self.request('GET', '/admin/chats/alertas', cookie=super_cookie)
        alerts = json.loads(data)
        self.assertGreaterEqual(alerts['count'], 1)
        self.assertEqual(alerts['latest']['name'], 'Visitante Widget')
        admin_page = self.request('GET', '/admin', cookie=super_cookie)[2]
        self.assertIn(b'id="staff-chat-alert"', admin_page)
        self.assertIn(b'aria-label="Abrir chat da equipe"', admin_page)
        self.assertNotIn(b'id="staff-chat-alert" data-chat-alert-endpoint="/admin/chats/alertas" hidden', admin_page)
        _, _, admin_csrf = self.csrf('/admin/atendimento-visitante?guest_id=' + str(guest['id']), super_cookie)
        status, _, data = self.request('GET', '/admin/chats/alertas', cookie=super_cookie)
        self.assertEqual(status, 200)
        reply = urllib.parse.urlencode({'csrf': admin_csrf, 'guest_id': guest['id'], 'body': 'Resposta da equipe pelo painel.'})
        self.assertEqual(self.request('POST', '/admin/atendimento-visitante/responder', reply, cookie=super_cookie)[0], 303)
        status, _, data = self.request('GET', '/chat/mensagens', cookie=guest_cookie)
        self.assertIn('Resposta da equipe pelo painel.'.encode(), data)
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        status, data, _ = self.csrf('/cliente', client_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'chat-widget', data)
        _, _, client_csrf = self.csrf('/cliente', client_cookie)
        client_start = urllib.parse.urlencode({'csrf': client_csrf})
        status, _, data = self.request('POST', '/chat/iniciar', client_start, {'Origin': origin}, client_cookie)
        self.assertEqual(status, 200)
        with app.db() as connection:
            client_chat = connection.execute('SELECT * FROM guest_sessions WHERE user_id=?', (client_id,)).fetchone()
            self.assertIsNotNone(client_chat)
        client_message = urllib.parse.urlencode({'csrf': client_csrf, 'body': 'Mensagem do cliente logado.'})
        self.assertEqual(self.request('POST', '/chat/mensagem', client_message, {'Origin': origin}, client_cookie)[0], 200)
        status, _, data = self.request('GET', '/chat/mensagens', cookie=client_cookie)
        self.assertIn('Mensagem do cliente logado.'.encode(), data)
        with app.db() as connection:
            connection.execute("UPDATE settings SET value='0' WHERE key='chat_online'")
        status, _, data = self.request('GET', '/chat/status', cookie=guest_cookie)
        self.assertFalse(json.loads(data)['online'])
        status, _, data = self.request('GET', '/', cookie=guest_cookie)
        self.assertIn(b'data-chat-online="0"', data)
        with app.db() as connection:
            connection.execute("UPDATE settings SET value='1' WHERE key='chat_online'")


    def test_personal_appointment_and_per_event_reminders(self):
        admin_id, admin_email = self.add_user('Admin Agenda Pessoal', role='admin')
        staff_id, staff_email = self.add_user('Advogado Agenda Pessoal', role='staff')
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin/compromissos', admin_cookie)
        body = urllib.parse.urlencode({'csrf': token, 'title': 'Lembrete pessoal de audiência', 'kind': 'pessoal', 'when_at': '2099-03-10T14:00', 'location': 'Escritório', 'owner_id': staff_id, 'reminder_choice': '1h', 'client_id': '', 'case_id': '', 'notes': 'Conferir documentos.'})
        self.assertEqual(self.request('POST', '/admin/appointment', body, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            event = connection.execute("SELECT * FROM appointments WHERE title='Lembrete pessoal de audiência'").fetchone()
        self.assertIsNone(event['client_id'])
        self.assertEqual(event['reminder_choice'], '1h')
        self.assertEqual(event['reminder_at'], '2099-03-10 13:00')
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/admin/compromissos', cookie=staff_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'Lembrete pessoal', data)
        self.assertIn(b'Evento interno', data)
        body = urllib.parse.urlencode({'csrf': token, 'title': 'Lembrete com um dia', 'kind': 'pessoal', 'when_at': '2099-03-11T09:00', 'owner_id': staff_id, 'reminder_choice': '1d', 'client_id': '', 'case_id': ''})
        self.assertEqual(self.request('POST', '/admin/appointment', body, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            event = connection.execute("SELECT * FROM appointments WHERE title='Lembrete com um dia'").fetchone()
        self.assertEqual(event['reminder_at'], '2099-03-10 09:00')
        with app.db() as connection:
            connection.execute("INSERT INTO appointments(client_id,title,when_at,owner_id,created_by,status,reminder_at,reminder_sent,kind,reminder_choice) VALUES(NULL,?,?,?,?,'pendente',?,0,'pessoal','1h')", ('Lembrete disparado', '2099-03-12 10:00', staff_id, admin_id, '2020-01-01 00:00'))
        status, _, data = self.request('GET', '/notificacoes', cookie=staff_cookie)
        payload = json.loads(data.decode('utf-8'))
        self.assertTrue(any(item['title'] == 'Lembrete de compromisso' and 'Lembrete disparado' in item['body'] for item in payload['items']))


    def test_appointment_edit_cancel_delete_and_chat_polling(self):
        admin_id, admin_email = self.add_user('Admin Agenda Edicao', role='admin')
        staff_id, staff_email = self.add_user('Advogado Agenda Edicao', role='staff')
        client_id, client_email = self.add_user('Cliente Agenda Edicao')
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin/compromissos', admin_cookie)
        create = urllib.parse.urlencode({'csrf': token, 'title': 'Evento para editar', 'kind': 'pessoal', 'when_at': '2099-04-10T10:00', 'owner_id': staff_id, 'reminder_choice': '1d', 'client_id': '', 'case_id': ''})
        self.assertEqual(self.request('POST', '/admin/appointment', create, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            appointment = connection.execute("SELECT * FROM appointments WHERE title='Evento para editar'").fetchone()
        status, _, data = self.request('GET', '/admin/compromisso?appointment_id=' + str(appointment['id']), cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Editar evento'.encode(), data)
        update = urllib.parse.urlencode({'csrf': token, 'appointment_id': appointment['id'], 'title': 'Evento atualizado', 'kind': 'prazo', 'when_at': '2099-04-11T11:00', 'owner_id': staff_id, 'reminder_choice': '1h', 'status': 'pendente', 'client_id': '', 'case_id': '', 'notes': 'Atualizado.'})
        self.assertEqual(self.request('POST', '/admin/compromisso/editar', update, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            updated = connection.execute('SELECT * FROM appointments WHERE id=?', (appointment['id'],)).fetchone()
        self.assertEqual(updated['title'], 'Evento atualizado')
        self.assertEqual(updated['reminder_choice'], '1h')
        self.assertEqual(updated['reminder_at'], '2099-04-11 10:00')
        cancel = urllib.parse.urlencode({'csrf': token, 'appointment_id': appointment['id'], 'status': 'cancelado'})
        self.assertEqual(self.request('POST', '/admin/compromisso/status', cancel, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            self.assertEqual(connection.execute('SELECT status FROM appointments WHERE id=?', (appointment['id'],)).fetchone()[0], 'cancelado')
        delete = urllib.parse.urlencode({'csrf': token, 'appointment_id': appointment['id']})
        self.assertEqual(self.request('POST', '/admin/compromisso/excluir', delete, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            deleted = connection.execute('SELECT * FROM appointments WHERE id=?', (appointment['id'],)).fetchone()
        self.assertTrue(deleted['deleted_at'])
        self.assertNotIn('Evento atualizado'.encode(), self.request('GET', '/admin/compromissos', cookie=admin_cookie)[2])

        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title) VALUES(?,?)', (client_id, 'Caso Chat Polling')).lastrowid
            conversation_id = connection.execute("INSERT INTO conversations(client_id,case_id,title,visibility,created_by) VALUES(?,?,?,?,?)", (client_id, case_id, 'Conversa Chat Polling', 'client', admin_id)).lastrowid
            connection.execute("INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,body) VALUES(?,?,?,?,?,?,?)", (client_id, case_id, conversation_id, client_id, 'client', 'client', 'Mensagem do cliente'))
            connection.execute("INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,body) VALUES(?,?,?,?,?,?,?)", (client_id, case_id, conversation_id, admin_id, 'admin', 'client', 'Mensagem do escritório'))
        status, _, data = self.request('GET', '/admin/mensagens?conversa=' + str(conversation_id), cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'data-conversation-endpoint="/conversas/' + str(conversation_id).encode() + b'/mensagens"', data)
        self.assertIn(b'class="message client"', data)
        self.assertIn(b'class="message office"', data)
        status, _, data = self.request('GET', '/conversas/' + str(conversation_id) + '/mensagens', cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'conversation_unread', data)
        self.assertIn('Mensagem do cliente'.encode(), data)
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/cliente/mensagens?conversa=' + str(conversation_id), cookie=client_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'data-conversation-endpoint="/conversas/' + str(conversation_id).encode() + b'/mensagens"', data)


    def test_internal_client_portal_enable_and_multiple_cases(self):
        admin_id, admin_email = self.add_user('Admin Cliente Interno', role='admin')
        staff_id, _ = self.add_user('Advogado Cliente Interno', role='staff')
        _, _, _, cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin/clientes', cookie)
        body = urllib.parse.urlencode({'csrf': token, 'name': 'Cliente Sem Portal', 'phone': '(88) 97777-0000', 'owner_staff_id': staff_id})
        self.assertEqual(self.request('POST', '/admin/cliente/interno', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            client = connection.execute("SELECT * FROM users WHERE name='Cliente Sem Portal'").fetchone()
        self.assertEqual(client['portal_enabled'], 0)
        self.assertTrue(client['email'].endswith('@interno.local'))
        self.assertEqual(self.login(client['email'], 'QualquerSenha123')[0], 401)
        listing = self.request('GET', '/admin/clientes?q=Cliente+Sem+Portal', cookie=cookie)[2]
        self.assertIn('Sem acesso ao portal'.encode(), listing)
        ficha = self.request('GET', '/admin/cliente?client_id=' + str(client['id']), cookie=cookie)[2]
        self.assertIn('Habilitar acesso ao portal'.encode(), ficha)
        enable = urllib.parse.urlencode({'csrf': token, 'client_id': client['id'], 'email': 'cliente.portal@example.test', 'password': 'SenhaPortal123', 'confirm': 'SenhaPortal123'})
        self.assertEqual(self.request('POST', '/admin/cliente/portal', enable, cookie=cookie)[0], 303)
        with app.db() as connection:
            enabled = connection.execute('SELECT * FROM users WHERE id=?', (client['id'],)).fetchone()
        self.assertEqual(enabled['portal_enabled'], 1)
        self.assertEqual(enabled['email'], 'cliente.portal@example.test')
        self.assertEqual(self.login('cliente.portal@example.test', 'SenhaPortal123')[0], 303)
        case_body = urllib.parse.urlencode({'csrf': token, 'client_id': client['id'], 'title': 'Caso interno do cliente', 'case_number': '0001', 'area': 'Civil', 'status': 'Em andamento', 'description': 'Caso cadastrado pela ficha.', 'return_to': '/admin/cliente?client_id=' + str(client['id'])})
        self.assertEqual(self.request('POST', '/admin/caso', case_body, cookie=cookie)[0], 303)
        with app.db() as connection:
            self.assertIsNotNone(connection.execute("SELECT 1 FROM cases WHERE client_id=? AND title='Caso interno do cliente'", (client['id'],)).fetchone())
        self.assertIn(b'Caso interno do cliente', self.request('GET', '/admin/cliente?client_id=' + str(client['id']), cookie=cookie)[2])


    def test_private_internal_and_participant_appointments(self):
        super_id, super_email = self.add_user('Super Privacidade Agenda', role='admin')
        lawyer_id, lawyer_email = self.add_user('Advogado Privacidade Agenda', role='staff')
        other_id, other_email = self.add_user('Outro Advogado Agenda', role='staff')
        _, _, _, lawyer_cookie = self.login(lawyer_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin/compromissos', lawyer_cookie)
        private = urllib.parse.urlencode({'csrf': token, 'title': 'Compromisso privado do advogado', 'kind': 'pessoal', 'privacy': 'private', 'when_at': '2099-05-01T09:00', 'owner_id': lawyer_id, 'reminder_choice': '1d', 'client_id': '', 'case_id': ''})
        self.assertEqual(self.request('POST', '/admin/appointment', private, cookie=lawyer_cookie)[0], 303)
        with app.db() as connection:
            appointment = connection.execute("SELECT * FROM appointments WHERE title='Compromisso privado do advogado'").fetchone()
        self.assertEqual(appointment['privacy'], 'private')
        self.assertIn('Compromisso privado do advogado'.encode(), self.request('GET', '/admin/compromissos', cookie=lawyer_cookie)[2])
        _, _, _, super_cookie = self.login(super_email, 'SenhaSegura123')
        self.assertNotIn('Compromisso privado do advogado'.encode(), self.request('GET', '/admin/compromissos', cookie=super_cookie)[2])
        self.assertEqual(self.request('GET', '/admin/compromisso?appointment_id=' + str(appointment['id']), cookie=super_cookie)[0], 403)
        internal = urllib.parse.urlencode({'csrf': token, 'title': 'Reunião interna da equipe', 'kind': 'reuniao', 'privacy': 'internal', 'when_at': '2099-05-02T10:00', 'owner_id': lawyer_id, 'participant_' + str(other_id): '1', 'reminder_choice': '1h', 'client_id': '', 'case_id': ''})
        self.assertEqual(self.request('POST', '/admin/appointment', internal, cookie=lawyer_cookie)[0], 303)
        with app.db() as connection:
            internal_event = connection.execute("SELECT * FROM appointments WHERE title='Reunião interna da equipe'").fetchone()
            self.assertTrue(connection.execute('SELECT 1 FROM appointment_participants WHERE appointment_id=? AND user_id=?', (internal_event['id'], other_id)).fetchone())
        self.assertIn('Reunião interna da equipe'.encode(), self.request('GET', '/admin/compromissos', cookie=super_cookie)[2])
        self.assertIn('Reunião interna da equipe'.encode(), self.request('GET', '/admin/compromissos', cookie=self.login(other_email, 'SenhaSegura123')[3])[2])

    def test_internal_case_communication_is_separate_from_client(self):
        admin_id, admin_email = self.add_user('Admin Comunicacao Interna', role='admin')
        client_id, client_email = self.add_user('Cliente Comunicacao Interna')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Caso Comunicacao Interna', admin_id)).lastrowid
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin/caso/historico?case_id=' + str(case_id), admin_cookie)
        body = urllib.parse.urlencode({'csrf': token, 'client_id': client_id, 'case_id': case_id, 'visibility': 'internal', 'subject': 'Assunto interno reservado', 'body': 'Mensagem apenas para a equipe.'})
        self.assertEqual(self.request('POST', '/admin/mensagem', body, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            conversation = connection.execute("SELECT * FROM conversations WHERE title='Assunto interno reservado'").fetchone()
        self.assertEqual(conversation['visibility'], 'internal')
        case_page = self.request('GET', '/admin/caso/historico?case_id=' + str(case_id), cookie=admin_cookie)[2]
        self.assertIn('Comunicação interna'.encode(), case_page)
        self.assertIn('Assunto interno reservado'.encode(), case_page)
        self.assertIn(b'Comunica', case_page)
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        self.assertEqual(self.request('GET', '/conversas/' + str(conversation['id']), cookie=client_cookie)[0], 403)
        client_messages = self.request('GET', '/cliente/mensagens', cookie=client_cookie)[2]
        self.assertNotIn('Assunto interno reservado'.encode(), client_messages)
        self.assertNotIn('Mensagem apenas para a equipe.'.encode(), client_messages)


    def test_profile_avatar_cover_and_restore(self):
        client_id, email = self.add_user('Cliente Perfil Imagem')
        _, _, _, cookie = self.login(email, 'SenhaSegura123')
        _, _, token = self.csrf('/perfil', cookie)
        body, headers = self.multipart({'csrf': token, 'name': 'Cliente Perfil Imagem', 'phone': '(88) 90000-0000'}, 'avatar.png', b'\x89PNG\r\n\x1a\nfake-image', 'image/png', 'avatar')
        self.assertEqual(self.request('POST', '/perfil', body, headers, cookie)[0], 303)
        with app.db() as connection:
            row = connection.execute('SELECT avatar FROM users WHERE id=?', (client_id,)).fetchone()
        self.assertTrue(row['avatar'])
        self.assertEqual(self.request('GET', '/perfil/imagem/' + str(client_id) + '/avatar', cookie=cookie)[0], 200)
        body, headers = self.multipart({'csrf': token, 'name': 'Cliente Perfil Imagem', 'remove_avatar': '1'}, '', b'', 'application/octet-stream', 'avatar')
        self.assertEqual(self.request('POST', '/perfil', body, headers, cookie)[0], 303)
        with app.db() as connection:
            self.assertEqual(connection.execute('SELECT avatar FROM users WHERE id=?', (client_id,)).fetchone()[0], '')

    def test_mentions_and_message_to_task_conversion(self):
        admin_id, admin_email = self.add_user('Admin Mencao', role='admin')
        mentioned_id, _ = self.add_user('Advogado Mencionado', role='staff')
        client_id, _ = self.add_user('Cliente Mencao')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title,responsible_id) VALUES(?,?,?)', (client_id, 'Caso Mencao', admin_id)).lastrowid
        _, _, _, cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin/caso/historico?case_id=' + str(case_id), cookie)
        body = urllib.parse.urlencode({'csrf': token, 'client_id': client_id, 'case_id': case_id, 'visibility': 'internal', 'subject': 'Mensagem com menção', 'body': '@Advogado Mencionado favor revisar o prazo.'})
        self.assertEqual(self.request('POST', '/admin/mensagem', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            message = connection.execute("SELECT * FROM messages WHERE body LIKE '%favor revisar%'").fetchone()
            mention = connection.execute('SELECT * FROM message_mentions WHERE message_id=? AND user_id=?', (message['id'], mentioned_id)).fetchone()
            notice = connection.execute("SELECT * FROM notifications WHERE user_id=? AND type='mention'", (mentioned_id,)).fetchone()
        self.assertIsNotNone(mention)
        self.assertIsNotNone(notice)
        status, _, data = self.request('GET', '/admin/tarefa/nova?message_id=' + str(message['id']), cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Transformar mensagem em tarefa'.encode(), data)
        task_body = urllib.parse.urlencode({'csrf': token, 'source_message_id': message['id'], 'title': 'Revisar prazo mencionado', 'description': message['body'], 'client_id': client_id, 'case_id': case_id, 'priority': 'alta', 'assigned_to': mentioned_id})
        self.assertEqual(self.request('POST', '/admin/tarefa', task_body, cookie=cookie)[0], 303)
        with app.db() as connection:
            task = connection.execute("SELECT * FROM tasks WHERE title='Revisar prazo mencionado'").fetchone()
        self.assertEqual(task['source_message_id'], message['id'])
        self.assertEqual(task['case_id'], case_id)

    def test_menu_groups_super_routine_and_responsible_options(self):
        admin_id, admin_email = self.add_user('Admin Menu', role='admin')
        extra_admin_id, _ = self.add_user('Outro Admin Responsavel', role='admin')
        _, _, _, cookie = self.login(admin_email, 'SenhaSegura123')
        status, _, data = self.request('GET', '/admin', cookie=cookie)
        self.assertEqual(status, 200)
        for label in ('Atendimentos', 'Agenda e Gestão', 'Documentos', 'Configurações'):
            self.assertIn(label.encode(), data)
        status, _, data = self.request('GET', '/admin?visao=minha', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Minha rotina'.encode(), data)
        clients_page = self.request('GET', '/admin/clientes', cookie=cookie)[2]
        self.assertIn('Outro Admin Responsavel'.encode(), clients_page)


    def test_team_chat_mentions_and_read_state(self):
        admin_id, admin_email = self.add_user('Admin Chat Equipe', role='admin')
        staff_id, staff_email = self.add_user('Advogado Chat Equipe', role='staff')
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        status, _, page = self.request('GET', '/admin/chat-equipe', cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Chat da equipe'.encode(), page)
        _, _, token = self.csrf('/admin/chat-equipe', admin_cookie)
        body = urllib.parse.urlencode({'csrf': token, 'body': '@Advogado Chat Equipe veja o andamento do caso.'})
        self.assertEqual(self.request('POST', '/admin/chat-equipe', body, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            message = connection.execute("SELECT * FROM team_chat_messages WHERE body LIKE '%andamento%'").fetchone()
            mention = connection.execute('SELECT * FROM team_chat_mentions WHERE message_id=? AND user_id=?', (message['id'], staff_id)).fetchone()
            notice = connection.execute("SELECT * FROM notifications WHERE user_id=? AND type='mention'", (staff_id,)).fetchone()
        self.assertIsNotNone(message)
        self.assertIsNotNone(mention)
        self.assertIsNotNone(notice)
        _, _, _, staff_cookie = self.login(staff_email, 'SenhaSegura123')
        status, _, page = self.request('GET', '/admin/chat-equipe', cookie=staff_cookie)
        self.assertEqual(status, 200)
        self.assertIn('veja o andamento do caso'.encode(), page)
        status, _, data = self.request('GET', '/admin/chat-equipe/mensagens', cookie=staff_cookie)
        self.assertEqual(status, 200)
        self.assertIn(b'team-message', data)

    def test_task_collaborators_subtasks_and_document_link(self):
        admin_id, admin_email = self.add_user('Admin Tarefa Completa', role='admin')
        collaborator_id, _ = self.add_user('Colaborador Tarefa', role='staff')
        client_id, _ = self.add_user('Cliente Tarefa Completa')
        with app.db() as connection:
            case_id = connection.execute('INSERT INTO cases(client_id,title) VALUES(?,?)', (client_id, 'Caso Tarefa Completa')).lastrowid
        document_id = self.add_document(client_id, 'documento-tarefa.txt', b'conteudo', case_id=case_id)
        _, _, _, cookie = self.login(admin_email, 'SenhaSegura123')
        _, _, token = self.csrf('/admin/tarefas', cookie)
        body = urllib.parse.urlencode({'csrf': token, 'title': 'Tarefa com colaborador', 'description': 'Teste.', 'client_id': client_id, 'case_id': case_id, 'assigned_to': admin_id, 'collaborator_' + str(collaborator_id): '1', 'document_id': document_id, 'priority': 'alta'})
        self.assertEqual(self.request('POST', '/admin/tarefa', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            task = connection.execute("SELECT * FROM tasks WHERE title='Tarefa com colaborador'").fetchone()
            self.assertEqual(task['document_id'], document_id)
            self.assertTrue(connection.execute('SELECT 1 FROM task_collaborators WHERE task_id=? AND user_id=?', (task['id'], collaborator_id)).fetchone())
        status, _, page = self.request('GET', '/admin/tarefa?task_id=' + str(task['id']), cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Subtarefas'.encode(), page)
        body = urllib.parse.urlencode({'csrf': token, 'task_id': task['id'], 'operation': 'add', 'title': 'Subtarefa nova'})
        self.assertEqual(self.request('POST', '/admin/tarefa/subtarefa', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            subtask = connection.execute('SELECT * FROM task_subtasks WHERE task_id=?', (task['id'],)).fetchone()
        self.assertEqual(subtask['title'], 'Subtarefa nova')
        body = urllib.parse.urlencode({'csrf': token, 'task_id': task['id'], 'subtask_id': subtask['id'], 'operation': 'toggle'})
        self.assertEqual(self.request('POST', '/admin/tarefa/subtarefa', body, cookie=cookie)[0], 303)
        with app.db() as connection:
            self.assertEqual(connection.execute('SELECT completed FROM task_subtasks WHERE id=?', (subtask['id'],)).fetchone()[0], 1)


    def test_faq_categories_expandable_admin_and_scam_notices(self):
        admin_id, admin_email = self.add_user('Admin FAQ Categorias', role='admin')
        client_id, client_email = self.add_user('Cliente FAQ Categorias')
        status, _, public_faq = self.request('GET', '/faq')
        self.assertEqual(status, 200)
        for category in ('Atendimento e contratação', 'Processos e acompanhamento jurídico', 'Área do cliente', 'Segurança e privacidade'):
            self.assertIn(category.encode(), public_faq)
        self.assertIn(b'faq-item', public_faq)
        self.assertIn('Não encontrou a resposta que procurava?'.encode(), public_faq)
        self.assertIn('ATENÇÃO AOS GOLPES!'.encode(), public_faq)
        self.assertIn('ATENÇÃO AOS GOLPES!'.encode(), self.request('GET', '/contato')[2])
        _, _, _, client_cookie = self.login(client_email, 'SenhaSegura123')
        self.assertIn('ATENÇÃO AOS GOLPES!'.encode(), self.request('GET', '/cliente', cookie=client_cookie)[2])
        _, _, _, admin_cookie = self.login(admin_email, 'SenhaSegura123')
        status, _, admin_page = self.request('GET', '/admin/faq', cookie=admin_cookie)
        self.assertEqual(status, 200)
        self.assertIn('Segurança e privacidade'.encode(), admin_page)
        _, _, token = self.csrf('/admin/faq', admin_cookie)
        with app.db() as connection:
            faq = connection.execute("SELECT * FROM faqs WHERE question='Como acesso minha Área do Cliente?'").fetchone()
        body = urllib.parse.urlencode({'csrf': token, 'faq_id': faq['id'], 'category': 'Área do cliente', 'question': 'Pergunta editada no painel', 'answer': 'Resposta editada e publicada.', 'sort_order': '1', 'published': '1'})
        self.assertEqual(self.request('POST', '/admin/faq/editar', body, cookie=admin_cookie)[0], 303)
        with app.db() as connection:
            updated = connection.execute('SELECT * FROM faqs WHERE id=?', (faq['id'],)).fetchone()
        self.assertEqual(updated['question'], 'Pergunta editada no painel')
        self.assertEqual(updated['published'], 1)
        public_page = self.request('GET', '/faq')[2]
        self.assertIn('Pergunta editada no painel'.encode(), public_page)
        unpublish = urllib.parse.urlencode({'csrf': token, 'faq_id': faq['id'], 'category': 'Área do cliente', 'question': 'Pergunta editada no painel', 'answer': 'Resposta editada e publicada.', 'sort_order': '1'})
        self.assertEqual(self.request('POST', '/admin/faq/editar', unpublish, cookie=admin_cookie)[0], 303)
        self.assertNotIn('Pergunta editada no painel'.encode(), self.request('GET', '/faq')[2])


if __name__ == '__main__':
    unittest.main()
