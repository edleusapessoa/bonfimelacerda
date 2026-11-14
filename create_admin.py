"""Cria uma conta de super administrador LOCAL, sem credenciais fixas no repositório."""
import getpass
import sqlite3
from app import init, db, pwd, EMAIL_RE

init()
name = input('Nome do administrador: ').strip()
email = input('E-mail: ').strip().lower()
password = getpass.getpass('Senha (mínimo 12 caracteres): ')
confirm = getpass.getpass('Confirme a senha: ')
if not name or not EMAIL_RE.match(email):
    raise SystemExit('Nome ou e-mail inválidos.')
if len(password) < 12 or len(password) > 256:
    raise SystemExit('A senha deve ter entre 12 e 256 caracteres.')
if password != confirm:
    raise SystemExit('A confirmação da senha não confere.')
try:
    with db() as c:
        c.execute('INSERT INTO users(name,email,password,role,is_super) VALUES(?,?,?,?,1)', (name, email, pwd(password), 'admin'))
except sqlite3.IntegrityError:
    raise SystemExit('E-mail já cadastrado. Escolha outro ou redefina a senha pelo painel.')
print('Super administrador cadastrado. Execute python app.py para iniciar.')
