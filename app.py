"""Bomfim & Lacerda — aplicação local de testes (não publicar na Internet)."""
import os, sys, sqlite3, secrets, hashlib, hmac, html, mimetypes, urllib.parse, datetime, calendar, threading, time, re, shutil, traceback, subprocess, json, zipfile, csv, io, base64, socket
from contextlib import contextmanager
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from email.parser import BytesParser
from email.policy import default


def _load_env_file():
    if os.getenv('APP_ENV') == 'test':
        return
    env_file = Path(__file__).resolve().parent / '.env'
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

import db_compat
from db_compat import IS_POSTGRES, IntegrityError

ROOT = Path(__file__).resolve().parent
DB = Path(os.getenv('APP_DB', str(ROOT / 'private' / 'app.db'))).resolve()
if db_compat.SQLITE_URL_PATH:
    sqlite_db = db_compat.SQLITE_URL_PATH
    if not sqlite_db.is_absolute():
        sqlite_db = ROOT / sqlite_db
    DB = sqlite_db.resolve()
UP = Path(os.getenv('APP_UPLOADS', str(ROOT / 'private' / 'uploads'))).resolve()
UP.mkdir(parents=True, exist_ok=True)
DB.parent.mkdir(parents=True, exist_ok=True)

MAX_BODY = 12 * 1024 * 1024
MAX_FILE = 10 * 1024 * 1024
MAX_CLIENT_STORAGE = int(os.getenv('MAX_CLIENT_STORAGE', str(100 * 1024 * 1024)))
SESSION_IDLE = int(os.getenv('SESSION_IDLE', '1800'))
SESSION_TTL = int(os.getenv('SESSION_TTL', '43200'))
COOKIE_SECURE = os.getenv('COOKIE_SECURE', '0') == '1'
PUBLIC_ORIGIN = os.getenv('PUBLIC_ORIGIN', '').rstrip('/')
TRUST_PROXY = os.getenv('TRUST_PROXY', '0') == '1'
SCRYPT_N = int(os.getenv('SCRYPT_N', str(2 ** 16)))
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 256 * 1024 * 1024
LOGIN_IP_LIMIT = int(os.getenv('LOGIN_IP_LIMIT', '10'))
LOGIN_EMAIL_LIMIT = int(os.getenv('LOGIN_EMAIL_LIMIT', '5'))
LOGIN_WINDOW = int(os.getenv('LOGIN_WINDOW', '900'))
CONTACT_LIMIT = int(os.getenv('CONTACT_LIMIT', '5'))
CONTACT_WINDOW = int(os.getenv('CONTACT_WINDOW', '900'))
REGISTER_LIMIT = int(os.getenv('REGISTER_LIMIT', '5'))
REGISTER_WINDOW = int(os.getenv('REGISTER_WINDOW', '3600'))
CLAMSCAN = os.getenv('CLAMSCAN', '')
CSRF_SECRET = secrets.token_bytes(32)
CSRF_PLACEHOLDER = '\x00csrf\x00'
SESS = {}
SESS_LOCK = threading.RLock()
MFA_CHALLENGES = {}
MFA_LOCK = threading.RLock()
MFA_TTL = 300
_LAST_CLEAN = [0.0]
RL = {}
RL_LOCK = threading.Lock()

AREAS = [('Direito Previdenciário', 'Aposentadorias, benefícios previdenciários, revisões e orientações sobre requerimentos.'), ('Direito Civil', 'Obrigações, contratos e demandas de natureza civil.'), ('Direito Trabalhista', 'Orientação e atuação em questões decorrentes das relações de trabalho.'), ('Direito do Consumidor', 'Orientação sobre direitos e conflitos nas relações de consumo.'), ('Família e Sucessões', 'Questões familiares, inventários, divórcios, guarda e partilha.'), ('Direito Empresarial', 'Orientação jurídica para empresas e negócios.'), ('Direito Tributário', 'Orientação e defesa em questões tributárias.'), ('Direito Administrativo', 'Questões relativas à Administração Pública e procedimentos administrativos.')]
TEAM=[('Dr. João Alves de Lacerda','OAB/CE 4.214','founders_portrait.webp'),('Rozária Neta Bomfim Lacerda','OAB/CE 4.224','founders_portrait.webp'),('Joatan Bonfim Lacerda','OAB/CE 17.307','portrait_joatan.webp'),('João Joab Bonfim Lacerda','OAB/CE 10.903','portrait_joaojoab.webp'),('Ninmery Ranya Lacerda Rached','OAB/CE 41.507','portrait_ninmery.webp'),('Sintia Amaro Sales','OAB/CE 32.071','portrait_sintia.webp')]
TEAM_DETAILS = [
    {'slug': 'joao-alves-de-lacerda', 'role': 'Advogado · Fundador', 'material': 1, 'bio': 'Ao lado de Rozária, João Alves de Lacerda fundou o escritório que, há mais de 40 anos, reúne a família em torno do compromisso com o Direito e com as pessoas. Pai de Joatan e João Joab e avô de Ninmery, faz parte das raízes de uma história que continua em novas gerações. Sua trajetória inspira uma advocacia pautada pela ética, pela responsabilidade e pelo respeito a cada cliente.', 'email': 'rozaria.joaoadvogados@hotmail.com', 'phone': '(88) 99802-2020'},
    {'slug': 'rozaria-neta-bomfim-lacerda', 'role': 'Advogada · Fundadora', 'material': 1, 'bio': 'Rozária Neta Bomfim Lacerda construiu, junto com João, os alicerces de um escritório que atravessa gerações. Mãe de Joatan e João Joab e avó de Ninmery, integra uma família que encontrou no Direito uma forma de servir e cuidar das pessoas. Sua história representa o valor da escuta, da confiança e da dedicação que orientam o trabalho da equipe.', 'email': 'rozaria.joaoadvogados@hotmail.com', 'phone': '(88) 99802-2221'},
    {'slug': 'joatan-bonfim-lacerda', 'role': 'Advogado', 'material': 2, 'bio': 'Filho dos fundadores João e Rozária, Joatan Bonfim Lacerda dá continuidade à trajetória construída por sua família. Em sua atuação, alia o compromisso com a ética à atenção às necessidades de cada pessoa, buscando oferecer orientação clara e cuidadosa. Seu trabalho abrange as áreas Civil, Trabalhista, Previdenciária e do Consumidor.', 'email': 'jbldireito@gmail.com', 'phone': '(88) 99802-2089'},
    {'slug': 'joao-joab-bonfim-lacerda', 'role': 'Advogado', 'material': 3, 'bio': 'João Joab Bonfim Lacerda é filho de João e Rozária e integra a geração que segue construindo a história do escritório. Sua atuação reúne responsabilidade, atenção aos detalhes e o compromisso de explicar cada caminho com clareza. Trabalha nas áreas Civil, Trabalhista, Previdenciária e do Consumidor, respeitando a história de cada cliente.', 'email': '', 'phone': '(88) 99696-2015'},
    {'slug': 'ninmery-ranya-lacerda-rached', 'role': 'Advogada', 'material': 4, 'bio': 'Neta dos fundadores, Ninmery Ranya Lacerda Rached representa a continuidade de uma história familiar dedicada à advocacia. Ao lado da equipe, contribui com um olhar atento e acolhedor, preservando os valores que unem as gerações do escritório. Sua atuação abrange as áreas Civil, Trabalhista, Previdenciária e do Consumidor.', 'email': '', 'phone': '(88) 99664-8636'},
    {'slug': 'sintia-amaro-sales', 'role': 'Advogada associada', 'material': 5, 'bio': 'Advogada associada, Sintia Amaro Sales soma sua dedicação à equipe Bomfim & Lacerda. Compartilha o compromisso de ouvir com atenção, orientar com clareza e conduzir cada demanda com responsabilidade. Sua atuação abrange as áreas Civil, Trabalhista, Previdenciária e do Consumidor.', 'email': 'sintiaasales@gmail.com', 'phone': '(85) 99748-7879'},
]
TEAM_AREAS = ('Direito Civil', 'Direito Trabalhista', 'Direito Previdenciário', 'Direito do Consumidor')
FAQ_CATEGORIES = ('Atendimento e contratação', 'Processos e acompanhamento jurídico', 'Área do cliente', 'Segurança e privacidade')
FAQ_SEED = [
    ('Atendimento e contratação', 'Como posso agendar um atendimento?', 'Você pode entrar em contato com nossa equipe pelos canais oficiais disponibilizados no site, pelo WhatsApp ou pelo chat de atendimento.', 1),
    ('Atendimento e contratação', 'Preciso agendar um horário para ser atendido?', 'Recomendamos o agendamento prévio para oferecer um atendimento adequado, organizado e individualizado.', 2),
    ('Atendimento e contratação', 'O escritório realiza atendimento on-line?', 'Sim. Realizamos atendimentos pelo WhatsApp e demais canais oficiais. Quando houver necessidade de uma análise mais aprofundada ou conversa diretamente com um advogado, poderá ser agendado um atendimento individualizado.', 3),
    ('Atendimento e contratação', 'Quais são as áreas de atuação do escritório?', 'Atuamos em diversas áreas do Direito, com destaque para o Direito Previdenciário, Trabalhista e Civil, entre outras. Consulte a seção Áreas de Atuação para mais informações.', 4),
    ('Atendimento e contratação', 'Quais documentos devo apresentar no primeiro atendimento?', 'Recomendamos apresentar seus documentos pessoais e aqueles relacionados à situação. A documentação necessária será avaliada individualmente, conforme cada caso, podendo ser solicitados documentos complementares.', 5),
    ('Processos e acompanhamento jurídico', 'Como posso acompanhar meu processo?', 'Você pode entrar em contato com nossa equipe ou realizar uma consulta pública no sistema eletrônico do tribunal em que o processo tramita, quando disponível. Clientes cadastrados também podem consultar informações eventualmente disponibilizadas na Área do Cliente.', 1),
    ('Processos e acompanhamento jurídico', 'Quanto tempo demora um processo judicial?', 'Não existe um prazo único. A duração depende da natureza da ação, da complexidade do caso, das etapas processuais e do andamento perante os órgãos responsáveis.', 2),
    ('Processos e acompanhamento jurídico', 'Como serei informado sobre novidades no meu processo?', 'O escritório entrará em contato quando houver acontecimentos relevantes, como solicitações de documentos, audiências, decisões importantes ou conclusão do processo. Nem toda movimentação exige comunicação individual. Mantenha seus dados atualizados e procure nossa equipe sempre que desejar informações sobre seu processo.', 3),
    ('Processos e acompanhamento jurídico', 'É possível garantir o resultado de um processo?', 'Não. O resultado depende dos fatos, das provas, da legislação e das decisões das autoridades competentes. Atuamos com responsabilidade, dedicação e comprometimento, sem garantir resultados.', 4),
    ('Área do cliente', 'Como acesso minha Área do Cliente?', 'Selecione a opção Área do Cliente no site e informe suas credenciais de acesso.', 1),
    ('Área do cliente', 'Ainda não tenho acesso ao portal. O que devo fazer?', 'Realize seu cadastro diretamente pelo site, acessando a Área do Cliente e selecionando a opção de cadastro. Caso tenha dificuldades, procure nossa equipe.', 2),
    ('Área do cliente', 'Posso enviar documentos pelo portal?', 'Sim. A Área do Cliente permite enviar documentos relacionados ao seu atendimento.', 3),
    ('Área do cliente', 'Posso conversar com o escritório pelo portal?', 'Sim. Utilize o canal de comunicação disponível em sua área exclusiva.', 4),
    ('Área do cliente', 'Esqueci minha senha. Como recuperá-la?', 'Entre em contato com nossa equipe pelos canais oficiais para receber orientações sobre a recuperação do acesso.', 5),
    ('Segurança e privacidade', 'Minhas informações são mantidas em sigilo?', 'Sim. O escritório observa o sigilo profissional e a legislação de proteção de dados pessoais, tratando as informações com responsabilidade, segurança e confidencialidade.', 1),
    ('Segurança e privacidade', 'Como posso confirmar se um contato realmente pertence ao escritório?', 'Sempre confirme a autenticidade dos contatos, mesmo que utilizem nomes, fotografias de nossos profissionais ou informações sobre seu processo. Verifique se correspondem aos canais oficiais do site. Em caso de dúvida, interrompa a conversa e procure diretamente nossa equipe antes de compartilhar informações, documentos ou realizar pagamentos.', 2),
    ('Segurança e privacidade', 'O escritório solicita pagamentos por mensagens?', 'Confirme sempre com nossa equipe, pelos canais oficiais, a autenticidade da solicitação, sua finalidade e os dados do beneficiário. Nunca realize pagamentos, transferências ou Pix sem confirmação prévia.', 3),
]
ADDRESSES = ['Rua João Facundes Bonfim, 74, sala 07, Centro — Independência/CE (Centro Comercial Bonfim Lacerda)', 'Rua Coronel Lucio, 414, sala 10, Shopping Bonfim Lacerda, Centro — Crateús/CE', 'Rua Marechal Deodoro, 1365, apartamento 204, Bloco B, Bairro Benfica — Fortaleza/CE', 'Av. Odilon Aguiar, 365, Centro — Tauá/CE', 'Rua 25 de Julho, Centro — Pimenteiras/PI (Posto JJ)']
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')


class ValidationError(Exception):
    pass


@contextmanager
def db():
    c = db_compat.connect(DB)
    try:
        with c:
            yield c
    finally:
        c.close()


def ensure_column(c, table, column, decl):
    cols = {row['name'] for row in db_compat.table_columns(c, table)}
    if column not in cols:
        c.execute('ALTER TABLE ' + table + ' ADD COLUMN ' + column + ' ' + decl)


def migrate_appointments_nullable(c):
    if IS_POSTGRES:
        return
    info = db_compat.table_columns(c, 'appointments')
    client_column = next((row for row in info if row['name'] == 'client_id'), None)
    if not client_column or not client_column['notnull']:
        return
    c.execute("""CREATE TABLE appointments_new(
        id INTEGER PRIMARY KEY,
        client_id INTEGER REFERENCES users(id),
        case_id INTEGER REFERENCES cases(id),
        title TEXT NOT NULL,
        when_at TEXT NOT NULL,
        notes TEXT DEFAULT '',
        created_by INTEGER REFERENCES users(id),
        status TEXT NOT NULL DEFAULT 'pendente',
        reminder_at TEXT DEFAULT '',
        reminder_sent INTEGER NOT NULL DEFAULT 0,
        created TEXT DEFAULT CURRENT_TIMESTAMP,
        kind TEXT DEFAULT 'compromisso',
        owner_id INTEGER REFERENCES users(id),
        location TEXT DEFAULT '',
        reminder_choice TEXT NOT NULL DEFAULT 'global'
    )""")
    c.execute("""INSERT INTO appointments_new(id,client_id,case_id,title,when_at,notes,created_by,status,reminder_at,reminder_sent,created,kind,owner_id,location,reminder_choice)
        SELECT id,client_id,case_id,title,when_at,notes,created_by,status,reminder_at,reminder_sent,created,kind,owner_id,location,reminder_choice FROM appointments""")
    c.execute('DROP TABLE appointments')
    c.execute('ALTER TABLE appointments_new RENAME TO appointments')
    c.execute('CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status,when_at)')


SCHEMA_VERSION = 21


def schema_version():
    with db() as c:
        if IS_POSTGRES:
            c.execute("SELECT pg_advisory_xact_lock(hashtext('bomfim_lacerda_schema'))")
        c.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        row = c.execute('SELECT MAX(version) FROM schema_migrations').fetchone()
    return row[0] if row and row[0] else 0


def backup_before_migration(current_version):
    backup_dir = DB.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    if IS_POSTGRES:
        target = backup_dir / f'postgres-v{current_version}-to-v{SCHEMA_VERSION}-{stamp}.dump'
        pg_dump = shutil.which('pg_dump')
        if pg_dump:
            subprocess.run([pg_dump, '--dbname', db_compat.DATABASE_URL, '--format=custom', '--file', str(target)], check=False)
        return target
    target = backup_dir / f'app-v{current_version}-to-v{SCHEMA_VERSION}-{stamp}.db'
    source = sqlite3.connect(DB)
    destination = sqlite3.connect(target)
    try:
        with destination:
            source.backup(destination)
    finally:
        destination.close()
        source.close()
    if UP.exists() and any(p.is_file() for p in UP.rglob('*')):
        zip_target = backup_dir / f'uploads-v{current_version}-to-v{SCHEMA_VERSION}-{stamp}.zip'
        try:
            with zipfile.ZipFile(zip_target, 'w', zipfile.ZIP_DEFLATED) as archive:
                for p in UP.rglob('*'):
                    if p.is_file():
                        archive.write(p, p.relative_to(UP))
        except Exception:
            pass
    return target


def init():
    current_version = schema_version()
    existed = current_version > 0 if IS_POSTGRES else (DB.exists() and DB.stat().st_size > 0)
    fresh_postgres = IS_POSTGRES and current_version == 0
    if existed and current_version < SCHEMA_VERSION:
        backup_before_migration(current_version)
    with db() as c:
        if IS_POSTGRES:
            c.execute("SELECT pg_advisory_xact_lock(hashtext('bomfim_lacerda_init'))")
        else:
            c.execute('PRAGMA journal_mode=WAL')
        c.executescript(db_compat.postgres_schema("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','staff','client')),active INTEGER NOT NULL DEFAULT 1,must_change INTEGER NOT NULL DEFAULT 0,is_super INTEGER NOT NULL DEFAULT 0,portal_enabled INTEGER NOT NULL DEFAULT 1,phone TEXT DEFAULT '',avatar TEXT DEFAULT '',cover TEXT DEFAULT '',created_by INTEGER,owner_staff_id INTEGER,deleted_at TEXT DEFAULT '',deleted_by INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,original_title TEXT DEFAULT '',case_number TEXT DEFAULT '',area TEXT DEFAULT '',status TEXT DEFAULT 'Em andamento',description TEXT DEFAULT '',responsible_id INTEGER REFERENCES users(id),created_by INTEGER REFERENCES users(id),source TEXT DEFAULT 'interno',last_activity_at TEXT DEFAULT '',deleted_at TEXT DEFAULT '',deleted_by INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS case_assignments(id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,staff_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,created TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(case_id,staff_id));
CREATE TABLE IF NOT EXISTS case_events(id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,actor_id INTEGER REFERENCES users(id),event_type TEXT NOT NULL,description TEXT DEFAULT '',from_status TEXT DEFAULT '',to_status TEXT DEFAULT '',old_title TEXT DEFAULT '',new_title TEXT DEFAULT '',visible_to_client INTEGER NOT NULL DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS updates(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES users(id),case_id INTEGER REFERENCES cases(id),title TEXT NOT NULL,body TEXT NOT NULL,author_id INTEGER REFERENCES users(id),seen_by_client INTEGER NOT NULL DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY,client_id INTEGER REFERENCES users(id),case_id INTEGER REFERENCES cases(id),title TEXT NOT NULL,when_at TEXT NOT NULL,notes TEXT DEFAULT '',created_by INTEGER REFERENCES users(id),status TEXT NOT NULL DEFAULT 'pendente',reminder_at TEXT DEFAULT '',reminder_sent INTEGER NOT NULL DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP,kind TEXT DEFAULT 'compromisso',owner_id INTEGER REFERENCES users(id),location TEXT DEFAULT '',reminder_choice TEXT NOT NULL DEFAULT 'global',deleted_at TEXT DEFAULT '',deleted_by INTEGER,privacy TEXT NOT NULL DEFAULT 'client');
CREATE TABLE IF NOT EXISTS appointment_participants(id INTEGER PRIMARY KEY,appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,created TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(appointment_id,user_id));
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES users(id),case_id INTEGER REFERENCES cases(id),subject TEXT NOT NULL,body TEXT NOT NULL,response TEXT DEFAULT '',status TEXT DEFAULT 'Pendente',responded_by INTEGER REFERENCES users(id),responded_at TEXT DEFAULT '',last_activity_at TEXT DEFAULT '',created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES users(id),case_id INTEGER REFERENCES cases(id),filename TEXT NOT NULL,stored TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,source TEXT NOT NULL,uploaded_by INTEGER REFERENCES users(id),reviewed INTEGER NOT NULL DEFAULT 0,seen_by_client INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'aguardando_analise',analysis_notes TEXT DEFAULT '',reviewed_by INTEGER REFERENCES users(id),reviewed_at TEXT DEFAULT '',deleted_at TEXT DEFAULT '',deleted_by INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES users(id),case_id INTEGER REFERENCES cases(id),sender_id INTEGER REFERENCES users(id),sender_role TEXT NOT NULL,visibility TEXT NOT NULL DEFAULT 'client',reveal_identity INTEGER NOT NULL DEFAULT 0,body TEXT NOT NULL,read_by_client INTEGER NOT NULL DEFAULT 0,read_by_staff INTEGER NOT NULL DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,body TEXT NOT NULL,published INTEGER NOT NULL DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS faqs(id INTEGER PRIMARY KEY,question TEXT NOT NULL,answer TEXT NOT NULL,published INTEGER NOT NULL DEFAULT 0,category TEXT DEFAULT 'Geral',sort_order INTEGER NOT NULL DEFAULT 0,updated TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL,message TEXT NOT NULL,ip TEXT DEFAULT '',consent INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'novo',responsible_id INTEGER REFERENCES users(id) ON DELETE SET NULL,updated TEXT DEFAULT '',created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT NOT NULL,detail TEXT NOT NULL,ip TEXT DEFAULT '',user_agent TEXT DEFAULT '',entity TEXT DEFAULT '',entity_id INTEGER,client_id INTEGER,case_id INTEGER,before TEXT DEFAULT '',after TEXT DEFAULT '',created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY,staff_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,created TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(staff_id,client_id));
CREATE TABLE IF NOT EXISTS permissions(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,action TEXT NOT NULL,allowed INTEGER NOT NULL DEFAULT 0,created_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,action));
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT,updated_by INTEGER,updated_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,client_id INTEGER,case_id INTEGER,type TEXT NOT NULL,title TEXT NOT NULL,body TEXT DEFAULT '',url TEXT DEFAULT '',dedupe_key TEXT DEFAULT '',read_at TEXT DEFAULT '',created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS pendencies(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES users(id),case_id INTEGER REFERENCES cases(id),created_by INTEGER REFERENCES users(id),title TEXT NOT NULL,description TEXT DEFAULT '',status TEXT NOT NULL DEFAULT 'Aberta',due_at TEXT DEFAULT '',received_at TEXT DEFAULT '',reviewed_by INTEGER REFERENCES users(id),reviewed_at TEXT DEFAULT '',review_notes TEXT DEFAULT '',document_id INTEGER REFERENCES documents(id),visible_to_client INTEGER NOT NULL DEFAULT 1,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY,client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,title TEXT NOT NULL,visibility TEXT NOT NULL CHECK(visibility IN ('client','internal')),status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed','legacy')),created_by INTEGER REFERENCES users(id),closed_by INTEGER REFERENCES users(id),closed_at TEXT DEFAULT '',created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS message_reads(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,read_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,message_id));
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,description TEXT DEFAULT '',client_id INTEGER REFERENCES users(id),case_id INTEGER REFERENCES cases(id),assigned_to INTEGER REFERENCES users(id),created_by INTEGER REFERENCES users(id),due_at TEXT DEFAULT '',priority TEXT NOT NULL DEFAULT 'normal' CHECK(priority IN ('normal','alta','urgente')),status TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente','em_andamento','concluida')),completed_at TEXT DEFAULT '',source_message_id INTEGER REFERENCES messages(id),document_id INTEGER REFERENCES documents(id),created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS internal_documents(id INTEGER PRIMARY KEY,title TEXT NOT NULL,category TEXT DEFAULT '',client_id INTEGER REFERENCES users(id),case_id INTEGER REFERENCES cases(id),filename TEXT NOT NULL,stored TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,uploaded_by INTEGER REFERENCES users(id),visibility TEXT NOT NULL DEFAULT 'equipe' CHECK(visibility IN ('equipe','caso')),created TEXT DEFAULT CURRENT_TIMESTAMP,deleted_at TEXT DEFAULT '',deleted_by INTEGER);
CREATE TABLE IF NOT EXISTS message_attachments(id INTEGER PRIMARY KEY,message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,filename TEXT NOT NULL,stored TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,uploaded_by INTEGER REFERENCES users(id),created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS guest_sessions(id INTEGER PRIMARY KEY,contact_id INTEGER REFERENCES contacts(id),user_id INTEGER REFERENCES users(id),token_hash TEXT UNIQUE NOT NULL,name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT DEFAULT '',consent INTEGER NOT NULL DEFAULT 0,ip TEXT DEFAULT '',user_agent TEXT DEFAULT '',status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP,last_seen TEXT DEFAULT '',expires_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS guest_messages(id INTEGER PRIMARY KEY,guest_id INTEGER NOT NULL REFERENCES guest_sessions(id) ON DELETE CASCADE,sender_role TEXT NOT NULL CHECK(sender_role IN ('guest','staff')),sender_id INTEGER REFERENCES users(id),body TEXT NOT NULL,read_by_staff INTEGER NOT NULL DEFAULT 0,read_by_guest INTEGER NOT NULL DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS message_mentions(id INTEGER PRIMARY KEY,message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,created TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(message_id,user_id));
CREATE TABLE IF NOT EXISTS team_chat_messages(id INTEGER PRIMARY KEY,sender_id INTEGER NOT NULL REFERENCES users(id),body TEXT DEFAULT '',attachment_filename TEXT DEFAULT '',attachment_stored TEXT DEFAULT '',attachment_mime TEXT DEFAULT '',attachment_size INTEGER NOT NULL DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS team_chat_reads(message_id INTEGER NOT NULL REFERENCES team_chat_messages(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,read_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(message_id,user_id));
CREATE TABLE IF NOT EXISTS team_chat_mentions(id INTEGER PRIMARY KEY,message_id INTEGER NOT NULL REFERENCES team_chat_messages(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,UNIQUE(message_id,user_id));
CREATE TABLE IF NOT EXISTS task_collaborators(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,created TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(task_id,user_id));
CREATE TABLE IF NOT EXISTS task_subtasks(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,title TEXT NOT NULL,completed INTEGER NOT NULL DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_message_attachments_message ON message_attachments(message_id);
CREATE INDEX IF NOT EXISTS idx_message_mentions_user ON message_mentions(user_id,message_id);
CREATE INDEX IF NOT EXISTS idx_guest_sessions_token ON guest_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_guest_messages_guest ON guest_messages(guest_id,id);
CREATE INDEX IF NOT EXISTS idx_tasks_scope ON tasks(status,due_at,assigned_to);
CREATE INDEX IF NOT EXISTS idx_internal_docs_scope ON internal_documents(visibility,case_id,created);
CREATE INDEX IF NOT EXISTS idx_cases_client ON cases(client_id,status);
CREATE INDEX IF NOT EXISTS idx_cases_responsible ON cases(responsible_id);
CREATE INDEX IF NOT EXISTS idx_messages_client ON messages(client_id,visibility);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id,read_at);
CREATE INDEX IF NOT EXISTS idx_case_events_case ON case_events(case_id);
CREATE INDEX IF NOT EXISTS idx_pendencies_client ON pendencies(client_id,status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedupe ON notifications(user_id,dedupe_key) WHERE dedupe_key<>'';"""))
        ensure_column(c, 'users', 'must_change', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'users', 'is_super', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'users', 'portal_enabled', 'INTEGER NOT NULL DEFAULT 1')
        ensure_column(c, 'users', 'avatar', "TEXT DEFAULT ''")
        ensure_column(c, 'users', 'cover', "TEXT DEFAULT ''")
        ensure_column(c, 'users', 'phone', "TEXT DEFAULT ''")
        ensure_column(c, 'users', 'created_by', 'INTEGER')
        ensure_column(c, 'users', 'owner_staff_id', 'INTEGER')
        ensure_column(c, 'users', 'deleted_at', "TEXT DEFAULT ''")
        ensure_column(c, 'users', 'deleted_by', 'INTEGER')
        ensure_column(c, 'users', 'totp_secret', "TEXT DEFAULT ''")
        ensure_column(c, 'users', 'totp_enabled', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'users', 'totp_last_step', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'users', 'totp_confirmed_at', "TEXT DEFAULT ''")
        ensure_column(c, 'users', 'recovery_codes', "TEXT DEFAULT ''")
        ensure_column(c, 'users', 'recovery_generated_at', "TEXT DEFAULT ''")
        ensure_column(c, 'users', 'staff_kind', "TEXT DEFAULT ''")
        c.execute("UPDATE users SET staff_kind='lawyer' WHERE role='staff' AND (staff_kind IS NULL OR staff_kind='')")
        ensure_column(c, 'cases', 'deleted_at', "TEXT DEFAULT ''")
        ensure_column(c, 'cases', 'deleted_by', 'INTEGER')
        ensure_column(c, 'documents', 'deleted_at', "TEXT DEFAULT ''")
        ensure_column(c, 'documents', 'deleted_by', 'INTEGER')
        ensure_column(c, 'contacts', 'ip', "TEXT DEFAULT ''")
        ensure_column(c, 'contacts', 'consent', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'contacts', 'status', "TEXT NOT NULL DEFAULT 'novo'")
        ensure_column(c, 'contacts', 'responsible_id', 'INTEGER REFERENCES users(id) ON DELETE SET NULL')
        ensure_column(c, 'contacts', 'updated', "TEXT DEFAULT ''")
        c.execute('CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status,id)')
        ensure_column(c, 'audit', 'ip', "TEXT DEFAULT ''")
        ensure_column(c, 'audit', 'user_agent', "TEXT DEFAULT ''")
        ensure_column(c, 'audit', 'entity', "TEXT DEFAULT ''")
        ensure_column(c, 'audit', 'entity_id', 'INTEGER')
        ensure_column(c, 'audit', 'client_id', 'INTEGER')
        ensure_column(c, 'audit', 'case_id', 'INTEGER')
        ensure_column(c, 'audit', 'before', "TEXT DEFAULT ''")
        ensure_column(c, 'audit', 'after', "TEXT DEFAULT ''")
        ensure_column(c, 'cases', 'case_number', "TEXT DEFAULT ''")
        ensure_column(c, 'cases', 'area', "TEXT DEFAULT ''")
        ensure_column(c, 'cases', 'status', "TEXT DEFAULT 'Em andamento'")
        ensure_column(c, 'cases', 'description', "TEXT DEFAULT ''")
        ensure_column(c, 'cases', 'responsible_id', 'INTEGER REFERENCES users(id)')
        ensure_column(c, 'cases', 'updated', "TEXT DEFAULT ''")
        ensure_column(c, 'updates', 'case_id', 'INTEGER REFERENCES cases(id)')
        ensure_column(c, 'updates', 'seen_by_client', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'appointments', 'case_id', 'INTEGER REFERENCES cases(id)')
        ensure_column(c, 'appointments', 'created_by', 'INTEGER REFERENCES users(id)')
        ensure_column(c, 'cases', 'original_title', "TEXT DEFAULT ''")
        ensure_column(c, 'cases', 'created_by', 'INTEGER REFERENCES users(id)')
        ensure_column(c, 'cases', 'source', "TEXT DEFAULT 'legado'")
        ensure_column(c, 'pendencies', 'review_notes', "TEXT DEFAULT ''")
        ensure_column(c, 'documents', 'status', "TEXT NOT NULL DEFAULT 'aguardando_analise'")
        ensure_column(c, 'documents', 'analysis_notes', "TEXT DEFAULT ''")
        ensure_column(c, 'documents', 'reviewed_by', 'INTEGER REFERENCES users(id)')
        ensure_column(c, 'documents', 'reviewed_at', "TEXT DEFAULT ''")
        ensure_column(c, 'appointments', 'status', "TEXT NOT NULL DEFAULT 'pendente'")
        ensure_column(c, 'appointments', 'reminder_at', "TEXT DEFAULT ''")
        ensure_column(c, 'appointments', 'reminder_sent', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'appointments', 'kind', "TEXT DEFAULT 'compromisso'")
        ensure_column(c, 'appointments', 'owner_id', 'INTEGER REFERENCES users(id)')
        ensure_column(c, 'appointments', 'location', "TEXT DEFAULT ''")
        ensure_column(c, 'appointments', 'reminder_choice', "TEXT NOT NULL DEFAULT 'global'")
        ensure_column(c, 'appointments', 'deleted_at', "TEXT DEFAULT ''")
        ensure_column(c, 'appointments', 'deleted_by', 'INTEGER')
        ensure_column(c, 'appointments', 'privacy', "TEXT NOT NULL DEFAULT 'internal'")
        c.execute("UPDATE appointments SET privacy='client' WHERE client_id IS NOT NULL AND privacy='internal'")
        ensure_column(c, 'tasks', 'deleted_at', "TEXT DEFAULT ''")
        ensure_column(c, 'tasks', 'deleted_by', 'INTEGER')
        ensure_column(c, 'tasks', 'source_message_id', 'INTEGER REFERENCES messages(id)')
        ensure_column(c, 'tasks', 'document_id', 'INTEGER REFERENCES documents(id)')
        ensure_column(c, 'guest_sessions', 'user_id', 'INTEGER REFERENCES users(id)')
        migrate_appointments_nullable(c)
        ensure_column(c, 'faqs', 'category', "TEXT DEFAULT 'Geral'")
        ensure_column(c, 'faqs', 'sort_order', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'faqs', 'updated', "TEXT DEFAULT ''")
        c.execute("UPDATE faqs SET category='Geral' WHERE category='' OR category IS NULL")
        c.execute("UPDATE faqs SET sort_order=id WHERE sort_order=0")
        if current_version < 21:
            for category, question, answer, order in FAQ_SEED:
                c.execute("INSERT INTO faqs(question,answer,published,category,sort_order) SELECT ?,?,1,?,? WHERE NOT EXISTS(SELECT 1 FROM faqs WHERE question=?)", (question, answer, category, order, question))
        c.execute('CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status,when_at)')
        ensure_column(c, 'cases', 'last_activity_at', "TEXT DEFAULT ''")
        ensure_column(c, 'requests', 'last_activity_at', "TEXT DEFAULT ''")
        ensure_column(c, 'requests', 'case_id', 'INTEGER REFERENCES cases(id)')
        ensure_column(c, 'requests', 'responded_by', 'INTEGER REFERENCES users(id)')
        ensure_column(c, 'requests', 'responded_at', "TEXT DEFAULT ''")
        ensure_column(c, 'documents', 'case_id', 'INTEGER REFERENCES cases(id)')
        ensure_column(c, 'documents', 'uploaded_by', 'INTEGER REFERENCES users(id)')
        ensure_column(c, 'documents', 'seen_by_client', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'messages', 'case_id', 'INTEGER REFERENCES cases(id)')
        ensure_column(c, 'messages', 'visibility', "TEXT NOT NULL DEFAULT 'client'")
        ensure_column(c, 'messages', 'reveal_identity', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(c, 'messages', 'conversation_id', 'INTEGER REFERENCES conversations(id) ON DELETE SET NULL')
        c.execute('CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id,id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_conversations_client ON conversations(client_id,status,updated)')
        if not fresh_postgres and current_version < 3:
            for row in c.execute('SELECT id,created,updated FROM cases').fetchall():
                values = [row['created'], row['updated']]
                for table in ('messages', 'documents', 'updates', 'appointments', 'requests'):
                    found = c.execute('SELECT MAX(created) AS m FROM ' + table + ' WHERE case_id=?', (row['id'],)).fetchone()
                    if found and found['m']:
                        values.append(found['m'])
                c.execute('UPDATE cases SET last_activity_at=? WHERE id=?', (max(values), row['id']))
            for row in c.execute('SELECT id,created,responded_at FROM requests').fetchall():
                c.execute('UPDATE requests SET last_activity_at=? WHERE id=?', (max([row['created'], row['responded_at']]), row['id']))
        if not fresh_postgres and current_version < 4:
            c.execute("UPDATE cases SET original_title=title WHERE original_title=''")
            c.execute('UPDATE cases SET created_by=responsible_id WHERE created_by IS NULL')
        if not fresh_postgres and current_version < 6:
            c.execute("UPDATE documents SET status='disponibilizado' WHERE source='escritório'")
            c.execute("UPDATE documents SET status='analisado' WHERE reviewed=1 AND source='cliente'")
            reminder_hours = 24
            configured = c.execute("SELECT value FROM settings WHERE key='appointment_reminder_hours'").fetchone()
            if configured and str(configured[0]).isdigit():
                reminder_hours = int(configured[0])
            for appointment in c.execute('SELECT id,when_at,reminder_at FROM appointments').fetchall():
                if appointment['reminder_at']:
                    continue
                parsed = None
                for fmt in ('%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M'):
                    try:
                        parsed = datetime.datetime.strptime(str(appointment['when_at']), fmt)
                        break
                    except ValueError:
                        pass
                if parsed:
                    reminder_at = (parsed - datetime.timedelta(hours=reminder_hours)).strftime('%Y-%m-%d %H:%M')
                    c.execute("UPDATE appointments SET status=COALESCE(NULLIF(status,''),'pendente'), reminder_at=?, reminder_sent=0 WHERE id=?", (reminder_at, appointment['id']))
        if not fresh_postgres and current_version < 8:
            groups = c.execute("SELECT m.client_id,m.case_id,m.visibility,MIN(m.created) AS created,MAX(m.created) AS updated FROM messages m WHERE m.conversation_id IS NULL GROUP BY m.client_id,m.case_id,m.visibility").fetchall()
            for group in groups:
                cursor = c.execute("INSERT INTO conversations(client_id,case_id,title,visibility,status,created,updated) VALUES(?,?,? ,?,'legacy',?,?)", (group['client_id'], group['case_id'], 'Histórico anterior', group['visibility'], group['created'], group['updated']))
                c.execute('UPDATE messages SET conversation_id=? WHERE conversation_id IS NULL AND client_id=? AND case_id IS ? AND visibility=?', (cursor.lastrowid, group['client_id'], group['case_id'], group['visibility']))
            for notice in c.execute("SELECT id,dedupe_key FROM notifications WHERE type IN ('message','internal')").fetchall():
                match = re.fullmatch(r'(?:message|internal)-(\d+)-(?:client|u\d+)', notice['dedupe_key'] or '')
                if match:
                    message = c.execute('SELECT conversation_id FROM messages WHERE id=?', (int(match.group(1)),)).fetchone()
                    if message and message['conversation_id']:
                        c.execute('UPDATE notifications SET url=? WHERE id=?', ('/conversas/' + str(message['conversation_id']), notice['id']))
            c.execute("INSERT OR IGNORE INTO message_reads(user_id,message_id) SELECT m.client_id,m.id FROM messages m WHERE m.visibility='client' AND m.read_by_client=1 AND m.sender_role!='client'")
            c.execute("INSERT OR IGNORE INTO message_reads(user_id,message_id) SELECT u.id,m.id FROM messages m JOIN users u ON u.role IN ('admin','staff') AND u.active=1 WHERE m.read_by_staff=1 AND m.sender_id IS NOT u.id")
        if existed and not fresh_postgres and current_version < 9:
            c.execute("UPDATE contacts SET status='nao_classificado' WHERE status='novo'")
        c.execute('INSERT OR IGNORE INTO schema_migrations(version) VALUES(?)', (SCHEMA_VERSION,))
        defaults = {
            'unread_hours': '24',
            'stale_hours': '48',
            'appointment_reminder_hours': '24',
            'client_show_lawyer': '0',
            'email_notifications': '0',
            'chat_online': '1',
        }
        for key, value in defaults.items():
            c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)', (key, value))
    cleanup_orphans()


def cleanup_orphans():
    try:
        with db() as c:
            stored = {r[0] for r in c.execute("SELECT stored FROM documents UNION SELECT stored FROM internal_documents UNION SELECT stored FROM message_attachments UNION SELECT avatar FROM users WHERE avatar<>'' UNION SELECT cover FROM users WHERE cover<>'' UNION SELECT attachment_stored FROM team_chat_messages WHERE attachment_stored<>''")}
        cutoff = time.time() - 86400
        for p in UP.iterdir():
            if not p.is_file() or p.name in stored:
                continue
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
            except OSError:
                pass
    except Exception:
        pass


def pwd(raw):
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(raw.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=SCRYPT_MAXMEM, dklen=64)
    return 'scrypt$' + str(SCRYPT_N) + '$' + str(SCRYPT_R) + '$' + str(SCRYPT_P) + '$' + salt.hex() + '$' + dk.hex()


def verify(raw, stored):
    try:
        if stored.startswith('scrypt$'):
            _, n, r, p, salt, digest = stored.split('$')
            dk = hashlib.scrypt(raw.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), maxmem=SCRYPT_MAXMEM, dklen=64)
        else:
            salt, digest = stored.split(':')
            dk = hashlib.scrypt(raw.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, maxmem=SCRYPT_MAXMEM, dklen=64)
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def needs_rehash(stored):
    try:
        if not stored.startswith('scrypt$'):
            return True
        parts = stored.split('$')
        return int(parts[1]) < SCRYPT_N or int(parts[2]) < SCRYPT_R or int(parts[3]) < SCRYPT_P
    except Exception:
        return True


def totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def totp_step(timestamp=None):
    return int((timestamp if timestamp is not None else time.time()) // 30)


def totp_code(secret, step):
    text = str(secret or '').strip().upper()
    if not text:
        return ''
    padded = text + '=' * ((8 - len(text) % 8) % 8)
    key = base64.b32decode(padded)
    digest = hmac.new(key, int(step).to_bytes(8, 'big'), hashlib.sha1).digest()
    offset = digest[-1] & 0x0f
    number = int.from_bytes(digest[offset:offset + 4], 'big') & 0x7fffffff
    return f'{number % 1000000:06d}'


def verify_totp(secret, code, last_step=0):
    normalized = re.sub(r'\s+', '', str(code or ''))
    if not normalized.isdigit() or len(normalized) != 6:
        return 0
    current = totp_step()
    for step in (current - 1, current, current + 1):
        if step > int(last_step or 0) and hmac.compare_digest(totp_code(secret, step), normalized):
            return step
    return 0


def recovery_hash(code):
    normalized = re.sub(r'[^A-Za-z0-9]', '', str(code or '')).upper()
    return hashlib.sha256(('bomfim-lacerda-mfa:' + normalized).encode()).hexdigest()


def new_recovery_codes(count=8):
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(6).upper()
        codes.append(raw[:4] + '-' + raw[4:8] + '-' + raw[8:12])
    return codes


def recovery_remaining(stored):
    try:
        return len(json.loads(stored or '[]'))
    except Exception:
        return 0


def consume_recovery_code(c, user_id, code):
    row = c.execute('SELECT recovery_codes FROM users WHERE id=?', (user_id,)).fetchone()
    if not row:
        return False
    try:
        codes = json.loads(row['recovery_codes'] or '[]')
    except Exception:
        return False
    hashed = recovery_hash(code)
    for index, stored in enumerate(codes):
        if hmac.compare_digest(str(stored), hashed):
            del codes[index]
            c.execute('UPDATE users SET recovery_codes=? WHERE id=?', (json.dumps(codes), user_id))
            return True
    return False


def esc(x):
    return html.escape(str(x if x is not None else ''), quote=True)


def fmt_when(value):
    raw = str(value or '')
    for pattern in ('%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M'):
        try:
            return datetime.datetime.strptime(raw, pattern).strftime('%d/%m/%Y %H:%M')
        except ValueError:
            pass
    return raw


def audit_json(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value[:10000]
    return json.dumps(value, ensure_ascii=False, default=str)[:10000]


def audit(c, user, action, detail, ip='', ua='', entity='', entity_id=None, client_id=None, case_id=None, before='', after=''):
    c.execute('INSERT INTO audit(user_id,action,detail,ip,user_agent,entity,entity_id,client_id,case_id,before,after) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (user, action, str(detail or '')[:1000], str(ip or '')[:64], str(ua or '')[:255], str(entity or '')[:80], entity_id, client_id, case_id, audit_json(before), audit_json(after)))


def is_super(user):
    return bool(user and user['role'] == 'admin' and user['is_super'])


def guest_token_hash(token):
    return hashlib.sha256(str(token or '').encode('utf-8')).hexdigest()


def selected_participant_ids(fields):
    ids = []
    for key, value in fields.items():
        if key.startswith('participant_') and str(value) == '1' and key[len('participant_'):].isdigit():
            ids.append(int(key[len('participant_'):]))
    return ids


def staff_kind(user):
    if not user or user['role'] != 'staff':
        return ''
    try:
        value = user['staff_kind']
    except (KeyError, IndexError):
        value = ''
    return value if value in ('lawyer', 'employee') else 'lawyer'


def is_lawyer(user):
    return bool(user and user['role'] == 'staff' and staff_kind(user) == 'lawyer')


def is_employee(user):
    return bool(user and user['role'] == 'staff' and staff_kind(user) == 'employee')


def role_label(user):
    if not user:
        return ''
    if user['role'] == 'client':
        return 'Cliente'
    if user['role'] == 'admin':
        return 'Super admin' if is_super(user) else 'Administrador'
    return 'Advogado' if is_lawyer(user) else 'Funcionário'


def initials(name):
    parts = [part for part in re.split(r'\s+', str(name or '').strip()) if part]
    if not parts:
        return 'BL'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


PERMISSION_ACTIONS = [
    ('manage_users', 'Gerenciar usuários'),
    ('manage_permissions', 'Gerenciar permissões'),
    ('view_audit', 'Visualizar auditoria'),
    ('manage_settings', 'Configurações do sistema'),
    ('create_clients', 'Criar e gerenciar clientes'),
    ('manage_cases', 'Criar e editar casos'),
    ('send_messages', 'Enviar mensagens e relatos'),
    ('manage_documents', 'Gerenciar documentos'),
    ('view_reports', 'Visualizar relatórios'),
    ('transfer_cases', 'Transferir casos'),
    ('delete_records', 'Excluir e restaurar registros'),
    ('permanent_delete', 'Exclusão definitiva'),
]

DEFAULT_PERMISSIONS = {
    'admin': {'create_clients', 'manage_cases', 'send_messages', 'manage_documents', 'view_reports'},
    'staff': {'create_clients', 'manage_cases', 'send_messages', 'manage_documents', 'view_reports'},
    'client': set(),
}


def has_permission(c, user, action):
    if not user:
        return False
    if is_super(user):
        return True
    row = c.execute('SELECT allowed FROM permissions WHERE user_id=? AND action=?', (user['id'], action)).fetchone()
    if row is not None:
        return bool(row['allowed'])
    return action in DEFAULT_PERMISSIONS.get(user['role'], set())


def setting(c, key, default=''):
    row = c.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return row['value'] if row else default


def parse_dt(value):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M'):
        try:
            return datetime.datetime.strptime(str(value or ''), fmt)
        except ValueError:
            pass
    return None


def hours_since(value):
    parsed = parse_dt(value)
    if not parsed:
        return 10 ** 9
    return max(0, (datetime.datetime.now() - parsed).total_seconds() / 3600)


def status_color(status):
    text = str(status or '').lower()
    if 'aguardando' in text or 'respondida' in text:
        return 'blue'
    if 'conclu' in text:
        return 'green'
    if 'inform' in text or 'suspens' in text:
        return 'gray'
    if 'pendente' in text or 'andamento' in text:
        return 'yellow'
    return 'gray'


def status_badge(status):
    return '<span class="status-badge status-' + status_color(status) + '">' + esc(status or 'Em andamento') + '</span>'


def status_alert_class(status, last_activity, stale_hours):
    if status_color(status) == 'yellow' and hours_since(last_activity) >= stale_hours:
        return ' status-alert-yellow'
    return ''


def status_box_class(base, status, last_activity, stale_hours):
    return base + ' status-border-' + status_color(status) + status_alert_class(status, last_activity, stale_hours)


def message_box_class(message, unread_hours):
    if message['sender_role'] == 'client' and not message['read_by_staff']:
        return 'request status-border-red' + (' status-alert' if hours_since(message['created']) >= unread_hours else '')
    return 'request status-border-gray'


DOCUMENT_STATUS_LABELS = {
    'aguardando_analise': 'Aguardando análise',
    'analisado': 'Analisado',
    'aceito': 'Aceito',
    'complementacao': 'Complementação',
    'disponibilizado': 'Disponibilizado',
}


def document_color(status):
    if status in ('aceito', 'disponibilizado'):
        return 'green'
    if status in ('analisado', 'complementacao'):
        return 'blue'
    return 'yellow'


def document_badge(status):
    return '<span class="status-badge status-' + document_color(status) + '">' + DOCUMENT_STATUS_LABELS.get(status, status or 'Aguardando análise') + '</span>'


def appointment_color(status):
    if status == 'realizado':
        return 'green'
    if status == 'cancelado':
        return 'gray'
    return 'yellow'


def appointment_badge(status):
    labels = {'pendente': 'Pendente', 'realizado': 'Realizado', 'cancelado': 'Cancelado'}
    return '<span class="status-badge status-' + appointment_color(status) + '">' + labels.get(status, status or 'Pendente') + '</span>'


def pendency_color(status):
    text = str(status or '').lower()
    if 'atendida' in text:
        return 'green'
    if 'recebida' in text or 'análise' in text or 'analise' in text:
        return 'yellow'
    return 'blue'


def pendency_badge(status):
    return '<span class="status-badge status-' + pendency_color(status) + '">' + esc(status or 'Aberta') + '</span>'


TASK_STATUS_LABELS = {'pendente': 'Pendente', 'em_andamento': 'Em andamento', 'concluida': 'Concluída'}
TASK_PRIORITY_LABELS = {'normal': 'Normal', 'alta': 'Alta', 'urgente': 'Urgente'}
TASK_KIND_LABELS = {'compromisso': 'Compromisso', 'processo': 'Processo', 'audiencia': 'Audiência', 'reuniao': 'Reunião', 'prazo': 'Prazo', 'pessoal': 'Pessoal', 'outro': 'Outro'}


def task_is_overdue(task):
    if task['status'] == 'concluida' or not task['due_at']:
        return False
    return str(task['due_at'])[:16] < datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def task_status_badge(task):
    if task_is_overdue(task):
        return '<span class="status-badge status-red">Atrasada</span>'
    color = {'pendente': 'yellow', 'em_andamento': 'blue', 'concluida': 'green'}.get(task['status'], 'gray')
    return '<span class="status-badge status-' + color + '">' + TASK_STATUS_LABELS.get(task['status'], task['status']) + '</span>'


def task_priority_badge(priority):
    color = {'urgente': 'red', 'alta': 'yellow', 'normal': 'gray'}.get(priority, 'gray')
    return '<span class="status-badge status-' + color + '">' + TASK_PRIORITY_LABELS.get(priority, priority) + '</span>'


def client_case_cards(cases, stale_hours):
    return ''.join('<div class="' + status_box_class('case-box', case['status'], case['last_activity_at'] or case['created'], stale_hours) + '"><h3>#' + str(case['id']) + ' — ' + esc(case['title']) + '</h3><p class="case-meta">' + status_badge(case['status']) + ' · atualizado em ' + esc(case['last_activity_at'] or case['updated'] or case['created']) + '</p>' + ('<p>' + esc(case['description'][:220]) + '</p>' if case['description'] else '') + '<p><a class="text-link" href="/cliente/atendimento/' + str(case['id']) + '">Consultar detalhes →</a></p></div>' for case in cases) or '<p class="muted">Nenhum atendimento cadastrado ainda.</p>'


def client_messages_thread(messages, unread_hours):
    parts = []
    for message in messages:
        label = 'Você' if message['sender_role'] == 'client' else (esc(message['sender_name']) if message['reveal_identity'] else 'Suporte do escritório')
        unread = message['sender_role'] != 'client' and not message['read_by_client']
        alert = ' status-alert' if unread and hours_since(message['created']) >= unread_hours else ''
        badge = ' <span class="status-badge status-red">Nova</span>' if unread else ''
        parts.append('<div class="message ' + ('client' if message['sender_role'] == 'client' else 'office') + (' unread' if unread else '') + alert + '"><p class="message-meta">' + label + ' · ' + esc(message['case_title'] or 'Caso geral') + ' · ' + esc(message['created']) + badge + '</p><p>' + esc(message['body']) + '</p></div>')
    return ''.join(parts) or '<p class="muted">Nenhuma mensagem ainda. Envie uma mensagem para a equipe.</p>'


def client_case_select(cases, selected=None):
    options = '<option value="">Sem caso específico</option>' + ''.join(f'<option value="{case["id"]}"' + (' selected' if str(case['id']) == str(selected) else '') + f'>#{case["id"]} — {esc(case["title"])}</option>' for case in cases)
    return '<label>Caso (opcional)<select name="case_id">' + options + '</select></label>'


def client_pendency_select(pendencies):
    default = '<option value="">Sem pendência específica</option>'
    options = ''.join(f'<option value="{pendency["id"]}">{esc(pendency["title"])} ({esc(pendency["status"])})</option>' for pendency in pendencies)
    return '<label>Pendência (opcional)<select name="pendency_id">' + default + options + '</select></label>'


def touch_case(c, case_id):
    if case_id:
        c.execute('UPDATE cases SET updated=CURRENT_TIMESTAMP,last_activity_at=CURRENT_TIMESTAMP WHERE id=?', (case_id,))


def touch_request(c, request_id):
    c.execute('UPDATE requests SET last_activity_at=CURRENT_TIMESTAMP WHERE id=?', (request_id,))


def notify(c, user_id, ntype, title, body='', url='', client_id=None, case_id=None, dedupe_key=''):
    if not user_id:
        return
    if dedupe_key and c.execute('SELECT 1 FROM notifications WHERE user_id=? AND dedupe_key=?', (user_id, dedupe_key)).fetchone():
        return
    c.execute('INSERT INTO notifications(user_id,client_id,case_id,type,title,body,url,dedupe_key) VALUES(?,?,?,?,?,?,?,?)', (user_id, client_id, case_id, ntype, title, body, url, dedupe_key))


def case_event(c, case_id, actor_id, event_type, description='', from_status='', to_status='', old_title='', new_title='', visible_to_client=0):
    if not case_id:
        return
    c.execute('INSERT INTO case_events(case_id,actor_id,event_type,description,from_status,to_status,old_title,new_title,visible_to_client) VALUES(?,?,?,?,?,?,?,?,?)', (case_id, actor_id, event_type, description, from_status, to_status, old_title, new_title, visible_to_client))


def case_audience(c, case_row):
    ids = set()
    if case_row:
        if case_row['responsible_id']:
            ids.add(case_row['responsible_id'])
        for row in c.execute('SELECT staff_id FROM case_assignments WHERE case_id=?', (case_row['id'],)):
            ids.add(row['staff_id'])
    for row in c.execute("SELECT id FROM users WHERE role='admin' AND is_super=1 AND active=1 AND deleted_at=''"):
        ids.add(row['id'])
    return ids


def client_export(c, client_id):
    client = c.execute("SELECT id,name,email,phone,created,active,deleted_at FROM users WHERE id=? AND role='client'", (client_id,)).fetchone()
    if not client:
        return None
    cases = [dict(row) for row in c.execute('SELECT id,title,original_title,case_number,area,status,description,source,created,updated,last_activity_at,deleted_at FROM cases WHERE client_id=? ORDER BY id', (client_id,))]
    documents = [dict(row) for row in c.execute('SELECT d.id,d.case_id,ca.title AS case_title,d.filename,d.mime,d.size,d.source,d.status,d.analysis_notes,d.created,d.reviewed_at,d.deleted_at FROM documents d LEFT JOIN cases ca ON ca.id=d.case_id WHERE d.client_id=? ORDER BY d.id', (client_id,))]
    messages = []
    for row in c.execute("SELECT m.id,m.case_id,m.conversation_id,m.sender_role,m.reveal_identity,m.body,m.created,m.read_by_client,s.name AS sender_name FROM messages m LEFT JOIN users s ON s.id=m.sender_id WHERE m.client_id=? AND m.visibility='client' ORDER BY m.id", (client_id,)):
        sender = 'Cliente' if row['sender_role'] == 'client' else ('Suporte do escritório' if not row['reveal_identity'] else (row['sender_name'] or 'Escritório'))
        messages.append({'id': row['id'], 'case_id': row['case_id'], 'conversa_id': row['conversation_id'], 'remetente': sender, 'corpo': row['body'], 'enviada_em': row['created'], 'lida_pelo_cliente': bool(row['read_by_client'])})
    conversations = [dict(row) for row in c.execute("SELECT id,case_id,title,status,created,updated,closed_at FROM conversations WHERE client_id=? AND visibility='client' ORDER BY id", (client_id,))]
    appointments = [dict(row) for row in c.execute('SELECT id,case_id,title,when_at,notes,status,created FROM appointments WHERE client_id=? ORDER BY id', (client_id,))]
    updates = [dict(row) for row in c.execute('SELECT id,case_id,title,body,created FROM updates WHERE client_id=? ORDER BY id', (client_id,))]
    requests = [dict(row) for row in c.execute('SELECT id,case_id,subject,body,status,response,created,responded_at FROM requests WHERE client_id=? ORDER BY id', (client_id,))]
    pendencies = [dict(row) for row in c.execute('SELECT id,case_id,title,description,due_at,status,review_notes,created,received_at,reviewed_at FROM pendencies WHERE client_id=? AND visible_to_client=1 ORDER BY id', (client_id,))]
    events = [dict(row) for row in c.execute('SELECT case_id,event_type,description,from_status,to_status,old_title,new_title,created FROM case_events WHERE visible_to_client=1 AND case_id IN (SELECT id FROM cases WHERE client_id=?) ORDER BY id', (client_id,))]
    notifications = [dict(row) for row in c.execute('SELECT type,title,body,url,case_id,created,read_at FROM notifications WHERE user_id=? ORDER BY id', (client_id,))]
    message_attachments = [dict(row) for row in c.execute("SELECT ma.id,ma.message_id,m.conversation_id,ma.filename,ma.mime,ma.size,ma.created FROM message_attachments ma JOIN messages m ON m.id=ma.message_id WHERE m.client_id=? AND m.visibility='client' ORDER BY ma.id", (client_id,))]
    return {
        'gerado_em': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'titular': dict(client),
        'casos': cases,
        'documentos': documents,
        'mensagens': messages,
        'conversas': conversations,
        'compromissos': appointments,
        'atualizacoes': updates,
        'solicitacoes': requests,
        'pendencias': pendencies,
        'eventos_visiveis': events,
        'notificacoes': notifications,
        'anexos_de_mensagens': message_attachments,
    }


def client_audience(c, client_id, case_id=None):
    case_row = c.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone() if case_id else None
    if case_row:
        return case_audience(c, case_row)
    ids = set()
    owner = c.execute('SELECT owner_staff_id FROM users WHERE id=?', (client_id,)).fetchone()
    if owner and owner['owner_staff_id']:
        ids.add(owner['owner_staff_id'])
    for row in c.execute('SELECT staff_id FROM assignments WHERE client_id=?', (client_id,)):
        ids.add(row['staff_id'])
    for row in c.execute("SELECT id FROM users WHERE role='admin' AND is_super=1 AND active=1 AND deleted_at=''"):
        ids.add(row['id'])
    return ids


def create_conversation(c, client_id, case_id, title, visibility, author_id):
    cursor = c.execute('INSERT INTO conversations(client_id,case_id,title,visibility,created_by) VALUES(?,?,?,?,?)', (client_id, case_id or None, title, visibility, author_id))
    return cursor.lastrowid


def employee_conversation_scope(alias):
    return ("((" + alias + ".case_id IS NULL AND " + alias + ".client_id IN (SELECT client_id FROM assignments WHERE staff_id=? UNION SELECT client_id FROM cases WHERE responsible_id=? AND deleted_at='' UNION SELECT ca.client_id FROM cases ca JOIN case_assignments cs ON cs.case_id=ca.id WHERE cs.staff_id=? AND ca.deleted_at='')) OR " + alias + ".case_id IN (SELECT id FROM cases WHERE responsible_id=? AND deleted_at='' UNION SELECT ca2.id FROM cases ca2 JOIN case_assignments cs2 ON cs2.case_id=ca2.id WHERE cs2.staff_id=? AND ca2.deleted_at=''))")


def highlight_mentions(body):
    escaped = esc(body)
    return re.sub(r'@([A-Za-zÀ-ÿ0-9_.-]{2,60})', r'<span class="mention">@\1</span>', escaped)


def mentioned_user_ids(c, body):
    tokens = re.findall(r'@([A-Za-zÀ-ÿ0-9_.-]{2,60})', str(body or ''))
    if not tokens:
        return []
    users = c.execute("SELECT id,name FROM users WHERE role IN ('admin','staff') AND active=1 AND deleted_at=''").fetchall()
    found = []
    for token in tokens:
        needle = token.casefold()
        for user_row in users:
            name = (user_row['name'] or '').strip()
            if needle in (name.casefold(), name.split()[0].casefold() if name else ''):
                if user_row['id'] not in found:
                    found.append(user_row['id'])
    return found


def team_chat_html(c, user):
    messages = c.execute("SELECT tm.*,u.name AS sender_name FROM team_chat_messages tm JOIN users u ON u.id=tm.sender_id ORDER BY tm.id DESC LIMIT 80").fetchall()
    parts = []
    for message in reversed(messages):
        attachment = ''
        if message['attachment_stored']:
            attachment = '<a class="message-attachment" href="/admin/chat-equipe/anexo/' + str(message['id']) + '">' + panel_icon('documents') + esc(message['attachment_filename']) + '</a>'
        mine = message['sender_id'] == user['id']
        side = 'client' if mine else 'office'
        created = esc((message['created'] or '')[:16])
        parts.append('<div class="message ' + side + ' team-message" data-avatar="' + esc(initials(message['sender_name'])) + '">' +
            '<span class="message-avatar" aria-hidden="true">' + esc(initials(message['sender_name'])) + '</span>' +
            '<div class="message-body"><p class="message-meta"><strong>' + esc(message['sender_name']) + '</strong> · <time>' + created + '</time></p>' +
            '<div class="bubble"><p>' + highlight_mentions(message['body']) + '</p>' + attachment + '</div></div></div>')
    return ''.join(parts) or '<p class="muted">Nenhuma mensagem no chat da equipe.</p>'


def team_chat_unread(c, user):
    return c.execute("SELECT COUNT(*) FROM team_chat_messages tm LEFT JOIN team_chat_reads tr ON tr.message_id=tm.id AND tr.user_id=? WHERE tm.sender_id<>? AND tr.message_id IS NULL", (user['id'], user['id'])).fetchone()[0]


def team_chat_read(c, user):
    c.execute("INSERT OR IGNORE INTO team_chat_reads(message_id,user_id) SELECT id,? FROM team_chat_messages WHERE sender_id<>?", (user['id'], user['id']))


def guest_thread_html(session, messages, staff_view=False):
    parts = []
    for message in messages:
        if message['sender_role'] == 'guest':
            sender = session['name'] if staff_view else 'Você'
            side = 'client'
        else:
            sender = 'Equipe Bomfim & Lacerda'
            side = 'office'
        parts.append('<div class="message ' + side + '" data-avatar="' + esc(initials(sender)) + '"><p class="message-meta">' + esc(sender) + ' · ' + esc(message['created']) + '</p><p>' + esc(message['body']) + '</p></div>')
    return ''.join(parts) or '<p class="muted">Nenhuma mensagem ainda.</p>'


def guest_session_by_token(c, token):
    return c.execute("SELECT gs.*,ct.status AS contact_status,ct.responsible_id FROM guest_sessions gs LEFT JOIN contacts ct ON ct.id=gs.contact_id WHERE gs.token_hash=?", (guest_token_hash(token),)).fetchone()


def conversation_unread(c, user, conversation_id):
    return c.execute('''SELECT COUNT(*) FROM messages m LEFT JOIN message_reads r ON r.message_id=m.id AND r.user_id=?
        WHERE m.conversation_id=? AND (m.sender_id IS NULL OR m.sender_id<>?) AND r.message_id IS NULL''',
        (user['id'], conversation_id, user['id'])).fetchone()[0]


def conversation_unread_totals(c, user):
    conditions = ["u.deleted_at=''", "(cv.case_id IS NULL OR ca.deleted_at='')", '(m.sender_id IS NULL OR m.sender_id<>?)', 'r.message_id IS NULL']
    params = [user['id'], user['id']]
    if user['role'] == 'client':
        conditions.extend(["cv.client_id=?", "cv.visibility='client'"])
        params.append(user['id'])
    elif user['role'] == 'staff':
        if is_employee(user):
            conditions.append(employee_conversation_scope('cv'))
            params.extend([user['id']] * 5)
        else:
            conditions.append("(cv.case_id IS NOT NULL OR cv.client_id IN (SELECT client_id FROM assignments WHERE staff_id=? UNION SELECT client_id FROM cases WHERE responsible_id=? AND deleted_at='' UNION SELECT ca2.client_id FROM cases ca2 JOIN case_assignments cs ON cs.case_id=ca2.id WHERE cs.staff_id=? AND ca2.deleted_at=''))")
            params.extend([user['id'], user['id'], user['id']])
    rows = c.execute('''SELECT cv.visibility,COUNT(*) AS unread FROM messages m JOIN conversations cv ON cv.id=m.conversation_id
        JOIN users u ON u.id=cv.client_id LEFT JOIN cases ca ON ca.id=cv.case_id
        LEFT JOIN message_reads r ON r.message_id=m.id AND r.user_id=? WHERE ''' + ' AND '.join(conditions) + ' GROUP BY cv.visibility', tuple(params)).fetchall()
    totals = {'client': 0, 'internal': 0}
    totals.update({row['visibility']: row['unread'] for row in rows})
    return totals


def conversation_rows(c, user, status=None, case_id=None):
    conditions = ["u.deleted_at=''", "(cv.case_id IS NULL OR ca.deleted_at='')"]
    params = [user['id'], user['id']]
    if user['role'] == 'client':
        conditions.extend(["cv.client_id=?", "cv.visibility='client'"])
        params.append(user['id'])
    elif user['role'] == 'staff':
        if is_employee(user):
            conditions.append(employee_conversation_scope('cv'))
            params.extend([user['id']] * 5)
        else:
            conditions.append("(cv.case_id IS NOT NULL OR cv.client_id IN (SELECT client_id FROM assignments WHERE staff_id=? UNION SELECT client_id FROM cases WHERE responsible_id=? AND deleted_at='' UNION SELECT ca2.client_id FROM cases ca2 JOIN case_assignments cs ON cs.case_id=ca2.id WHERE cs.staff_id=? AND ca2.deleted_at=''))")
            params.extend([user['id'], user['id'], user['id']])
    if status:
        conditions.append('cv.status=?')
        params.append(status)
    if case_id:
        conditions.append('cv.case_id=?')
        params.append(case_id)
    return c.execute('''SELECT cv.*,u.name AS client_name,ca.title AS case_title,
        (SELECT COUNT(*) FROM messages m LEFT JOIN message_reads r ON r.message_id=m.id AND r.user_id=?
         WHERE m.conversation_id=cv.id AND (m.sender_id IS NULL OR m.sender_id<>?) AND r.message_id IS NULL) AS unread,
        (SELECT body FROM messages m WHERE m.conversation_id=cv.id ORDER BY m.id DESC LIMIT 1) AS last_body
        FROM conversations cv JOIN users u ON u.id=cv.client_id LEFT JOIN cases ca ON ca.id=cv.case_id WHERE ''' +
        ' AND '.join(conditions) + ' ORDER BY cv.updated DESC,cv.id DESC', tuple(params)).fetchall()


def conversation_cards(rows, user, detail_base='/conversas/', dialog=True):
    statuses = {'open': 'Em andamento', 'closed': 'Encerrada', 'legacy': 'Histórico anterior'}
    parts = []
    for row in rows:
        label = statuses.get(row['status'], row['status'])
        unread = ('<span class="conversation-unread">' + str(row['unread']) + ' não lida(s)</span>') if row['unread'] else ''
        context = (esc(row['client_name']) + ' · ') if user['role'] != 'client' else ''
        context += esc(row['case_title'] or 'Contato geral')
        if row['visibility'] == 'internal':
            context += ' · Relato interno'
        parts.append('<a class="conversation-card"' + (' data-conversation-link' if dialog else '') + ' href="' + detail_base + str(row['id']) + '"><span class="conversation-card-top"><strong>' + esc(row['title']) + '</strong><span class="conversation-status">' + esc(label) + '</span></span><span class="conversation-context">' + context + '</span><span class="conversation-preview">' + esc((row['last_body'] or '')[:160]) + '</span><span class="conversation-meta">' + esc(row['updated'] or row['created']) + ' ' + unread + '</span></a>')
    return ''.join(parts) or '<p class="muted">Nenhuma conversa nesta seção.</p>'


def admin_context_actions(client_id, case_id=None, can_message=False, can_cases=False, can_documents=False):
    params = {'client_id': client_id, 'novo': '1'}
    if case_id:
        params['case_id'] = case_id
    query = urllib.parse.urlencode(params)
    links = []
    if can_message:
        links.append('<a class="btn" href="/admin/mensagens?' + query + '">Nova conversa</a>')
    if can_cases:
        links.extend(['<a class="btn ghost" href="/admin/pendencias?' + query + '">Solicitar documento</a>', '<a class="btn ghost" href="/admin/compromissos?' + query + '">Agendar compromisso</a>'])
    if can_documents:
        links.append('<a class="btn ghost" href="/admin/arquivos?' + query + '">Enviar documento</a>')
    return '<div class="quick-actions">' + ''.join(links) + '</div>' if links else ''


def admin_context_return(client_id='', case_id=''):
    if str(case_id).isdigit() and int(case_id) > 0:
        return '/admin/caso/historico?case_id=' + str(int(case_id))
    if str(client_id).isdigit() and int(client_id) > 0:
        return '/admin/cliente?client_id=' + str(int(client_id))
    return ''


def admin_client_select(clients, selected=''):
    options = '<option value="">Selecione o cliente</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if str(row['id']) == str(selected) else '') + '>' + esc(row['name']) + ' (' + esc(row['email']) + ')</option>' for row in clients)
    return '<label>Cliente<select name="client_id" data-context-client required>' + options + '</select></label>'


def admin_case_select(cases, selected=''):
    options = '<option value="">Sem caso específico</option>' + ''.join('<option value="' + str(row['id']) + '" data-client-id="' + str(row['client_id']) + '"' + (' selected' if str(row['id']) == str(selected) else '') + '>#' + str(row['id']) + ' — ' + esc(row['title']) + ' (' + esc(row['client_name']) + ')</option>' for row in cases)
    return '<label>Caso<select name="case_id" data-context-case>' + options + '</select></label>'


def admin_context_hidden(clients, cases, selected_client='', selected_case=''):
    valid_client = next((row for row in clients if str(row['id']) == str(selected_client)), None)
    valid_case = next((row for row in cases if str(row['id']) == str(selected_case) and valid_client and row['client_id'] == valid_client['id']), None)
    target = admin_context_return(valid_client['id'] if valid_client else '', valid_case['id'] if valid_case else '')
    return '<input type="hidden" name="return_to" value="' + esc(target) + '">' if target else ''


def safe_admin_return(fields, default):
    requested = str(fields.get('return_to', ''))
    expected = admin_context_return(fields.get('client_id', ''), fields.get('case_id', ''))
    return requested if expected and requested == expected else default


def card(title, body='', extra=''):
    return f'<article class="panel"><h3>{esc(title)}</h3>{body}{extra}</article>'


def scam_notice():
    return '<aside class="scam-warning" role="alert"><strong>ATENÇÃO AOS GOLPES!</strong><p>Criminosos podem utilizar nomes, fotografias de advogados e informações de processos para solicitar pagamentos indevidos. Antes de pagar, confirme a solicitação diretamente com nosso escritório pelos canais oficiais.</p><span>Sua segurança é importante para nós.</span></aside>'


def panel_card(title, body, action=''):
    return '<article class="panel panel-card"><div class="panel-card-head"><h2>' + esc(title) + '</h2>' + action + '</div>' + body + '</article>'


def panel_ring(pct, label, count):
    pct = max(0, min(100, int(round(pct))))
    return ('<div class="panel-ring-item"><div class="panel-ring"><svg viewBox="0 0 42 42" aria-hidden="true"><circle class="ring-track" cx="21" cy="21" r="16"></circle><circle class="ring-value" cx="21" cy="21" r="16" pathLength="100" stroke-dasharray="' + str(pct) + ' 100"></circle></svg><strong>' + str(pct) + '%</strong></div><span>' + esc(label) + '</span><small>' + str(count) + ' caso(s)</small></div>')


def ui_icon(name):
    paths = {
        'location': '<path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
        'phone': '<path d="M5 3 3 5c0 7 9 16 16 16l2-2-4-4-2 2c-3-1-5-3-6-6l2-2-4-4Z"/>',
        'message': '<path d="M21 11.5a8.5 8.5 0 0 1-12.7 7.4L3 20l1.1-5.3A8.5 8.5 0 1 1 21 11.5Z"/><path d="M8 11h8M8 14h5"/>',
        'email': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
        'lock': '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
        'document': '<path d="M6 3h9l3 3v15H6zM14 3v4h4M9 11h6M9 15h6"/>',
        'updates': '<path d="M4 12a8 8 0 1 0 2-5.3M4 4v4h4M12 8v4l3 2"/>',
    }
    return '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true">' + paths[name] + '</svg>'


PANEL_ICON_PATHS = {
    'home': '<path d="M3 10 12 3l9 7v10h-6v-6H9v6H3z"/>',
    'clients': '<path d="M9 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21a7 7 0 0 1 14 0M16 4a4 4 0 0 1 0 8M18 14a7 7 0 0 1 4 7"/>',
    'cases': '<path d="M4 7h16v13H4zM9 7V5h6v2M4 12h16"/>',
    'messages': '<path d="M4 4h16v12H9l-5 4zM8 9h8M8 12h5"/>',
    'documents': '<path d="M6 3h9l3 3v15H6zM14 3v4h4M9 11h6M9 15h6"/>',
    'calendar': '<path d="M4 6h16v14H4zM8 3v6M16 3v6M4 10h16M8 14h3"/>',
    'tasks': '<path d="M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/>',
    'updates': '<path d="M4 12a8 8 0 1 0 2-5.3M4 4v4h4M12 8v4l3 2"/>',
    'report': '<path d="M4 20h16M7 17v-5M12 17V5M17 17V9"/>',
    'settings': '<path d="M4 7h16M7 4v6M4 17h16M17 14v6"/>',
    'profile': '<path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 21a7 7 0 0 1 14 0"/>',
    'add': '<path d="M12 4v16M4 12h16"/>',
    'shield': '<path d="M12 3 4 6v5c0 5 3 8 8 10 5-2 8-5 8-10V6zM9 12l2 2 4-4"/>',
    'trash': '<path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6"/>',
    'content': '<path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/>',
    'faq': '<path d="M4 5h16v12H9l-5 3z M9 9a3 3 0 1 1 4 2.8c-.7.3-1 1-1 1.7M12 16h.01"/>',
    'support': '<path d="M4 13v-2a8 8 0 0 1 16 0v2M4 13a2 2 0 0 0 2 2h1v-6H6a2 2 0 0 0-2 2zM20 13a2 2 0 0 1-2 2h-1v-6h1a2 2 0 0 1 2 2zM18 17a4 4 0 0 1-4 4h-2"/>',
    'logout': '<path d="M10 4H5v16h5M14 8l4 4-4 4M8 12h10"/>',
}


def panel_icon(name):
    return '<svg class="panel-icon" viewBox="0 0 24 24" aria-hidden="true">' + PANEL_ICON_PATHS.get(name, PANEL_ICON_PATHS['home']) + '</svg>'


def professional_contacts(detail, include_office=False):
    links = []
    if detail['phone']:
        digits = re.sub(r'\D', '', detail['phone'])
        links.append(f'<a class="profile-contact-link" href="tel:+55{digits}">{ui_icon("phone")}<span>Ligar: {esc(detail["phone"])}</span></a>')
        links.append(f'<a class="profile-contact-link" href="https://wa.me/55{digits}">{ui_icon("message")}<span>WhatsApp: {esc(detail["phone"])}</span></a>')
    if detail['email']:
        links.append(f'<a class="profile-contact-link" href="mailto:{esc(detail["email"])}">{ui_icon("email")}<span>{esc(detail["email"])}</span></a>')
    if include_office:
        links.append(f'<a class="profile-contact-link" href="/contato">{ui_icon("location")}<span>Endereços do escritório</span></a>')
    return ''.join(links)


def field(label, name, typ='text', required=True):
    return f'<label>{esc(label)}<input type="{typ}" name="{esc(name)}" {"required" if required else ""}></label>'


def input_field(label, name, value='', typ='text', required=True):
    return f'<label>{esc(label)}<input type="{typ}" name="{esc(name)}" value="{esc(value)}" {"required" if required else ""}></label>'


def status_select(current):
    options = ''.join('<option' + (' selected' if current == s else '') + '>' + s + '</option>' for s in ('Pendente', 'Em andamento', 'Respondida', 'Concluída', 'Informativo'))
    return '<label>Status<select name="status">' + options + '</select></label>'


def button(label='Salvar'):
    return f'<button class="btn" type="submit">{esc(label)}</button>'


def form(action, fields, label='Salvar', enctype=''):
    return f'<form method="post" action="{esc(action)}" enctype="{enctype}"><input type="hidden" name="csrf" value="{CSRF_PLACEHOLDER}">{fields}{button(label)}</form>'


def security_headers():
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
        'Cross-Origin-Opener-Policy': 'same-origin',
        'Cross-Origin-Resource-Policy': 'same-origin',
        'X-Permitted-Cross-Domain-Policies': 'none',
    }


def content_disposition(name):
    raw = str(name or 'documento')
    ascii_name = ''.join(ch if 32 <= ord(ch) < 127 and ch not in '"\\' else '_' for ch in raw)[:120] or 'documento'
    quoted = urllib.parse.quote(raw, safe='')[:300]
    return 'attachment; filename="' + ascii_name + '"; filename*=UTF-8\'\'' + quoted


def text_field(fields, key, maxlen, required=False, label=None):
    value = fields.get(key, '')
    if value is None:
        value = ''
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if required and not value:
        raise ValidationError('Preencha o campo ' + (label or key) + '.')
    if len(value) > maxlen:
        raise ValidationError('O campo ' + (label or key) + ' excede ' + str(maxlen) + ' caracteres.')
    return value


def password_field(fields, key, required=True):
    value = fields.get(key, '')
    if value is None:
        value = ''
    if not isinstance(value, str):
        value = str(value)
    if required and not value:
        raise ValidationError('Informe a senha.')
    if len(value) > 256:
        raise ValidationError('A senha excede o limite de 256 caracteres.')
    return value


def check_password_strength(value):
    if len(value) < 12:
        raise ValidationError('A senha deve ter ao menos 12 caracteres.')


def email_field(fields, key='email', required=True):
    value = text_field(fields, key, 200, required, 'e-mail').lower()
    if value and not EMAIL_RE.match(value):
        raise ValidationError('Informe um e-mail válido.')
    return value


def to_int(fields, key, required=True, minvalue=1):
    raw = fields.get(key, '')
    if raw is None:
        raw = ''
    raw = str(raw).strip()
    if not raw:
        if required:
            raise ValidationError('Selecione um registro válido.')
        return 0
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError('Identificador inválido.')
    if value < minvalue:
        raise ValidationError('Identificador inválido.')
    return value


def bool_flag(fields, key):
    return 1 if str(fields.get(key, '')) == '1' else 0


def rate_limited(key, limit, window):
    if limit <= 0:
        return False
    moment = time.monotonic()
    with RL_LOCK:
        queue = RL.setdefault(key, [])
        cutoff = moment - window
        while queue and queue[0] < cutoff:
            queue.pop(0)
        if len(queue) >= limit:
            return True
        queue.append(moment)
        if len(RL) > 5000:
            for k in [k for k, v in RL.items() if not v or v[-1] < cutoff]:
                RL.pop(k, None)
        return False


def rate_reset(key):
    with RL_LOCK:
        RL.pop(key, None)


def verify_anon_csrf(token):
    try:
        raw_ts, sig = str(token).split('.', 1)
        timestamp = int(raw_ts)
        if abs(time.time() - timestamp) > 86400:
            return False
        expected = hmac.new(CSRF_SECRET, raw_ts.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def scan_file(path):
    if not CLAMSCAN:
        return True
    try:
        result = subprocess.run([CLAMSCAN, '--no-summary', str(path)], capture_output=True, timeout=30)
        return result.returncode == 0
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = 'BomfimLacerda'
    sys_version = ''

    def version_string(self):
        return self.server_version

    def log_message(self, fmt, *args):
        if os.getenv('ACCESS_LOG', '0') == '1':
            sys.stderr.write('%s - %s\n' % (self.address_string(), fmt % args))

    def client_ip(self):
        if TRUST_PROXY:
            forwarded = self.headers.get('X-Forwarded-For', '')
            if forwarded:
                return forwarded.split(',')[0].strip()[:64]
        return (self.client_address[0] if self.client_address else '')[:64]

    def is_https(self):
        return self.headers.get('X-Forwarded-Proto', '').lower() == 'https'

    def cookie_secure(self):
        return COOKIE_SECURE or self.is_https()

    def session_cookie(self, sid, max_age):
        secure = '; Secure' if self.cookie_secure() else ''
        return 'sid=' + sid + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=' + str(int(max_age)) + secure

    def mfa_cookie(self, token, max_age=MFA_TTL):
        secure = '; Secure' if self.cookie_secure() else ''
        return 'mfa=' + token + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=' + str(int(max_age)) + secure

    def mfa_token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return ''
        row = cookie.get('mfa')
        return row.value if row else ''

    def chat_cookie(self, token, max_age=30 * 24 * 3600):
        secure = '; Secure' if self.cookie_secure() else ''
        return 'bl_chat=' + token + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=' + str(int(max_age)) + secure

    def chat_token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return ''
        row = cookie.get('bl_chat')
        return row.value if row else ''

    def chat_csrf_ok(self, fields):
        data = self.session()
        token = str(fields.get('csrf', '') or '')
        if data and hmac.compare_digest(token, data['csrf']):
            return True
        return verify_anon_csrf(token)

    def chat_session(self, c, user):
        if user and user['role'] == 'client':
            return c.execute("SELECT * FROM guest_sessions WHERE user_id=? AND status='open' ORDER BY id DESC LIMIT 1", (user['id'],)).fetchone()
        token = self.chat_token()
        if not token:
            return None
        session = guest_session_by_token(c, token)
        return session if session and session['status'] == 'open' else None

    def staff_online_count(self):
        moment = time.monotonic()
        with SESS_LOCK:
            uids = {data['uid'] for data in SESS.values() if moment - data.get('created', 0) <= SESSION_TTL and moment - data.get('last', 0) <= SESSION_IDLE}
        if not uids:
            return 0
        with db() as c:
            placeholders = ','.join('?' for _ in uids)
            row = c.execute("SELECT COUNT(*) FROM users WHERE id IN (" + placeholders + ") AND role IN ('admin','staff') AND active=1 AND deleted_at=''", tuple(uids)).fetchone()
        return row[0] if row else 0

    def send(self, body, status=200, ctype='text/html; charset=utf-8', headers=None, cache=None):
        if isinstance(body, str):
            body = body.encode()
        hdrs = security_headers()
        hdrs.update({'Content-Type': ctype, 'Content-Length': str(len(body)), 'Cache-Control': cache or 'no-store'})
        if self.is_https():
            hdrs['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        if headers:
            hdrs.update(headers)
        self.send_response(status)
        for key, value in hdrs.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def send_file(self, path, ctype, download=None, cache=None):
        try:
            stat = path.stat()
        except OSError:
            return self.send('Não encontrado', 404)
        etag = '"' + format(stat.st_mtime_ns, 'x') + '-' + format(stat.st_size, 'x') + '"'
        if self.headers.get('If-None-Match') == etag:
            return self.send(b'', 304, ctype=ctype, headers={'ETag': etag}, cache=cache)
        hdrs = security_headers()
        hdrs.update({'Content-Type': ctype, 'Content-Length': str(stat.st_size), 'Cache-Control': cache or 'no-store', 'ETag': etag})
        if self.is_https():
            hdrs['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        if download:
            hdrs['Content-Disposition'] = content_disposition(download)
        self.send_response(200)
        for key, value in hdrs.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command == 'HEAD':
            return
        try:
            with path.open('rb') as source:
                shutil.copyfileobj(source, self.wfile, 64 * 1024)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, data, status=200, headers=None):
        self.send(json.dumps(data, ensure_ascii=False), status=status, ctype='application/json; charset=utf-8', headers=headers, cache='no-store')

    def redirect(self, path, headers=None):
        self.send(b'', 303, headers={'Location': path, **(headers or {})})

    def session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            return None
        sid = cookie.get('sid')
        if not sid:
            return None
        key = sid.value
        moment = time.monotonic()
        with SESS_LOCK:
            data = SESS.get(key)
            if not data:
                return None
            if moment - data.get('created', 0) > SESSION_TTL or moment - data.get('last', 0) > SESSION_IDLE:
                SESS.pop(key, None)
                return None
            data['last'] = moment
            if moment - _LAST_CLEAN[0] > 300:
                _LAST_CLEAN[0] = moment
                for k, v in list(SESS.items()):
                    if moment - v.get('created', 0) > SESSION_TTL or moment - v.get('last', 0) > SESSION_IDLE:
                        SESS.pop(k, None)
            return data

    def user(self):
        data = self.session()
        if not data:
            return None
        with db() as c:
            row = c.execute('SELECT id,name,email,role,staff_kind,active,must_change,is_super,phone,owner_staff_id,deleted_at,avatar,cover FROM users WHERE id=?', (data['uid'],)).fetchone()
        return row if row and row['active'] and not row['deleted_at'] else None

    def anon_csrf(self):
        timestamp = str(int(time.time()))
        signature = hmac.new(CSRF_SECRET, timestamp.encode(), hashlib.sha256).hexdigest()
        return timestamp + '.' + signature

    def request_host(self):
        host = self.headers.get('Host', '127.0.0.1:8080').strip()
        if not re.match(r'^[A-Za-z0-9.\-:\[\]]+$', host):
            return '127.0.0.1:8080'
        return host[:255]

    def origin_ok(self):
        origin = self.headers.get('Origin')
        if not origin:
            return True
        scheme = 'https' if self.is_https() else 'http'
        allowed = {scheme + '://' + self.request_host()}
        if PUBLIC_ORIGIN:
            allowed.add(PUBLIC_ORIGIN)
        for extra in os.getenv('EXTRA_ORIGINS', '').split(','):
            extra = extra.strip()
            if extra:
                allowed.add(extra)
        return origin in allowed

    def csrf_public_ok(self, fields):
        data = self.session()
        token = str(fields.get('csrf', '') or '')
        if data and hmac.compare_digest(token, data['csrf']):
            return True
        return verify_anon_csrf(token)

    def notif_bell(self):
        return '''<div class="notif" id="notif-wrap"><button type="button" class="notif-btn" id="notif-btn" aria-label="Notificações" aria-expanded="false" aria-controls="notif-panel"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></svg><span class="notif-count" id="notif-count" hidden>0</span></button><div class="notif-panel" id="notif-panel" role="region" aria-label="Central de notificações" hidden><div class="notif-head"><div><strong>Notificações</strong><p id="notif-summary">Carregando avisos...</p></div><button type="button" class="notif-close" id="notif-close" aria-label="Fechar notificações">×</button></div><div class="notif-filters" aria-label="Filtrar notificações"><button type="button" id="notif-filter-all" aria-pressed="true">Todas</button><button type="button" id="notif-filter-unread" aria-pressed="false">Não lidas</button></div><p class="notif-status" id="notif-status" role="status" aria-live="polite"></p><div id="notif-list"><p class="notif-empty">Carregando notificações...</p></div><div class="notif-actions"><button type="button" id="notif-enable">Ativar no navegador</button><button type="button" id="notif-sound">Som: desativado</button><button type="button" id="notif-read-all">Marcar todas como lidas</button></div><p class="notif-hint">Mostrando até 20 avisos recentes. Alertas do navegador funcionam enquanto o site estiver aberto.</p></div><div class="notif-toasts" id="notif-toasts" aria-live="polite" aria-atomic="false"></div></div>'''

    def panel_nav(self, user):
        path = urllib.parse.urlsplit(self.path).path
        with db() as c:
            totals = conversation_unread_totals(c, user)
            unread = totals['client'] + totals['internal']
            new_contacts = c.execute("SELECT COUNT(*) FROM contacts WHERE status='novo'").fetchone()[0] if is_super(user) else 0
            guest_unread = c.execute("SELECT COUNT(*) FROM guest_messages gm JOIN guest_sessions gs ON gs.id=gm.guest_id WHERE gm.sender_role='guest' AND gm.read_by_staff=0 AND gs.status='open'").fetchone()[0] if user['role'] in ('admin', 'staff') else 0
            team_unread = team_chat_unread(c, user) if user['role'] in ('admin', 'staff') else 0
            if is_employee(user):
                explicit = c.execute("SELECT allowed FROM permissions WHERE user_id=? AND action='view_reports'", (user['id'],)).fetchone()
                can_reports = bool(explicit and explicit['allowed'])
            else:
                can_reports = has_permission(c, user, 'view_reports')
            can_cases = has_permission(c, user, 'manage_cases')
            can_documents = has_permission(c, user, 'manage_documents')
        admin = user['role'] == 'admin'
        home = '/admin' if admin else '/advogado'
        primary = [(home, 'Visão geral' if admin else 'Meu painel', 'home'), ('/admin/clientes', 'Clientes', 'clients'), ('/admin/casos', 'Casos', 'cases')]
        attendance = [('/admin/mensagens', 'Conversas com clientes', 'messages', str(unread) if unread else ''), ('/admin/chats', 'Chat ao vivo', 'messages', str(guest_unread) if guest_unread else ''), ('/admin/solicitacoes', 'Solicitações', 'messages')]
        if is_super(user):
            attendance.append(('/admin/contatos', 'Contatos do site', 'support', str(new_contacts) if new_contacts else ''))
        agenda_links = [('/admin/compromissos', 'Agenda', 'calendar'), ('/admin/atualizacoes', 'Atualizações', 'updates')]
        if can_cases:
            agenda_links += [('/admin/tarefas?status=atrasadas', 'Prazos', 'tasks'), ('/admin/tarefas', 'Tarefas', 'tasks'), ('/admin/pendencias', 'Pendências', 'tasks')]
        documents = [('/admin/arquivos', 'Documentos de clientes', 'documents')]
        if can_documents:
            documents.append(('/admin/documentos-internos', 'Documentos internos', 'documents'))
        site = [('/admin/conteudos', 'Conteúdos', 'content'), ('/admin/faq', 'FAQ', 'faq')] if admin else []
        config = [('/admin/permissoes', 'Permissões', 'shield'), ('/admin/seguranca', 'Segurança', 'shield'), ('/admin/auditoria', 'Auditoria', 'report'), ('/admin/lixeira', 'Lixeira', 'trash')] if is_super(user) else []

        def is_active(href):
            return path == href or (href == home and path == '/admin' and not admin) or (href == '/admin/mensagens' and path.startswith('/conversas/')) or (href != home and href != '/admin' and path.startswith(href))

        def link(item, nested=False):
            href, label, icon = item[:3]
            badge = item[3] if len(item) > 3 else ''
            active = is_active(href)
            badge_html = '<span class="panel-badge">' + esc(badge) + '</span>' if badge else ''
            return '<a href="' + esc(href) + '"' + (' class="active" aria-current="page"' if active else '') + '>' + panel_icon(icon) + '<span>' + esc(label) + '</span>' + badge_html + '</a>'

        def group(label, icon, items):
            if not items:
                return ''
            open_attr = ' open' if any(is_active(item[0]) for item in items) else ''
            active_class = ' active-group' if open_attr else ''
            return '<details class="panel-nav-group' + active_class + '"' + open_attr + '><summary>' + panel_icon(icon) + '<span>' + esc(label) + '</span><span class="panel-group-arrow">›</span></summary><div class="panel-nav-sublinks">' + ''.join(link(item, True) for item in items) + '</div></details>'

        nav = ''.join(link(item) for item in primary)
        nav += group('Atendimento ao cliente', 'messages', attendance)
        internal_links = [('/admin/chat-equipe', 'Chat da equipe', 'messages', str(team_unread) if team_unread else ''), ('/admin/mensagens?tipo=interno&status=todas', 'Conversas internas dos casos', 'messages')]
        nav += group('Comunicação interna', 'support', internal_links)
        nav += group('Agenda e Gestão', 'calendar', agenda_links)
        nav += group('Documentos', 'documents', documents)
        if can_reports:
            nav += link(('/admin/relatorios', 'Relatórios', 'report'))
        nav += group('Gestão do site', 'content', site)
        if is_super(user):
            nav += link(('/admin/usuarios', 'Equipe e usuários', 'clients'))
        nav += group('Configurações', 'settings', config)
        return '<nav class="panel-nav" aria-label="Navegação do painel">' + nav + '</nav>'

    def panel_layout(self, title, content, user=None, description=None, csrf_token=''):
        desc = description or (str(title) + ' — Bomfim & Lacerda Advocacia.')
        home = '/admin' if user['role'] == 'admin' else '/advogado'
        first_name = esc((user['name'] or '').split()[0] if user['name'] else '')
        role = role_label(user)
        avatar = ('<img class="panel-avatar-img" src="/perfil/imagem/' + str(user['id']) + '/avatar" alt="">') if ('avatar' in user.keys() and user['avatar']) else esc(initials(user['name']))
        bell = self.notif_bell()
        nav = self.panel_nav(user)
        chat_alert = '<div class="staff-chat-alert" id="staff-chat-alert" data-chat-alert-endpoint="/admin/chats/alertas"><a class="staff-chat-bubble" id="staff-chat-bubble" href="/admin/chats" aria-label="Abrir chat da equipe" title="Chat da equipe"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16v12H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg><span class="staff-chat-badge" id="staff-chat-badge" hidden>0</span></a><div class="staff-chat-toast" id="staff-chat-toast" hidden><button type="button" class="staff-chat-toast-close" id="staff-chat-toast-close" aria-label="Fechar aviso">×</button><p class="staff-chat-toast-meta">Nova mensagem no chat</p><strong id="staff-chat-toast-name"></strong><p id="staff-chat-toast-body"></p><a id="staff-chat-toast-link" href="/admin/chats">Abrir atendimento →</a></div></div>'
        return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(desc)}"><meta name="csrf-token" content="{esc(csrf_token)}"><title>{esc(title)} | Bomfim & Lacerda Advocacia</title><link rel="icon" href="/static/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/static/style.css?v=20261111r"></head><body class="panel-area"><a class="skip" href="#main">Pular para o conteúdo</a><header class="panel-top"><button type="button" class="panel-menu-btn" id="panel-menu" aria-label="Abrir menu" aria-expanded="false" aria-controls="panel-sidebar">☰</button><div class="panel-top-context"><span class="eyebrow">BOMFIM &amp; LACERDA</span><strong>{esc(title)}</strong></div><form class="panel-global-search" method="get" action="/admin/busca"><input type="search" name="q" placeholder="Buscar clientes, casos, tarefas, documentos..." aria-label="Busca global"></form><div class="panel-top-actions">{bell}<details class="panel-user-menu"><summary aria-label="Menu da conta"><span class="panel-avatar">{avatar}</span><span class="panel-user-name"><strong>{esc(user['name'])}</strong><small>{esc(role)}</small></span></summary><div class="panel-user-dropdown"><a href="{home}">Meu painel</a><a href="/perfil">Meu perfil</a><a href="/senha">Alterar senha</a><a href="/">Site do escritório</a><a href="/sair">Sair</a></div></details><a class="panel-exit" href="/sair" aria-label="Sair">Sair</a></div></header><div class="panel-shell"><aside class="panel-sidebar" id="panel-sidebar"><a class="panel-brand" href="{home}"><span class="panel-monogram">BL</span><span>BOMFIM &amp; LACERDA<small>ADVOCACIA</small></span></a>{nav}<div class="panel-side-card"><p class="eyebrow">ATENDIMENTO</p><strong>Conte com a nossa equipe.</strong><p>Estamos à disposição para apoiar o seu trabalho.</p><a class="text-link" href="/contato">Falar com o escritório →</a></div></aside><button type="button" class="panel-overlay" id="panel-overlay" aria-label="Fechar menu" tabindex="-1"></button><main id="main" class="panel-main">{content}</main></div>{chat_alert}<script src="/static/app.js?v=20261111r" defer></script></body></html>'''

    def chat_widget(self, user, csrf_token):
        with db() as c:
            online = setting(c, 'chat_online', '1') == '1' and self.staff_online_count() > 0
        authenticated = bool(user and user['role'] == 'client')
        name = esc(user['name']) if authenticated else ''
        email = esc(user['email']) if authenticated else ''
        prefill = ''
        if authenticated:
            prefill = '<input type="hidden" name="name" value="' + name + '"><input type="hidden" name="email" value="' + email + '">'
        else:
            prefill = '<label>Nome<input type="text" name="name" required autocomplete="name"></label><label>E-mail<input type="email" name="email" required autocomplete="email"></label><label>Telefone (opcional)<input type="tel" name="phone" autocomplete="tel"></label>'
        consent = '' if authenticated else '<label class="check"><input type="checkbox" name="consent" value="1" required> Concordo com o contato e o aviso de privacidade.</label>'
        return '<div class="chat-widget" id="chat-widget" data-chat-widget data-chat-online="' + ('1' if online else '0') + '" data-chat-authenticated="' + ('1' if authenticated else '0') + '" data-chat-endpoint="/chat"><button type="button" class="chat-bubble" id="chat-bubble" aria-label="Abrir atendimento" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16v12H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg><span class="chat-bubble-badge" data-chat-badge hidden></span></button><section class="chat-panel" id="chat-panel" aria-label="Atendimento pelo site" hidden><header class="chat-panel-head"><div class="chat-heading"><span class="chat-presence" data-chat-presence></span><div><strong data-chat-title>' + ('Atendimento online' if online else 'Atendimento fora do horário') + '</strong><small data-chat-subtitle>' + ('Fale agora com a equipe.' if online else 'Deixe sua mensagem; responderemos depois.') + '</small></div></div><button type="button" class="chat-close" id="chat-close" aria-label="Fechar atendimento">×</button></header><div class="chat-panel-body"><div class="chat-start" data-chat-start><p class="muted">' + ('Preencha seus dados para iniciar a conversa.' if not authenticated else 'Inicie a conversa com a equipe.') + '</p><form data-chat-start-form><input type="hidden" name="csrf" value="' + esc(csrf_token) + '">' + prefill + consent + '<button class="btn" type="submit">Iniciar atendimento</button></form></div><div class="chat-conversation" data-chat-conversation hidden><div class="chat-thread" data-chat-thread></div><form data-chat-form><input type="hidden" name="csrf" value="' + esc(csrf_token) + '"><label>Mensagem<textarea name="body" rows="3" required></textarea></label><button class="btn" type="submit">Enviar</button></form></div></div></section></div>'

    def layout(self, title, content, user=None, description=None, csrf_token=''):
        desc = description or (str(title) + ' — Bomfim & Lacerda Advocacia. 40 anos de tradição jurídica, ética e atendimento próximo.')
        nav = '<a href="/">Início</a><a href="/escritorio">O escritório</a><a href="/equipe">Equipe</a><a href="/areas">Áreas</a><a href="/conteudos">Conteúdo</a><a href="/faq">Dúvidas</a><a href="/contato">Contato</a>'
        bell = ''
        if user:
            panel = 'advogado' if user['role'] == 'staff' else ('admin' if user['role'] == 'admin' else 'cliente')
            nav += f'<a href="/{panel}">Meu painel</a><a href="/senha">Senha</a><a href="/sair">Sair</a>'
            bell = self.notif_bell()
        else:
            nav += '<a class="nav-login" href="/entrar">Área do cliente</a>'
        widget = self.chat_widget(user, csrf_token) if not user or user['role'] == 'client' else ''
        return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(desc)}"><meta name="csrf-token" content="{esc(csrf_token)}"><title>{esc(title)} | Bomfim & Lacerda Advocacia</title><link rel="stylesheet" href="/static/style.css?v=20261111r"></head><body><a class="skip" href="#main">Pular para o conteúdo</a><header class="top"><a class="brand" href="/"><span class="monogram">BL</span><span>BOMFIM & LACERDA<small>ADVOCACIA</small></span></a><button class="mobile-toggle" type="button" id="menu-btn" aria-label="Abrir menu" aria-expanded="false" aria-controls="nav">☰</button><nav id="nav" aria-label="Navegação principal">{nav}</nav>{bell}</header><main id="main">{content}</main><footer><div><strong>BOMFIM & LACERDA</strong><p>40 anos de tradição jurídica.</p></div><div>Ética • Dedicação • Compromisso</div><div><a href="/privacidade">Privacidade</a> · <a href="/termos">Termos de uso</a></div></footer>{widget}<script src="/static/app.js?v=20261111r" defer></script></body></html>'''

    def client_layout(self, title, content, user=None, description=None, csrf_token=''):
        desc = description or (str(title) + ' — Meu Espaço — Bomfim & Lacerda Advocacia.')
        path = urllib.parse.urlsplit(self.path).path
        with db() as c:
            totals = conversation_unread_totals(c, user) if user else {'client': 0, 'internal': 0}
        unread = totals['client']
        avatar = (('<img class="panel-avatar-img" src="/perfil/imagem/' + str(user['id']) + '/avatar" alt="">') if ('avatar' in user.keys() and user['avatar']) else esc(initials(user['name']))) if user else 'BL'
        bell = self.notif_bell() if user else ''
        links = [('/cliente', 'Início', 'home'), ('/cliente/atendimentos', 'Meus atendimentos', 'cases'), ('/cliente/mensagens', 'Conversas', 'messages'), ('/cliente/documentos', 'Documentos', 'documents'), ('/cliente/compromissos', 'Compromissos', 'calendar'), ('/cliente/atualizacoes', 'Atualizações', 'updates'), ('/cliente/novo', 'Novo atendimento', 'add'), ('/perfil', 'Meu perfil', 'profile')]
        nav = []
        for href, label, icon in links:
            active = path == href or (href != '/cliente' and path.startswith(href))
            badge = ''
            if href == '/cliente/mensagens' and unread:
                badge = '<span class="panel-badge" data-unread-count>' + str(unread) + '</span>'
            nav.append('<a href="' + href + '"' + (' class="active" aria-current="page"' if active else '') + '>' + panel_icon(icon) + '<span>' + esc(label) + '</span>' + badge + '</a>')
        nav = ''.join(nav)
        widget = self.chat_widget(user, csrf_token)
        return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(desc)}"><meta name="csrf-token" content="{esc(csrf_token)}"><title>{esc(title)} | Meu Espaço — Bomfim & Lacerda Advocacia</title><link rel="icon" href="/static/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/static/style.css?v=20261111r"></head><body class="panel-area client-area"><a class="skip" href="#main">Pular para o conteúdo</a><header class="panel-top"><button type="button" class="panel-menu-btn" id="panel-menu" aria-label="Abrir menu" aria-expanded="false" aria-controls="panel-sidebar">☰</button><div class="panel-top-context"><span class="eyebrow">MEU ESPAÇO</span><strong>{esc(title)}</strong></div><div class="panel-top-actions">{bell}<details class="panel-user-menu"><summary aria-label="Menu da conta"><span class="panel-avatar">{avatar}</span><span class="panel-user-name"><strong>{esc(user['name'] if user else '')}</strong><small>Cliente</small></span></summary><div class="panel-user-dropdown"><a href="/cliente">Meu painel</a><a href="/cliente/perfil">Meu perfil</a><a href="/">Site do escritório</a><a href="/sair">Sair</a></div></details><a class="panel-exit" href="/sair" aria-label="Sair">Sair</a></div></header><div class="panel-shell"><aside class="panel-sidebar" id="panel-sidebar"><a class="panel-brand" href="/cliente"><span class="panel-monogram">BL</span><span>MEU ESPAÇO<small>BOMFIM &amp; LACERDA</small></span></a><nav class="panel-nav" id="nav" aria-label="Menu do cliente">{nav}</nav><div class="panel-side-card"><p class="eyebrow">SUPORTE</p><strong>Estamos à disposição.</strong><p>Fale com a equipe do escritório sempre que precisar.</p><a class="text-link" href="/contato">Falar com o escritório →</a></div></aside><button type="button" class="panel-overlay" id="panel-overlay" aria-label="Fechar menu" tabindex="-1"></button><main id="main" class="panel-main client-main">{content}</main></div>{widget}<script src="/static/app.js?v=20261111r" defer></script></body></html>'''

    def page(self, title, content, user=None, status=200, description=None):
        data = self.session()
        token = data['csrf'] if data else self.anon_csrf()
        body = content.replace(CSRF_PLACEHOLDER, esc(token))
        if user and data and status == 200:
            with SESS_LOCK:
                message = data.pop('flash', '')
            if message:
                body = '<div class="wrap"><p class="admin-flash" role="status">' + esc(message) + '</p></div>' + body
        if user and user['role'] == 'client':
            self.send(self.client_layout(title, body, user, description, token), status)
        elif user and user['role'] in ('admin', 'staff'):
            self.send(self.panel_layout(title, body, user, description, token), status)
        else:
            self.send(self.layout(title, body, user, description, token), status)

    def forbidden(self):
        self.page('Acesso negado', '<section class="wrap section"><h1>Acesso não autorizado</h1><p>Você não tem permissão para visualizar esta página.</p></section>', self.user(), 403)

    def flash(self, message):
        data = self.session()
        if data:
            with SESS_LOCK:
                data['flash'] = message

    def error_page(self, title, message, status=400, user=None):
        self.page(title, '<section class="wrap section"><h1>' + esc(title) + '</h1><p>' + esc(message) + '</p></section>', user, status)

    def read_post(self):
        raw_length = self.headers.get('Content-Length', '0')
        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            raise ValidationError('Requisição inválida.')
        if length < 0 or length > MAX_BODY:
            raise ValidationError('Arquivo ou formulário muito grande (limite: 12 MB).')
        raw = self.rfile.read(length)
        ctype = self.headers.get('Content-Type', '')
        if ctype.startswith('multipart/form-data'):
            message = BytesParser(policy=default).parsebytes(b'Content-Type: ' + ctype.encode() + b'\r\nMIME-Version: 1.0\r\n\r\n' + raw)
            fields = {}
            files = {}
            for part in message.iter_parts():
                key = part.get_param('name', header='content-disposition')
                filename = part.get_filename()
                if filename is not None:
                    files[key] = (filename, part.get_payload(decode=True), part.get_content_type())
                elif key:
                    payload = part.get_payload(decode=True) or b''
                    fields[key] = payload.decode('utf-8', 'replace')
            return fields, files
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode('utf-8', 'replace'), keep_blank_values=True).items()}, {}

    def scoped_clients(self, c, user):
        if user['role'] == 'admin':
            return c.execute("SELECT * FROM users WHERE role='client' AND deleted_at='' ORDER BY name").fetchall()
        return c.execute("SELECT * FROM users WHERE role='client' AND deleted_at='' AND id IN (SELECT client_id FROM assignments WHERE staff_id=? UNION SELECT client_id FROM cases WHERE responsible_id=? AND deleted_at='' UNION SELECT ca.client_id FROM cases ca JOIN case_assignments cs ON cs.case_id=ca.id WHERE cs.staff_id=? AND ca.deleted_at='') ORDER BY name", (user['id'], user['id'], user['id'])).fetchall()

    def can_manage(self, c, user, client_id):
        if user['role'] == 'admin':
            return bool(c.execute("SELECT 1 FROM users WHERE id=? AND role='client' AND deleted_at=''", (client_id,)).fetchone())
        if user['role'] == 'staff':
            return bool(c.execute('SELECT 1 FROM assignments WHERE staff_id=? AND client_id=?', (user['id'], client_id)).fetchone()) or bool(c.execute("SELECT 1 FROM cases ca LEFT JOIN case_assignments cs ON cs.case_id=ca.id WHERE ca.client_id=? AND ca.deleted_at='' AND (ca.responsible_id=? OR cs.staff_id=?)", (client_id, user['id'], user['id'])).fetchone())
        return user['role'] == 'client' and user['id'] == client_id

    def scoped_cases(self, c, user):
        if user['role'] == 'admin':
            return c.execute("SELECT ca.*, u.name AS client_name FROM cases ca JOIN users u ON u.id=ca.client_id WHERE ca.deleted_at='' ORDER BY ca.id DESC").fetchall()
        if user['role'] == 'staff':
            return c.execute("SELECT DISTINCT ca.*, u.name AS client_name FROM cases ca JOIN users u ON u.id=ca.client_id LEFT JOIN case_assignments cs ON cs.case_id=ca.id AND cs.staff_id=? WHERE ca.deleted_at='' AND (ca.responsible_id=? OR cs.staff_id=?) ORDER BY ca.id DESC", (user['id'], user['id'], user['id'])).fetchall()
        return c.execute("SELECT ca.*, u.name AS client_name FROM cases ca JOIN users u ON u.id=ca.client_id WHERE ca.client_id=? AND ca.deleted_at='' ORDER BY ca.id DESC", (user['id'],)).fetchall()

    def visible_cases(self, c, user):
        if user['role'] == 'admin' or is_lawyer(user):
            return c.execute("SELECT ca.*,u.name AS client_name FROM cases ca JOIN users u ON u.id=ca.client_id WHERE ca.deleted_at='' AND u.deleted_at='' ORDER BY ca.id DESC").fetchall()
        return self.scoped_cases(c, user)

    def task_rows(self, c, user):
        if user['role'] == 'admin':
            return c.execute("SELECT t.*,u.name AS client_name,ca.title AS case_title,ru.name AS responsible_name FROM tasks t LEFT JOIN users u ON u.id=t.client_id LEFT JOIN cases ca ON ca.id=t.case_id LEFT JOIN users ru ON ru.id=t.assigned_to WHERE t.deleted_at='' ORDER BY CASE WHEN t.status='concluida' THEN 1 ELSE 0 END, COALESCE(NULLIF(t.due_at,''),'9999') ASC,t.id DESC").fetchall()
        if is_lawyer(user):
            return c.execute("SELECT t.*,u.name AS client_name,ca.title AS case_title,ru.name AS responsible_name FROM tasks t LEFT JOIN users u ON u.id=t.client_id LEFT JOIN cases ca ON ca.id=t.case_id LEFT JOIN users ru ON ru.id=t.assigned_to WHERE t.deleted_at='' AND (t.assigned_to=? OR t.created_by=? OR t.case_id IN (SELECT id FROM cases WHERE deleted_at='')) ORDER BY CASE WHEN t.status='concluida' THEN 1 ELSE 0 END, COALESCE(NULLIF(t.due_at,''),'9999') ASC,t.id DESC", (user['id'], user['id'])).fetchall()
        return c.execute("SELECT t.*,u.name AS client_name,ca.title AS case_title,ru.name AS responsible_name FROM tasks t LEFT JOIN users u ON u.id=t.client_id LEFT JOIN cases ca ON ca.id=t.case_id LEFT JOIN users ru ON ru.id=t.assigned_to WHERE t.deleted_at='' AND (t.assigned_to=? OR t.created_by=? OR t.case_id IN (SELECT id FROM cases WHERE responsible_id=? AND deleted_at='' UNION SELECT ca2.id FROM cases ca2 JOIN case_assignments cs ON cs.case_id=ca2.id WHERE cs.staff_id=? AND ca2.deleted_at='')) ORDER BY CASE WHEN t.status='concluida' THEN 1 ELSE 0 END, COALESCE(NULLIF(t.due_at,''),'9999') ASC,t.id DESC", (user['id'], user['id'], user['id'], user['id'])).fetchall()

    def can_view_internal_document(self, c, user, document):
        if not user or user['role'] == 'client' or not document:
            return False
        if user['role'] == 'admin':
            return True
        if document['visibility'] == 'equipe':
            return True
        if document['case_id']:
            return self.can_access_case(c, user, document['case_id'])
        if document['client_id']:
            return self.can_manage(c, user, document['client_id'])
        return True

    def can_access_case(self, c, user, case_id):
        if user['role'] == 'admin':
            return bool(c.execute("SELECT 1 FROM cases WHERE id=? AND deleted_at=''", (case_id,)).fetchone())
        if user['role'] == 'staff':
            return bool(c.execute("SELECT 1 FROM cases ca LEFT JOIN case_assignments cs ON cs.case_id=ca.id AND cs.staff_id=? WHERE ca.id=? AND ca.deleted_at='' AND (ca.responsible_id=? OR cs.staff_id=?)", (user['id'], case_id, user['id'], user['id'])).fetchone())
        return bool(c.execute("SELECT 1 FROM cases WHERE id=? AND client_id=? AND deleted_at=''", (case_id, user['id'])).fetchone())

    def can_view_appointment(self, c, user, appointment):
        if not user or not appointment:
            return False
        privacy = appointment['privacy'] or 'internal'
        owner_creator = appointment['created_by'] == user['id'] or appointment['owner_id'] == user['id']
        if user['role'] == 'client':
            return appointment['client_id'] == user['id'] and privacy == 'client'
        if privacy == 'private':
            return user['id'] == (appointment['owner_id'] or appointment['created_by'])
        if privacy == 'internal':
            return user['role'] in ('admin', 'staff')
        if user['role'] == 'admin':
            return True
        if user['role'] == 'staff':
            if c.execute('SELECT 1 FROM appointment_participants WHERE appointment_id=? AND user_id=?', (appointment['id'], user['id'])).fetchone():
                return True
            if appointment['case_id']:
                return self.can_access_case(c, user, appointment['case_id'])
            if appointment['client_id']:
                return self.can_manage(c, user, appointment['client_id'])
            return owner_creator
        return False

    def can_edit_appointment(self, c, user, appointment):
        if not user or user['role'] not in ('admin', 'staff') or not appointment:
            return False
        privacy = appointment['privacy'] or 'internal'
        owner_creator = appointment['created_by'] == user['id'] or appointment['owner_id'] == user['id']
        if privacy == 'private':
            return user['id'] == (appointment['owner_id'] or appointment['created_by'])
        if privacy == 'internal':
            return is_super(user) or user['role'] == 'admin' or owner_creator
        if is_super(user) or user['role'] == 'admin':
            return True
        if c.execute('SELECT 1 FROM appointment_participants WHERE appointment_id=? AND user_id=?', (appointment['id'], user['id'])).fetchone():
            return True
        if appointment['case_id']:
            return self.can_access_case(c, user, appointment['case_id'])
        if appointment['client_id']:
            return self.can_manage(c, user, appointment['client_id'])
        return owner_creator

    def can_view_case(self, c, user, case_id):
        if user['role'] == 'admin' or is_lawyer(user):
            return bool(c.execute("SELECT 1 FROM cases ca JOIN users u ON u.id=ca.client_id WHERE ca.id=? AND ca.deleted_at='' AND u.deleted_at=''", (case_id,)).fetchone())
        return self.can_access_case(c, user, case_id)

    def conversation_access(self, c, user, conversation_id):
        row = c.execute("SELECT cv.*,u.name AS client_name,ca.title AS case_title,ru.name AS responsible_name FROM conversations cv JOIN users u ON u.id=cv.client_id LEFT JOIN cases ca ON ca.id=cv.case_id LEFT JOIN users ru ON ru.id=ca.responsible_id WHERE cv.id=? AND u.deleted_at='' AND (cv.case_id IS NULL OR ca.deleted_at='')", (conversation_id,)).fetchone()
        if not row:
            return None
        if user['role'] == 'client' and (row['client_id'] != user['id'] or row['visibility'] != 'client'):
            return None
        if user['role'] == 'staff' and row['case_id'] is None and not self.can_manage(c, user, row['client_id']):
            return None
        if user['role'] == 'staff' and row['case_id'] is not None and is_employee(user) and not self.can_access_case(c, user, row['case_id']):
            return None
        if user['role'] not in ('client', 'admin', 'staff'):
            return None
        return row

    def can_reply_conversation(self, c, user, conversation):
        if conversation['status'] != 'open':
            return False
        if user['role'] == 'client':
            return conversation['client_id'] == user['id'] and conversation['visibility'] == 'client'
        return (has_permission(c, user, 'send_messages') and self.can_manage(c, user, conversation['client_id'])
                and (not conversation['case_id'] or self.can_access_case(c, user, conversation['case_id'])))

    def conversation_messages_html(self, c, user, conversation_id):
        conversation_meta = c.execute('SELECT visibility,case_id,client_id FROM conversations WHERE id=?', (conversation_id,)).fetchone()
        messages = c.execute('SELECT m.*,u.name AS sender_name FROM messages m LEFT JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=? ORDER BY m.id', (conversation_id,)).fetchall()
        attachment_rows = c.execute("SELECT ma.* FROM message_attachments ma JOIN messages m ON m.id=ma.message_id WHERE m.conversation_id=? ORDER BY ma.id", (conversation_id,)).fetchall()
        attachments_by_message = {}
        for attachment in attachment_rows:
            attachments_by_message.setdefault(attachment['message_id'], []).append(attachment)
        is_internal = bool(conversation_meta and conversation_meta['visibility'] == 'internal')
        messages_html = []
        for message in messages:
            mine = message['sender_id'] == user['id']
            if mine:
                sender = 'Você'
            elif user['role'] == 'client' and message['sender_role'] != 'client' and not message['reveal_identity']:
                sender = 'Suporte do escritório'
            else:
                sender = message['sender_name'] or 'Escritório'
            side = 'client' if message['sender_role'] == 'client' else ('office' if not is_internal else 'internal')
            if is_internal and message['sender_role'] != 'client':
                side = 'office'
            if is_internal and message['sender_role'] == 'client':
                side = 'client'
            file_links = ''.join('<a class="message-attachment" href="/anexo/' + str(attachment['id']) + '">' + panel_icon('documents') + esc(attachment['filename']) + '</a>' for attachment in attachments_by_message.get(message['id'], []))
            unread_mark = '<span class="unread-mark" title="Não lida"></span>' if not message['read_by_staff'] and user['role'] != 'client' and not mine else ''
            created = esc((message['created'] or '')[:16])
            task_button = ''
            if is_internal and user['role'] in ('admin', 'staff'):
                meta_case = conversation_meta['case_id'] if conversation_meta else ''
                meta_client = conversation_meta['client_id'] if conversation_meta else ''
                task_button = '<div class="message-tools"><button type="button" class="task-from-message" data-task-from-message="' + str(message['id']) + '" data-task-case="' + str(meta_case or '') + '" data-task-client="' + str(meta_client or '') + '" data-task-body="' + esc(message['body'][:200]) + '">' + panel_icon('tasks') + 'Criar tarefa a partir desta mensagem</button></div>'
            messages_html.append('<div class="message ' + side + '" data-avatar="' + esc(initials(sender)) + '">' +
                '<span class="message-avatar" aria-hidden="true">' + esc(initials(sender)) + '</span>' +
                '<div class="message-body"><p class="message-meta"><strong>' + esc(sender) + '</strong> · <time>' + created + '</time>' + unread_mark + '</p>' +
                '<div class="bubble"><p>' + highlight_mentions(message['body']) + '</p>' + file_links + '</div>' + task_button + '</div></div>')
        return ''.join(messages_html) or '<p class="muted">Nenhuma mensagem.</p>', messages

    def conversation_view_html(self, c, user, conversation_id):
        conversation = self.conversation_access(c, user, conversation_id)
        if not conversation:
            return None
        can_reply = self.can_reply_conversation(c, user, conversation)
        messages_html, messages = self.conversation_messages_html(c, user, conversation_id)
        hidden = '<input type="hidden" name="conversation_id" value="' + str(conversation_id) + '">'
        reply_fields = hidden + '<label>Resposta<textarea name="body" rows="4"></textarea></label><label>Anexo (opcional)<input type="file" name="file"></label><p class="muted chat-attachment-hint">Permitidos: PDF, PNG, JPG e TXT, até 10 MB.</p>'
        if user['role'] != 'client' and conversation['visibility'] == 'client':
            reply_fields += '<label class="check"><input type="checkbox" name="reveal_identity" value="1"> Mostrar meu nome ao cliente</label>'
        reason = ('Este histórico anterior foi preservado para consulta.' if conversation['status'] == 'legacy' else 'Esta conversa está encerrada.' if conversation['status'] == 'closed' else 'Consulta disponível. Respostas e encerramento dependem de atribuição e permissão da equipe.')
        reply = '<div class="conversation-composer">' + form('/conversas/responder', reply_fields, 'Enviar resposta', 'multipart/form-data') + '</div>' if can_reply else '<p class="muted">' + reason + '</p>'
        if user['role'] == 'client' and conversation['status'] != 'open':
            new_url = '/cliente/mensagens' + ('?case_id=' + str(conversation['case_id']) if conversation['case_id'] else '?novo=1')
            reply += '<p><a class="text-link" href="' + new_url + '">Iniciar nova conversa →</a></p>'
        close = form('/conversas/encerrar', hidden, 'Encerrar conversa') if can_reply and user['role'] in ('staff', 'admin') else ''
        last_shown_id = messages[-1]['id'] if messages else 0
        mark = form('/conversas/ler', hidden + '<input type="hidden" name="last_message_id" value="' + str(last_shown_id) + '">', 'Marcar como lida')
        status = {'open': 'Em andamento', 'closed': 'Encerrada', 'legacy': 'Histórico anterior'}[conversation['status']]
        context = (esc(conversation['client_name']) + ' · ') if user['role'] != 'client' else ''
        context += esc(conversation['case_title'] or 'Contato geral')
        if user['role'] != 'client' and conversation['case_id']:
            context += ' · Responsável: ' + esc(conversation['responsible_name'] or 'Não atribuído')
        if conversation['visibility'] == 'internal':
            context += ' · Relato interno'
        return '<article class="conversation-view panel" id="conversation-view" data-conversation-id="' + str(conversation_id) + '" data-conversation-endpoint="/conversas/' + str(conversation_id) + '/mensagens"><div class="conversation-view-head"><div><p class="eyebrow">' + esc(status) + '</p><h1>' + esc(conversation['title']) + '</h1><p class="muted">' + context + '</p></div></div><div class="thread conversation-thread">' + (''.join(messages_html) or '<p class="muted">Nenhuma mensagem.</p>') + '</div>' + reply + close + '<div class="conversation-mark">' + mark + '</div></article>'

    def case_options(self, c, user, client_id=None, selected=None):
        rows = self.scoped_cases(c, user)
        if client_id:
            rows = [r for r in rows if r['client_id'] == client_id]
        options = ''.join(f'<option value="{r["id"]}"' + (' selected' if selected and int(selected) == r['id'] else '') + f'>#{r["id"]} — {esc(r["title"])} ({esc(r["client_name"])})</option>' for r in rows)
        return '<label>Caso<select name="case_id"><option value="">Sem caso específico</option>' + options + '</select></label>'

    def audit_action(self, c, user_id, action, detail, entity='', entity_id=None, client_id=None, case_id=None, before=None, after=None):
        audit(c, user_id, action, detail, self.client_ip(), self.headers.get('User-Agent', ''), entity, entity_id, client_id, case_id, audit_json(before), audit_json(after))

    def admin_nav(self, user):
        home = '/advogado' if user['role'] == 'staff' else '/admin'
        links = [f'<a href="{home}">Painel</a>', '<a href="/admin/clientes">Clientes</a>', '<a href="/admin/casos">Casos</a>', '<a href="/admin/mensagens">Conversas</a>', '<a href="/admin/arquivos">Documentos</a>', '<a href="/admin/compromissos">Agenda</a>']
        more = ['<a href="/admin/solicitacoes">Solicitações</a>', '<a href="/admin/pendencias">Pendências</a>', '<a href="/admin/atualizacoes">Atualizações</a>', '<a href="/admin/conteudos">Conteúdos</a>', '<a href="/admin/faq">FAQ</a>', '<a href="/admin/relatorios">Relatórios</a>']
        if is_super(user):
            more += ['<a href="/admin/usuarios">Usuários</a>', '<a href="/admin/permissoes">Permissões</a>', '<a href="/admin/seguranca">Segurança</a>', '<a href="/admin/configuracoes">Configurações</a>', '<a href="/admin/auditoria">Auditoria</a>', '<a href="/admin/lixeira">Lixeira</a>', '<a href="/admin/contatos">Contatos</a>']
        return '<nav class="admin-nav" aria-label="Navegação administrativa">' + ''.join(links) + '<details class="admin-nav-more"><summary>Mais opções</summary><div>' + ''.join(more) + '</div></details></nav>'

    def security_page(self, user, c, codes=None, message=''):
        account = c.execute('SELECT totp_secret,totp_enabled,totp_confirmed_at,recovery_codes FROM users WHERE id=?', (user['id'],)).fetchone()
        message_html = ('<p class="client-alert">' + esc(message) + '</p>') if message else ''
        codes_html = ''
        if codes:
            codes_html = card('Códigos de recuperação', '<p><strong>Guarde estes códigos em local seguro.</strong> Cada código pode ser usado uma única vez e não será exibido novamente.</p><ul class="recovery-list">' + ''.join('<li><code>' + esc(code) + '</code></li>' for code in codes) + '</ul>')
        if account['totp_enabled']:
            remaining = recovery_remaining(account['recovery_codes'])
            status = card('MFA ativado', '<p>O acesso de super admin exige o código do app autenticador.</p><p class="muted">Ativado em ' + esc(account['totp_confirmed_at'] or '—') + ' · ' + str(remaining) + ' código(s) de recuperação restante(s).</p>')
            actions = card('Regenerar códigos de recuperação', '<p class="muted">Gera novos códigos e invalida os antigos. Confirme com sua senha e o código atual.</p>' + form('/admin/seguranca/recuperacao', field('Senha atual', 'password', 'password') + field('Código do app', 'code'), 'Gerar novos códigos')) + card('Desativar MFA', '<p class="muted">Use apenas se necessário; o acesso voltará a exigir somente senha.</p>' + form('/admin/seguranca/desativar', field('Senha atual', 'password', 'password') + field('Código do app', 'code'), 'Desativar MFA'))
            setup = ''
        else:
            status = card('MFA não configurado', '<p class="status-badge status-yellow">Recomendado para super admins</p><p>O MFA adiciona uma segunda etapa com app autenticador e códigos de recuperação.</p>')
            if account['totp_secret']:
                uri = 'otpauth://totp/' + urllib.parse.quote('Bomfim & Lacerda:' + user['email']) + '?secret=' + urllib.parse.quote(account['totp_secret']) + '&issuer=' + urllib.parse.quote('Bomfim & Lacerda') + '&digits=6&period=30'
                setup = card('Configuração pendente', '<p>Adicione a chave abaixo ao seu app autenticador (Google Authenticator, Microsoft Authenticator, 1Password etc.):</p><p><code class="mfa-secret">' + esc(account['totp_secret']) + '</code></p><p><a class="text-link" href="' + esc(uri) + '">Abrir link otpauth://</a></p><p class="muted">Depois informe o código de 6 dígitos para confirmar.</p>' + form('/admin/seguranca/confirmar', field('Código de 6 dígitos', 'code'), 'Confirmar MFA'))
            else:
                setup = card('Ativar MFA', '<p>Gere uma chave secreta e configure o app autenticador.</p>' + form('/admin/seguranca/iniciar', '<p class="muted">A chave será exibida na próxima tela.</p>', 'Iniciar configuração'))
            actions = ''
        content = '<section class="wrap section">' + self.admin_nav(user) + '<h1>Segurança</h1>' + message_html + status + codes_html + setup + actions + '<p><a class="text-link" href="/admin">Voltar ao painel</a></p></section>'
        return self.page('Segurança', content, user)

    def page_number(self):
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        try:
            page = int(query.get('page', ['1'])[0])
        except (TypeError, ValueError):
            page = 1
        return max(1, page)

    def pager(self, base, page, pages):
        separator = '&' if '?' in base else '?'
        prev_link = f'<a class="btn ghost" href="{esc(base + separator + "page=" + str(page - 1))}">Anterior</a>' if page > 1 else ''
        next_link = f'<a class="btn ghost" href="{esc(base + separator + "page=" + str(page + 1))}">Próxima</a>' if page < pages else ''
        return f'<p class="pager">{prev_link}<span>Página {page} de {pages}</span>{next_link}</p>'

    def paginate_rows(self, rows, per=15):
        total = len(rows)
        pages = max(1, (total + per - 1) // per)
        page = min(self.page_number(), pages)
        parsed = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        query.pop('page', None)
        suffix = urllib.parse.urlencode(query, doseq=True)
        base = parsed.path + ('?' + suffix if suffix else '')
        return rows[(page - 1) * per:page * per], self.pager(base, page, pages), total

    def base_url(self):
        if PUBLIC_ORIGIN:
            return PUBLIC_ORIGIN
        scheme = 'https' if self.is_https() else 'http'
        return scheme + '://' + self.request_host()

    def scoped_condition(self, alias):
        return alias + ".client_id IN (SELECT a.client_id FROM assignments a JOIN users u ON u.id=a.client_id WHERE a.staff_id=? AND u.deleted_at='') OR " + alias + ".case_id IN (SELECT id FROM cases WHERE responsible_id=? AND deleted_at='' UNION SELECT ca.id FROM cases ca JOIN case_assignments cs ON cs.case_id=ca.id WHERE cs.staff_id=? AND ca.deleted_at='')"

    def overview(self, user):
        admin = user['role'] == 'admin'
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        view_mode = query.get('visao', ['equipe'])[0]
        personal = is_super(user) and view_mode == 'minha'
        personal_client_ids = set()
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        with db() as c:
            clients = self.scoped_clients(c, user)
            cases = self.visible_cases(c, user) if admin else self.scoped_cases(c, user)
            if personal:
                personal_cases = c.execute("SELECT id,client_id FROM cases WHERE deleted_at='' AND (responsible_id=? OR id IN (SELECT case_id FROM case_assignments WHERE staff_id=?))", (user['id'], user['id'])).fetchall()
                personal_case_ids = {row['id'] for row in personal_cases}
                personal_client_ids = {row['client_id'] for row in personal_cases}
                cases = [case for case in cases if case['id'] in personal_case_ids]
                clients = [client for client in clients if client['id'] in personal_client_ids or client['owner_staff_id'] == user['id']]
            stale_hours = max(1, int(setting(c, 'stale_hours', '48') or 48))
            unread_hours = max(1, int(setting(c, 'unread_hours', '24') or 24))
            counts = {'yellow': 0, 'blue': 0, 'green': 0, 'gray': 0}
            stale = 0
            for case in cases:
                color = status_color(case['status'])
                counts[color] = counts.get(color, 0) + 1
                if color == 'yellow' and hours_since(case['last_activity_at'] or case['created']) >= stale_hours:
                    stale += 1
            if admin:
                messages = c.execute("SELECT m.*, u.name AS client, ca.title AS case_title, s.name AS sender FROM messages m JOIN users u ON u.id=m.client_id LEFT JOIN cases ca ON ca.id=m.case_id LEFT JOIN users s ON s.id=m.sender_id WHERE m.visibility='client' ORDER BY m.id DESC LIMIT 10").fetchall()
                requests = c.execute("SELECT r.*, u.name AS client, ca.title AS case_title FROM requests r JOIN users u ON u.id=r.client_id LEFT JOIN cases ca ON ca.id=r.case_id ORDER BY r.id DESC LIMIT 10").fetchall()
                docs = c.execute("SELECT d.*, u.name AS client, cu.name AS uploader, ca.title AS case_title FROM documents d JOIN users u ON u.id=d.client_id LEFT JOIN users cu ON cu.id=d.uploaded_by LEFT JOIN cases ca ON ca.id=d.case_id WHERE d.source='cliente' AND d.deleted_at='' ORDER BY d.id DESC LIMIT 10").fetchall()
                unread_messages = c.execute("SELECT COUNT(*) FROM messages WHERE visibility='client' AND sender_role='client' AND read_by_staff=0").fetchone()[0]
                unread_internal = c.execute("SELECT COUNT(*) FROM messages WHERE visibility='internal' AND read_by_staff=0").fetchone()[0]
                requests_open = c.execute("SELECT COUNT(*) FROM requests r JOIN users u ON u.id=r.client_id WHERE u.deleted_at='' AND r.status IN ('Pendente','Em andamento') AND (r.case_id IS NULL OR r.case_id IN (SELECT id FROM cases WHERE deleted_at=''))").fetchone()[0]
                docs_pending = c.execute("SELECT COUNT(*) FROM documents d JOIN users u ON u.id=d.client_id WHERE u.deleted_at='' AND d.source='cliente' AND d.deleted_at='' AND d.status='aguardando_analise' AND (d.case_id IS NULL OR d.case_id IN (SELECT id FROM cases WHERE deleted_at=''))").fetchone()[0]
                upcoming = c.execute("SELECT a.*, u.name AS client, ca.title AS case_title FROM appointments a LEFT JOIN users u ON u.id=a.client_id LEFT JOIN cases ca ON ca.id=a.case_id WHERE a.status='pendente' AND a.deleted_at='' AND replace(a.when_at,'T',' ') >= ? ORDER BY replace(a.when_at,'T',' ') LIMIT 20", (now_str,)).fetchall()
                upcoming = [row for row in upcoming if self.can_view_appointment(c, user, row)]
                if personal:
                    upcoming = [row for row in upcoming if row['owner_id'] == user['id'] or row['created_by'] == user['id']]
                upcoming = upcoming[:5]
            else:
                params = (user['id'], user['id'], user['id'])
                msg_scope = self.scoped_condition('m')
                req_scope = self.scoped_condition('r')
                doc_scope = self.scoped_condition('d')
                app_scope = "(" + self.scoped_condition('a') + " OR a.owner_id=?)"
                messages = c.execute("SELECT m.*, u.name AS client, ca.title AS case_title, s.name AS sender FROM messages m JOIN users u ON u.id=m.client_id LEFT JOIN cases ca ON ca.id=m.case_id LEFT JOIN users s ON s.id=m.sender_id WHERE m.visibility='client' AND (" + msg_scope + ") ORDER BY m.id DESC LIMIT 10", params).fetchall()
                requests = c.execute("SELECT r.*, u.name AS client, ca.title AS case_title FROM requests r JOIN users u ON u.id=r.client_id LEFT JOIN cases ca ON ca.id=r.case_id WHERE (" + req_scope + ") ORDER BY r.id DESC LIMIT 10", params).fetchall()
                docs = c.execute("SELECT d.*, u.name AS client, cu.name AS uploader, ca.title AS case_title FROM documents d JOIN users u ON u.id=d.client_id LEFT JOIN users cu ON cu.id=d.uploaded_by LEFT JOIN cases ca ON ca.id=d.case_id WHERE d.source='cliente' AND d.deleted_at='' AND (" + doc_scope + ") ORDER BY d.id DESC LIMIT 10", params).fetchall()
                unread_messages = c.execute("SELECT COUNT(*) FROM messages WHERE visibility='client' AND sender_role='client' AND read_by_staff=0 AND (" + self.scoped_condition('messages') + ")", params).fetchone()[0]
                unread_internal = c.execute("SELECT COUNT(*) FROM messages WHERE visibility='internal' AND read_by_staff=0 AND (" + self.scoped_condition('messages') + ")", params).fetchone()[0]
                requests_open = c.execute("SELECT COUNT(*) FROM requests r JOIN users u ON u.id=r.client_id WHERE u.deleted_at='' AND r.status IN ('Pendente','Em andamento') AND (r.case_id IS NULL OR r.case_id IN (SELECT id FROM cases WHERE deleted_at='')) AND (" + self.scoped_condition('r') + ")", params).fetchone()[0]
                candidates = c.execute("SELECT d.client_id,d.case_id FROM documents d JOIN users u ON u.id=d.client_id WHERE u.deleted_at='' AND d.source='cliente' AND d.deleted_at='' AND d.status='aguardando_analise' AND (d.case_id IS NULL OR d.case_id IN (SELECT id FROM cases WHERE deleted_at='')) AND (" + self.scoped_condition('d') + ")", params).fetchall()
                writable_case_ids = {case['id'] for case in cases}
                writable_client_ids = {client['id'] for client in clients}
                docs_pending = sum(1 for doc in candidates if (doc['case_id'] in writable_case_ids if doc['case_id'] else doc['client_id'] in writable_client_ids))
                upcoming = c.execute("SELECT a.*, u.name AS client, ca.title AS case_title FROM appointments a LEFT JOIN users u ON u.id=a.client_id LEFT JOIN cases ca ON ca.id=a.case_id WHERE a.status='pendente' AND a.deleted_at='' AND replace(a.when_at,'T',' ') >= ? ORDER BY replace(a.when_at,'T',' ') LIMIT 20", (now_str,)).fetchall()
                upcoming = [row for row in upcoming if self.can_view_appointment(c, user, row)]
                if personal:
                    upcoming = [row for row in upcoming if row['owner_id'] == user['id'] or row['created_by'] == user['id']]
                upcoming = upcoming[:5]
            clients_recent = clients[:10]
            conversations = conversation_rows(c, user)
            if personal:
                conversations = [row for row in conversations if row['client_id'] in personal_client_ids]
            unread_messages = sum(row['unread'] for row in conversations if row['visibility'] == 'client')
            unread_internal = sum(row['unread'] for row in conversations if row['visibility'] == 'internal')
            if admin:
                pending_received = c.execute("SELECT COUNT(*) FROM pendencies p JOIN users u ON u.id=p.client_id WHERE u.deleted_at='' AND p.status='Recebida' AND (p.case_id IS NULL OR p.case_id IN (SELECT id FROM cases WHERE deleted_at=''))").fetchone()[0]
            else:
                pending_received = c.execute("SELECT COUNT(*) FROM pendencies p JOIN users u ON u.id=p.client_id WHERE u.deleted_at='' AND p.status='Recebida' AND (p.case_id IS NULL OR p.case_id IN (SELECT id FROM cases WHERE deleted_at='')) AND (" + self.scoped_condition('p') + ")", (user['id'], user['id'], user['id'])).fetchone()[0]
            new_contacts = c.execute("SELECT COUNT(*) FROM contacts WHERE status='novo'").fetchone()[0] if is_super(user) else 0
            staff_names = {row['id']: row['name'] for row in c.execute("SELECT id,name FROM users WHERE role IN ('admin','staff') AND deleted_at='' ORDER BY name")}
            stale_cases = [case for case in cases if status_color(case['status']) == 'yellow' and hours_since(case['last_activity_at'] or case['created']) >= stale_hours]
            tasks = self.task_rows(c, user)
            if personal:
                tasks = [task for task in tasks if task['assigned_to'] == user['id'] or task['created_by'] == user['id']]
            open_tasks = [task for task in tasks if task['status'] != 'concluida']
            overdue_tasks = [task for task in open_tasks if task_is_overdue(task)]
            due_today = [task for task in open_tasks if str(task['due_at'])[:10] == datetime.datetime.now().strftime('%Y-%m-%d')]
            if is_employee(user):
                explicit = c.execute("SELECT allowed FROM permissions WHERE user_id=? AND action='view_reports'", (user['id'],)).fetchone()
                can_reports = bool(explicit and explicit['allowed'])
            else:
                can_reports = has_permission(c, user, 'view_reports')
        unassigned = sum(1 for case in cases if not case['responsible_id'] and case['status'] not in ('Concluído', 'Suspenso'))
        documents_url = '/admin/arquivos?status=aguardando_analise' + ('' if admin else '&acao=meus')
        kpis = [
            ('Mensagens não lidas', unread_messages, 'red', '/admin/mensagens?filtro=nao_lidas&status=todas'),
            ('Casos em andamento', counts.get('yellow', 0), 'yellow', '/admin/casos?status=Em+andamento'),
            ('Aguardando cliente', counts.get('blue', 0), 'blue', '/admin/casos?status=Aguardando+cliente'),
            ('Concluídos', counts.get('green', 0), 'green', '/admin/casos?status=Conclu%C3%ADdo'),
            ('Documentos a analisar', docs_pending, 'lavender', documents_url),
            ('Pendências recebidas', pending_received, 'blue', '/admin/pendencias?status=Recebida'),
            ('Tarefas atrasadas', len(overdue_tasks), 'red', '/admin/tarefas?status=atrasadas'),
            ('Relatos internos', unread_internal, 'lavender', '/admin/mensagens?tipo=interno&filtro=nao_lidas&status=todas'),
        ]
        if is_super(user):
            kpis.append(('Contatos do site', new_contacts, 'blue', '/admin/contatos?status=novo'))
        icons = {'Mensagens não lidas': 'messages', 'Casos em andamento': 'cases', 'Aguardando cliente': 'cases', 'Concluídos': 'shield', 'Documentos a analisar': 'documents', 'Pendências recebidas': 'tasks', 'Tarefas atrasadas': 'tasks', 'Relatos internos': 'messages', 'Contatos do site': 'support'}
        kpi_html = ''.join('<a class="panel-kpi tone-' + color + '" href="' + esc(path) + '"' + (' data-hide-zero hidden' if label in ('Relatos internos', 'Contatos do site') and not value else ' data-hide-zero' if label in ('Relatos internos', 'Contatos do site') else '') + '><span class="panel-kpi-icon">' + panel_icon(icons.get(label, 'report')) + '</span><span class="panel-kpi-value"' + (' data-unread-client' if label == 'Mensagens não lidas' else ' data-unread-internal' if label == 'Relatos internos' else ' data-new-contacts' if label == 'Contatos do site' else '') + '>' + str(value) + '</span><span class="panel-kpi-label">' + esc(label) + '</span><span class="panel-kpi-action">Abrir seção →</span></a>' for label, value, color, path in kpis)
        attention = []
        if unread_messages:
            attention.append(('red', str(unread_messages) + ' mensagem(ns) não lida(s) aguardando a equipe.', '/admin/mensagens?filtro=nao_lidas&status=todas'))
        if docs_pending:
            attention.append(('yellow', str(docs_pending) + ' documento(s) aguardando análise.', documents_url))
        if pending_received:
            attention.append(('blue', str(pending_received) + ' pendência(s) recebida(s) para conferir.', '/admin/pendencias?status=Recebida'))
        if overdue_tasks:
            attention.append(('red', str(len(overdue_tasks)) + ' tarefa(s) atrasada(s) exigindo atenção.', '/admin/tarefas?status=atrasadas'))
        elif due_today:
            attention.append(('yellow', str(len(due_today)) + ' tarefa(s) com prazo para hoje.', '/admin/tarefas'))
        if unassigned:
            attention.append(('yellow', str(unassigned) + ' atendimento(s) sem responsável.', '/admin/casos?responsavel=sem'))
        if stale_cases:
            attention.append(('yellow', str(len(stale_cases)) + ' caso(s) em andamento sem movimentação recente.', '/admin/casos?status=Em+andamento'))
        if unread_internal:
            attention.append(('lavender', str(unread_internal) + ' relato(s) interno(s) não lido(s).', '/admin/mensagens?tipo=interno&filtro=nao_lidas&status=todas'))
        if new_contacts:
            attention.append(('blue', str(new_contacts) + ' contato(s) novo(s) pelo site.', '/admin/contatos?status=novo'))
        attention_html = ''.join('<li><span class="panel-dot ' + color + '"></span><span>' + esc(text) + ' <a class="text-link" href="' + esc(href) + '">Abrir</a></span></li>' for color, text, href in attention) or '<li><span class="panel-dot green"></span><span>Nenhuma pendência crítica no momento.</span></li>'
        priority = {'red': 0, 'yellow': 1, 'blue': 2, 'green': 3, 'gray': 4}
        priority_cases = sorted(cases, key=lambda case: (priority.get(status_color(case['status']), 5), 0 if not case['responsible_id'] else 1, -hours_since(case['last_activity_at'] or case['created'])))[:5]
        priority_html = ''.join('<a class="panel-priority status-border-' + status_color(case['status']) + '" href="/admin/caso/historico?case_id=' + str(case['id']) + '"><span><strong>' + esc(case['title']) + '</strong><small>' + esc(case['client_name']) + ' · ' + esc(staff_names.get(case['responsible_id'], 'Sem responsável')) + '</small></span>' + status_badge(case['status']) + '</a>' for case in priority_cases) or '<p class="muted">Nenhum atendimento cadastrado.</p>'
        recent = sorted((row for row in conversations if row['status'] == 'open'), key=lambda row: not bool(row['unread']))[:5]
        message_html = conversation_cards(recent, user) + '<p><a class="text-link" href="/admin/mensagens">Ver todas as conversas →</a></p>'
        upcoming_html = ''.join('<div class="panel-appointment"><span class="panel-date">' + esc(fmt_when(appointment['when_at'])) + '</span><span><strong>' + esc(appointment['title']) + '</strong><small>' + esc(appointment['client'] or 'Evento interno') + '</small></span></div>' for appointment in upcoming) or '<p class="muted">Nenhum compromisso próximo.</p>'
        total_cases = max(1, len(cases))
        rings = panel_ring(counts.get('yellow', 0) * 100 / total_cases, 'Em andamento', counts.get('yellow', 0)) + panel_ring(counts.get('blue', 0) * 100 / total_cases, 'Aguardando cliente', counts.get('blue', 0)) + panel_ring(counts.get('green', 0) * 100 / total_cases, 'Concluídos', counts.get('green', 0))
        quick = [('/admin/casos', 'Casos', 'cases'), ('/admin/mensagens', 'Conversas', 'messages'), ('/admin/arquivos', 'Documentos', 'documents'), ('/admin/compromissos', 'Agenda', 'calendar')]
        if admin:
            quick.insert(0, ('/admin/clientes', 'Clientes', 'clients'))
        quick_html = ''.join('<a class="panel-quick" href="' + esc(href) + '">' + panel_icon(icon) + '<strong>' + esc(label) + '</strong></a>' for href, label, icon in quick)
        search = '<form method="get" action="/admin/busca" class="admin-search"><label>Pesquisar<input type="search" name="q" placeholder="Cliente, caso, mensagem ou documento"></label><button class="btn" type="submit">Pesquisar</button></form>'
        today_key = datetime.datetime.now().strftime('%Y-%m-%d')
        today_agenda = [row for row in upcoming if str(row['when_at'])[:10] == today_key]
        if personal:
            personal_kpis = [
                ('Mensagens não lidas', unread_messages, 'red', '/admin/mensagens?filtro=nao_lidas&status=todas'),
                ('Compromissos hoje', len(today_agenda), 'blue', '/admin/compromissos'),
                ('Tarefas abertas', len(open_tasks), 'yellow', '/admin/tarefas'),
                ('Tarefas atrasadas', len(overdue_tasks), 'red', '/admin/tarefas?status=atrasadas'),
            ]
            personal_icons = {'Mensagens não lidas': 'messages', 'Compromissos hoje': 'calendar', 'Tarefas abertas': 'tasks', 'Tarefas atrasadas': 'tasks'}
            kpi_html = ''.join('<a class="panel-kpi tone-' + color + '" href="' + esc(path) + '"><span class="panel-kpi-icon">' + panel_icon(personal_icons.get(label, 'report')) + '</span><span class="panel-kpi-value"' + (' data-unread-client' if label == 'Mensagens não lidas' else '') + '>' + str(value) + '</span><span class="panel-kpi-label">' + esc(label) + '</span><span class="panel-kpi-action">Abrir seção →</span></a>' for label, value, color, path in personal_kpis)
        today_html = ''.join('<div class="panel-appointment"><span class="panel-date">' + esc(fmt_when(row['when_at'])) + '</span><span><strong>' + esc(row['title']) + '</strong><small>' + esc(row['client'] or 'Evento interno') + '</small></span></div>' for row in today_agenda) or '<p class="muted">Nenhum compromisso para hoje.</p>'
        focus_tasks = sorted(open_tasks, key=lambda task: task['due_at'] or '9999-12-31')[:5]
        task_agenda_html = ''.join('<a class="panel-priority status-border-' + ('red' if task_is_overdue(task) else 'yellow') + '" href="/admin/tarefa?task_id=' + str(task['id']) + '"><span><strong>' + esc(task['title']) + '</strong><small>' + esc(task['case_title'] or task['client_name'] or 'Sem vínculo') + ((' · ' + esc(fmt_when(task['due_at']))) if task['due_at'] else '') + '</small></span>' + task_status_badge(task) + '</a>' for task in focus_tasks) or '<p class="muted">Nenhuma tarefa em aberto.</p>'
        view_toggle = '<div class="view-toggle"><a class="' + ('active' if not personal else '') + '" href="/admin?visao=equipe">Visão geral do escritório</a><a class="' + ('active' if personal else '') + '" href="/admin?visao=minha">Minha rotina</a></div>' if is_super(user) else ''
        title = 'Minha rotina' if personal else ('Painel do advogado' if is_lawyer(user) else 'Painel do funcionário' if is_employee(user) else 'Gestão do escritório')
        subtitle = ('Sua agenda, tarefas e mensagens em um só lugar.' if personal else 'Acompanhe os atendimentos do escritório, organize as atividades e veja o que precisa de atenção hoje.' if is_lawyer(user) else 'Organize as atividades operacionais e acompanhe o que precisa de atenção hoje.' if is_employee(user) else 'Acompanhe os atendimentos, a equipe e as atividades que precisam de atenção.')
        hero = '<div class="panel-hero"><div><p class="eyebrow">' + esc(title) + '</p><h1>Olá, ' + esc((user['name'] or '').split()[0]) + '!</h1><p>' + esc(subtitle) + '</p></div><img src="/static/img/office_meeting.webp" alt=""></div>'
        return '<div class="admin-dashboard panel-dashboard">' + hero + view_toggle + search + '<div class="panel-kpis">' + kpi_html + '</div><div class="panel-dash-grid panel-dash-grid-3"><div class="panel-col">' + panel_card('Agenda de hoje', '<div class="panel-agenda-list">' + today_html + '</div>', '<a class="text-link" href="/admin/compromissos">Abrir agenda →</a>') + panel_card('Tarefas e prazos', '<div class="panel-priority-list">' + task_agenda_html + '</div>', '<a class="text-link" href="/admin/tarefas">Ver tarefas →</a>') + '</div><div class="panel-col">' + panel_card('Precisam de atenção', '<ul class="panel-attention">' + attention_html + '</ul>', '<a class="text-link" href="/admin/casos">Ver detalhes →</a>') + panel_card('Conversas recentes', message_html) + '</div><div class="panel-col">' + panel_card('Próximos compromissos', '<div class="panel-agenda-list">' + upcoming_html + '</div>', '<a class="text-link" href="/admin/compromissos">Ver agenda →</a>') + panel_card('Atendimentos prioritários', '<div class="panel-priority-list">' + priority_html + '</div>', '<a class="text-link" href="/admin/casos">Ver todos →</a>') + '</div></div><div class="panel-bottom-grid">' + panel_card('Acompanhamento dos atendimentos', '<div class="panel-rings">' + rings + '</div>', '<a class="text-link" href="/admin/relatorios">Ver relatório →</a>' if can_reports else '') + panel_card('Acesso rápido', '<div class="panel-quick-grid">' + quick_html + '</div>') + '</div></div>'

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        user = self.user()
        if path.startswith('/static/'):
            target = (ROOT / path.lstrip('/')).resolve()
            if not target.is_relative_to((ROOT / 'static').resolve()) or not target.is_file():
                return self.send('Não encontrado', 404)
            ctype = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
            return self.send_file(target, ctype, cache='public, max-age=3600')
        if path == '/favicon.ico':
            return self.send_file(ROOT / 'static' / 'favicon.svg', 'image/svg+xml', cache='public, max-age=3600')
        if path == '/robots.txt':
            body = 'User-agent: *\nDisallow: /admin\nDisallow: /cliente\nDisallow: /arquivo\nDisallow: /senha\nSitemap: ' + self.base_url() + '/sitemap.xml\n'
            return self.send(body, ctype='text/plain; charset=utf-8', cache='public, max-age=3600')
        if path == '/sitemap.xml':
            pages = ['/', '/escritorio', '/equipe', '/areas', '/conteudos', '/faq', '/contato', '/privacidade', '/termos', '/entrar', '/cadastro'] + ['/equipe/' + detail['slug'] for detail in TEAM_DETAILS]
            items = ''.join('<url><loc>' + esc(self.base_url() + item) + '</loc></url>' for item in pages)
            body = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + items + '</urlset>'
            return self.send(body, ctype='application/xml; charset=utf-8', cache='public, max-age=3600')
        if path == '/chat/status':
            user = self.user()
            with db() as c:
                online = setting(c, 'chat_online', '1') == '1' and self.staff_online_count() > 0
                session = self.chat_session(c, user)
                unread = c.execute("SELECT COUNT(*) FROM guest_messages WHERE guest_id=? AND sender_role='staff' AND read_by_guest=0", (session['id'],)).fetchone()[0] if session else 0
            return self.send_json({'ok': True, 'online': online, 'authenticated': bool(user and user['role'] == 'client'), 'session': bool(session), 'name': session['name'] if session else '', 'unread': unread, 'status': session['status'] if session else ''})
        if path == '/chat/mensagens':
            user = self.user()
            with db() as c:
                session = self.chat_session(c, user)
                if not session:
                    return self.send_json({'ok': False, 'error': 'session'}, 401)
                messages = c.execute('SELECT * FROM guest_messages WHERE guest_id=? ORDER BY id', (session['id'],)).fetchall()
                unread = c.execute("SELECT COUNT(*) FROM guest_messages WHERE guest_id=? AND sender_role='staff' AND read_by_guest=0", (session['id'],)).fetchone()[0]
                c.execute("UPDATE guest_messages SET read_by_guest=1 WHERE guest_id=? AND sender_role='staff'", (session['id'],))
                c.execute('UPDATE guest_sessions SET last_seen=CURRENT_TIMESTAMP WHERE id=?', (session['id'],))
            return self.send_json({'ok': True, 'html': guest_thread_html(session, messages), 'status': session['status'], 'unread': unread, 'updated': messages[-1]['created'] if messages else session['created']})
        if path == '/notificacoes':
            if not user:
                return self.send_json({'error': 'unauthorized'}, 401)
            with db() as c:
                stale_hours = max(1, int(setting(c, 'stale_hours', '48') or 48))
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
                if user['role'] == 'client':
                    for case in self.scoped_cases(c, user):
                        if status_color(case['status']) == 'blue' and hours_since(case['last_activity_at'] or case['created']) >= stale_hours:
                            notify(c, user['id'], 'waiting_client', 'Aguardando sua providência', case['title'], '/cliente', case['client_id'], case['id'], 'waiting-' + str(case['id']) + '-' + today)
                else:
                    for case in self.scoped_cases(c, user):
                        if status_color(case['status']) == 'yellow' and hours_since(case['last_activity_at'] or case['created']) >= stale_hours:
                            for uid in case_audience(c, case):
                                notify(c, uid, 'stale_case', 'Atendimento sem movimentação', case['title'], '/admin/casos', case['client_id'], case['id'], 'stale-case-' + str(case['id']) + '-' + str(uid) + '-' + today)
                    if user['role'] == 'admin':
                        stale_requests = c.execute("SELECT * FROM requests WHERE status IN ('Pendente','Em andamento') ORDER BY id DESC LIMIT 200").fetchall()
                    else:
                        stale_requests = c.execute("SELECT r.* FROM requests r WHERE r.status IN ('Pendente','Em andamento') AND (r.client_id IN (SELECT client_id FROM assignments WHERE staff_id=?) OR r.case_id IN (SELECT id FROM cases WHERE responsible_id=? UNION SELECT case_id FROM case_assignments WHERE staff_id=?)) ORDER BY r.id DESC LIMIT 200", (user['id'], user['id'], user['id'])).fetchall()
                    for request_row in stale_requests:
                        last = request_row['last_activity_at'] or request_row['responded_at'] or request_row['created']
                        if hours_since(last) >= stale_hours:
                            for uid in client_audience(c, request_row['client_id'], request_row['case_id']):
                                notify(c, uid, 'stale_request', 'Solicitação sem movimentação', request_row['subject'], '/admin', request_row['client_id'], request_row['case_id'], 'stale-request-' + str(request_row['id']) + '-' + str(uid) + '-' + today)
                if user['role'] == 'client':
                    reminder_appointments = c.execute("SELECT * FROM appointments WHERE client_id=? AND privacy='client' AND status='pendente' AND deleted_at='' AND reminder_at<>'' AND reminder_at<=? AND reminder_sent=0", (user['id'], now_str)).fetchall()
                else:
                    reminder_appointments = c.execute("SELECT * FROM appointments WHERE status='pendente' AND deleted_at='' AND reminder_at<>'' AND reminder_at<=? AND reminder_sent=0", (now_str,)).fetchall()
                    reminder_appointments = [appointment for appointment in reminder_appointments if self.can_view_appointment(c, user, appointment)]
                for appointment in reminder_appointments:
                    privacy = appointment['privacy'] or 'internal'
                    if appointment['client_id'] and privacy == 'client':
                        notify(c, appointment['client_id'], 'appointment', 'Lembrete de compromisso', appointment['title'] + ' — ' + appointment['when_at'], '/cliente/compromissos', appointment['client_id'], appointment['case_id'], 'appointment-reminder-' + str(appointment['id']) + '-client')
                        for uid in client_audience(c, appointment['client_id'], appointment['case_id']):
                            if uid != appointment['client_id']:
                                notify(c, uid, 'appointment', 'Lembrete de compromisso', appointment['title'] + ' — ' + appointment['when_at'], '/admin/compromisso?appointment_id=' + str(appointment['id']), appointment['client_id'], appointment['case_id'], 'appointment-reminder-' + str(appointment['id']) + '-u' + str(uid))
                    else:
                        owner = appointment['owner_id'] or appointment['created_by']
                        if owner:
                            notify(c, owner, 'appointment', 'Lembrete de compromisso', appointment['title'] + ' — ' + appointment['when_at'], '/admin/compromisso?appointment_id=' + str(appointment['id']), appointment['client_id'], appointment['case_id'], 'appointment-reminder-' + str(appointment['id']) + '-owner')
                        if privacy != 'private':
                            for participant in c.execute('SELECT user_id FROM appointment_participants WHERE appointment_id=?', (appointment['id'],)).fetchall():
                                if participant['user_id'] != owner:
                                    notify(c, participant['user_id'], 'appointment', 'Lembrete de compromisso', appointment['title'] + ' — ' + appointment['when_at'], '/admin/compromisso?appointment_id=' + str(appointment['id']), appointment['client_id'], appointment['case_id'], 'appointment-reminder-' + str(appointment['id']) + '-p' + str(participant['user_id']))
                    c.execute('UPDATE appointments SET reminder_sent=1 WHERE id=?', (appointment['id'],))
                rows = c.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY CASE WHEN read_at='' THEN 0 ELSE 1 END,id DESC LIMIT 20", (user['id'],)).fetchall()
                unread = c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read_at=''", (user['id'],)).fetchone()[0]
                conversation_counts = conversation_unread_totals(c, user)
                unread_client = conversation_counts['client']
                unread_internal = conversation_counts['internal']
                new_contacts = c.execute("SELECT COUNT(*) FROM contacts WHERE status='novo'").fetchone()[0] if is_super(user) else None
            items = [{'id': row['id'], 'type': row['type'], 'title': row['title'], 'body': row['body'], 'url': row['url'], 'created': row['created'], 'unread': not row['read_at']} for row in rows]
            return self.send_json({'unread': unread, 'unread_client': unread_client, 'unread_internal': unread_internal, 'new_contacts': new_contacts, 'items': items})
        if user and user['must_change'] and path not in ('/senha', '/sair'):
            return self.redirect('/senha')
        if path == '/sair':
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
            except Exception:
                cookie = SimpleCookie()
            sid = cookie.get('sid')
            if sid:
                with SESS_LOCK:
                    SESS.pop(sid.value, None)
            if user:
                with db() as c:
                    self.audit_action(c, user['id'], 'logout', user['email'])
            return self.redirect('/', {'Set-Cookie': self.session_cookie('', 0)})
        if path == '/':
            areas = ''.join(f'<a class="area" href="/areas"><span aria-hidden="true">{index:02d}</span><h3>{esc(a)}</h3><p>{esc(d)}</p></a>' for index, (a,d) in enumerate(AREAS[:4], 1))
            team = ''.join(f'<a class="person" href="/equipe/{detail["slug"]}"><img src="/static/img/{image}" alt="" loading="lazy" decoding="async"><h3>{esc(n)}</h3><small>{esc(oab)}</small></a>' for (n,oab,image), detail in zip(TEAM[2:6], TEAM_DETAILS[2:6]))
            content = f'''<section class="hero"><div class="wrap hero-grid"><div><p class="eyebrow">FAMÍLIA, CONFIANÇA E DEDICAÇÃO</p><h1>Uma história dedicada às <em>pessoas.</em></h1><p class="lead">Há mais de 40 anos, nossa família constrói uma trajetória no Direito com ética, escuta e atenção à história de cada cliente.</p><div class="actions"><a class="btn" href="/escritorio">Conheça nossa história</a><a class="btn secondary" href="/contato">Entre em contato</a></div></div><div class="hero-art"><img src="/static/img/emblem.webp" alt="Emblema institucional Bomfim & Lacerda" decoding="async"></div></div></section><section class="wrap section home-areas"><p class="eyebrow">NOSSA ATUAÇÃO</p><h2>Orientação jurídica com atenção ao que importa.</h2><p class="home-intro">Cada história é única. Nosso compromisso começa por ouvir e compreender suas necessidades.</p><div class="cards">{areas}</div><p><a class="text-link" href="/areas">Conheça todas as áreas de atuação →</a></p></section><section class="section soft home-story"><div class="wrap split"><div><p class="eyebrow">NOSSA HISTÓRIA</p><h2>Uma família, várias gerações e um compromisso em comum.</h2><p>Fundado por João e Rozária, o escritório cresceu com a participação dos filhos e da neta, reunindo experiência e cuidado em cada atendimento.</p><a class="btn dark" href="/escritorio">Nossa trajetória</a></div><img class="feature-img" src="/static/img/founders_portrait.webp" alt="João Alves de Lacerda e Rozária Neta Bomfim Lacerda, fundadores do escritório" loading="lazy" decoding="async"></div></section><section class="wrap section home-team"><p class="eyebrow">PESSOAS E EXPERIÊNCIA</p><h2>Uma equipe feita de histórias.</h2><p class="home-intro">Conheça os profissionais que dão continuidade a essa trajetória.</p><div class="people">{team}</div><a class="text-link" href="/equipe">Ver todos os profissionais →</a></section><section class="section cta"><div class="wrap"><h2>Informação e proximidade em cada etapa</h2><p>Clientes cadastrados podem consultar comunicados, documentos e compromissos compartilhados pelo escritório.</p><a class="btn" href="/entrar">Acessar área do cliente</a></div></section>'''
            return self.page('Início', content, user)
        if path == '/escritorio':
            content = '''<section class="story-hero"><div class="wrap story-hero-grid"><div><p class="eyebrow">NOSSA HISTÓRIA</p><h1>Uma história de família, feita de <em>pessoas.</em></h1><p>Há mais de 40 anos, o Direito aproxima nossa família de muitas outras histórias. Cada uma merece ser ouvida com respeito e atenção.</p><a class="story-hero-link" href="#trajetoria">Conheça nossa trajetória <span aria-hidden="true">↓</span></a></div><figure class="story-founders"><img src="/static/img/founders_portrait.webp" alt="João Alves de Lacerda e Rozária Neta Bomfim Lacerda, fundadores do escritório" decoding="async"><figcaption>João e Rozária <span>·</span> Fundadores</figcaption></figure></div></section><section class="wrap story-section" id="trajetoria"><div class="story-heading"><p class="eyebrow">DE GERAÇÃO EM GERAÇÃO</p><h2>O que começa com uma família pode alcançar muitas outras.</h2></div><div class="story-columns"><p class="story-lead">Nossa trajetória começou com João Alves de Lacerda e Rozária Neta Bomfim Lacerda. Juntos, fundaram um escritório sustentado pela dedicação ao Direito e pela proximidade com as pessoas.</p><div><p>Com o passar dos anos, esse compromisso encontrou continuidade nos filhos, Joatan e João Joab, e na neta Ninmery. Cada geração contribui com seu olhar, mantendo vivos o respeito, a responsabilidade e a confiança que fazem parte da nossa história.</p><p>Ao lado da advogada associada Sintia Amaro Sales, nossa equipe segue trabalhando com um propósito comum: acolher cada demanda com atenção e oferecer orientação jurídica clara e responsável.</p></div></div></section><section class="story-mission"><div class="wrap story-mission-grid"><div><p class="eyebrow">NOSSO PROPÓSITO</p><h2>O Direito começa com uma boa escuta.</h2></div><div><h3>Nossa missão</h3><p>Orientar cada pessoa com clareza, dedicação e respeito, compreendendo suas necessidades e conduzindo cada atendimento com responsabilidade e atenção.</p></div></div></section><section class="wrap story-section"><div class="story-heading"><p class="eyebrow">O QUE NOS ORIENTA</p><h2>Valores que atravessam gerações.</h2><p>Mais do que palavras, são compromissos que procuramos levar para cada encontro e cada etapa do trabalho.</p></div><div class="value-grid"><article><span>01</span><h3>Ética e transparência</h3><p>Agir com honestidade e explicar os caminhos de forma clara.</p></article><article><span>02</span><h3>Respeito e escuta</h3><p>Reconhecer a pessoa e a história que existem por trás de cada demanda.</p></article><article><span>03</span><h3>Dedicação e cuidado</h3><p>Tratar cada atendimento com atenção, responsabilidade e compromisso.</p></article><article><span>04</span><h3>Legado e continuidade</h3><p>Honrar o que aprendemos, mantendo abertura para seguir evoluindo.</p></article></div><div class="story-end"><div><p class="eyebrow">PESSOAS E EXPERIÊNCIA</p><h2>Conheça quem faz parte dessa história.</h2></div><a class="btn dark" href="/equipe">Conheça nossa equipe</a></div></section>'''
            return self.page('O escritório', content, user)
        if path == '/equipe':
            photo_icon = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4M10.5 7.5v6M7.5 10.5h6"/></svg>'
            items = []
            for (name, oab, image), detail in zip(TEAM, TEAM_DETAILS):
                caption = 'João Alves de Lacerda e Rozária Neta Bomfim Lacerda · Fundadores' if image == 'founders_portrait.webp' else name
                profile_url = '/equipe/' + detail['slug']
                photo_url = '/static/img/' + image
                items.append(f'''<article class="team-tile"><div class="team-tile-image"><a class="team-photo-link" href="{profile_url}" aria-label="Conhecer o perfil de {esc(name)}"><img src="{photo_url}" alt="{esc(caption)}" loading="lazy" decoding="async"></a><a class="team-photo-expand" href="{photo_url}" data-photo-lightbox data-photo-caption="{esc(caption)}" data-hint="Ampliar foto" aria-label="Ampliar foto de {esc(caption)}">{photo_icon}</a></div><div class="team-tile-body"><p class="team-role">{esc(detail["role"])}</p><h3><a href="{profile_url}">{esc(name)}</a></h3><p class="team-tile-oab">{esc(oab)}</p><a class="team-tile-link" href="{profile_url}">Conhecer perfil <span aria-hidden="true">→</span></a></div></article>''')
            content = f'''<section class="team-intro team-intro-family"><div class="wrap"><p class="eyebrow">FAMÍLIA, CONFIANÇA E DEDICAÇÃO</p><h1>Uma equipe, muitas histórias.</h1><p>Uma família que encontrou no Direito um propósito em comum — e uma equipe dedicada a acolher cada pessoa com atenção.</p><a href="/escritorio" class="team-intro-link">Conheça nossa história <span aria-hidden="true">→</span></a></div></section><section class="wrap team-section"><div class="team-section-heading"><div><p class="eyebrow">PESSOAS E EXPERIÊNCIA</p><h2>Conheça nossos profissionais</h2></div><p>Selecione uma foto ou perfil para conhecer a trajetória de cada integrante.</p></div><div class="team-tiles">{''.join(items)}</div><div class="team-contact"><div><p class="eyebrow">ESTAMOS À DISPOSIÇÃO</p><h2>Vamos conversar?</h2><p>Entre em contato para conhecer nossos canais de atendimento.</p></div><a class="btn" href="/contato">Entre em contato</a></div></section>'''
            return self.page('Nossa equipe', content, user)
        if path.startswith('/equipe/'):
            member = next(((person, detail) for person, detail in zip(TEAM, TEAM_DETAILS) if path == '/equipe/' + detail['slug']), None)
            if member:
                (name, oab, image), detail = member
                icons = (
                    '<path d="M6 3h9l3 3v15H6zM14 3v4h4M9 11h6M9 15h6"/>',
                    '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5h6v2M3 12h18M10 12v2h4v-2"/>',
                    '<path d="M12 3 4 6v5c0 5 3 8 8 10 5-2 8-5 8-10V6l-8-3ZM9 12l2 2 4-4"/>',
                    '<path d="M3 4h2l2 11h11l2-8H6M9 20h.01M17 20h.01"/><circle cx="9" cy="20" r="1"/><circle cx="17" cy="20" r="1"/>',
                )
                areas = ''.join(f'<li><span class="profile-icon"><svg viewBox="0 0 24 24" aria-hidden="true">{icon}</svg></span><span>{esc(area)}</span></li>' for area, icon in zip(TEAM_AREAS, icons))
                contacts = professional_contacts(detail, include_office=True)
                caption = 'João Alves de Lacerda e Rozária Neta Bomfim Lacerda · Fundadores' if image == 'founders_portrait.webp' else name
                content = f'''<section class="team-intro profile-intro"><div class="wrap"><a class="profile-back" href="/equipe">← Voltar para a equipe</a><p class="eyebrow">{esc(detail["role"])}</p><h1>{esc(name)}</h1><p>{esc(oab)}</p></div></section><section class="wrap profile-detail"><div class="profile-detail-image"><a class="profile-photo-open" href="/static/img/{image}" data-photo-lightbox data-photo-caption="{esc(caption)}" aria-label="Ampliar foto de {esc(caption)}"><img src="/static/img/{image}" alt="{esc(caption)}" decoding="async"><span>Ampliar foto <span aria-hidden="true">↗</span></span></a></div><div class="profile-detail-content"><div class="profile-detail-block"><p class="eyebrow">TRAJETÓRIA</p><h2>Sobre {esc(name)}</h2><p>{esc(detail["bio"])}</p></div><div class="profile-detail-block"><p class="eyebrow">EXPERIÊNCIA</p><h2>Áreas de atuação</h2><ul class="profile-area-list">{areas}</ul></div><div class="profile-detail-block"><p class="eyebrow">FALE CONOSCO</p><h2>Contato</h2><div class="profile-contact-links">{contacts}</div></div></div></section>'''
                return self.page(name, content, user)
        if path == '/areas':
            return self.page('Áreas de atuação', '<section class="wrap section"><p class="eyebrow">COMO PODEMOS ORIENTAR</p><h1>Áreas de atuação</h1><p>Conheça as áreas apresentadas nos materiais institucionais do escritório. Cada situação exige análise individual.</p><div class="cards">' + ''.join(card(a, '<p>' + esc(d) + '</p>') for a, d in AREAS) + '</div></section>', user)
        if path == '/conteudos':
            with db() as c:
                posts = c.execute('SELECT * FROM posts WHERE published=1 ORDER BY created DESC').fetchall()
            body = ''.join(card(p['title'], f'<p class="muted">{esc(p["category"])} · {esc(p["created"][:10])}</p><p>{esc(p["body"])}</p>') for p in posts) or '<p>Ainda não há publicações. Os conteúdos serão disponibilizados após revisão e publicação pela equipe.</p>'
            return self.page('Conteúdo jurídico', '<section class="wrap section"><h1>Conteúdo jurídico</h1><p>Informações educativas e orientações gerais. Cada caso exige avaliação individual.</p><div class="cards">' + body + '</div></section>', user)
        if path == '/faq':
            with db() as c:
                faqs = c.execute("SELECT * FROM faqs WHERE published=1 ORDER BY sort_order,id").fetchall()
            grouped = {}
            for faq in faqs:
                grouped.setdefault(faq['category'] or 'Geral', []).append(faq)
            category_order = [category for category in FAQ_CATEGORIES if category in grouped] + sorted(category for category in grouped if category not in FAQ_CATEGORIES)
            sections = []
            for category in category_order:
                items = ''.join('<details class="faq-item"><summary>' + esc(faq['question']) + '<span class="faq-chevron">+</span></summary><div class="faq-answer"><p>' + esc(faq['answer']) + '</p></div></details>' for faq in grouped[category])
                sections.append('<section class="faq-category"><div class="faq-category-head"><span class="eyebrow">PERGUNTAS FREQUENTES</span><h2>' + esc(category) + '</h2></div>' + items + '</section>')
            body = ''.join(sections) or '<p>As perguntas frequentes serão publicadas após revisão jurídica pela equipe.</p>'
            cta = '<section class="faq-cta"><div><p class="eyebrow">AINDA COM DÚVIDAS?</p><h2>Não encontrou a resposta que procurava?</h2><p>Fale com a nossa equipe pelos canais oficiais. Teremos prazer em orientar você.</p></div><div class="quick-actions"><a class="btn" href="/contato">Falar com o escritório</a><a class="btn ghost" href="https://wa.me/5588998022020">WhatsApp</a><a class="btn ghost" href="/entrar">Área do Cliente</a></div></section>'
            content = '<section class="faq-hero"><div class="wrap"><p class="eyebrow">CENTRAL DE AJUDA</p><h1>Perguntas frequentes</h1><p>Informações claras sobre atendimento, processos, portal do cliente e segurança.</p></div></section><section class="wrap section faq-section">' + body + cta + '</section><div class="wrap section">' + scam_notice() + '</div>'
            return self.page('Perguntas frequentes', content, user)
        if path == '/contato':
            cities = ('Independência / CE', 'Crateús / CE', 'Fortaleza / CE', 'Tauá / CE', 'Pimenteiras / PI')
            addresses = ''.join(f'<article class="office-card"><span class="contact-icon">{ui_icon("location")}</span><div><h3>{esc(city)}</h3><address>{esc(address)}</address></div></article>' for city, address in zip(cities, ADDRESSES))
            professionals = ''.join(f'<article class="contact-person"><h3><a href="/equipe/{detail["slug"]}">{esc(name)}</a></h3><div class="profile-contact-links">{professional_contacts(detail)}</div></article>' for (name, _, _), detail in zip(TEAM, TEAM_DETAILS))
            f = form('/contato', field('Nome', 'name') + field('E-mail', 'email', 'email') + field('Telefone (opcional)', 'phone', 'tel', required=False) + '<label>Mensagem<textarea name="message" rows="5" required></textarea></label><div class="hp"><label>Site<input name="website" tabindex="-1" autocomplete="off"></label></div><label class="check"><input type="checkbox" name="consent" value="1" required> Li o aviso de privacidade e concordo com o contato.</label><p class="muted">Você poderá acompanhar a conversa por um link após o envio. Não envie documentos ou dados sensíveis por este formulário.</p>', 'Enviar mensagem')
            content = f'''<section class="team-intro contact-intro"><div class="wrap"><p class="eyebrow">ESTAMOS À DISPOSIÇÃO</p><h1>Entre em contato</h1><p>Encontre nossos endereços e fale diretamente com nossa equipe.</p></div></section><section class="wrap contact-section">{scam_notice()}<div class="contact-layout"><div><p class="eyebrow">ONDE ESTAMOS</p><h2>Nossos escritórios</h2><div class="office-list">{addresses}</div><p class="eyebrow">FALE COM A EQUIPE</p><h2>Contatos dos profissionais</h2><div class="contact-people">{professionals}</div></div><aside class="contact-form">{card("Envie sua mensagem", f)}</aside></div></section>'''
            return self.page('Contato', content, user)
        guest_match = re.fullmatch(r'/atendimento/([A-Za-z0-9_-]{20,100})(/mensagens)?', path)
        if guest_match:
            token = guest_match.group(1)
            with db() as c:
                session = guest_session_by_token(c, token)
                if not session:
                    return self.send('Atendimento não encontrado', 404)
                if session['expires_at'] and str(session['expires_at']) < datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
                    return self.send('Este link de atendimento expirou.', 410)
                messages = c.execute('SELECT * FROM guest_messages WHERE guest_id=? ORDER BY id', (session['id'],)).fetchall()
                c.execute("UPDATE guest_messages SET read_by_guest=1 WHERE guest_id=? AND sender_role='staff'", (session['id'],))
                c.execute('UPDATE guest_sessions SET last_seen=CURRENT_TIMESTAMP WHERE id=?', (session['id'],))
            if guest_match.group(2):
                payload = {'ok': True, 'status': session['status'], 'html': guest_thread_html(session, messages), 'updated': messages[-1]['created'] if messages else session['created']}
                return self.send_json(payload)
            status_label = 'Em atendimento' if session['status'] == 'open' else 'Atendimento encerrado'
            form_html = ''
            if session['status'] == 'open':
                form_html = form('/atendimento/responder', '<input type="hidden" name="token" value="' + esc(token) + '"><label>Mensagem<textarea name="body" rows="4" required></textarea></label>', 'Enviar mensagem')
            content = '<section class="wrap section narrow guest-chat-page"><p class="eyebrow">ATENDIMENTO</p><h1>Olá, ' + esc(session['name']) + '!</h1><p class="muted">Acompanhe abaixo a conversa com a equipe. Não é necessário ter cadastro.</p><div class="guest-chat panel" id="guest-chat" data-guest-endpoint="/atendimento/' + esc(token) + '/mensagens"><div class="guest-chat-head"><strong>' + esc(status_label) + '</strong><small>' + esc(session['email']) + '</small></div><div class="thread guest-thread" data-guest-thread>' + guest_thread_html(session, messages) + '</div>' + form_html + '<p class="muted chat-attachment-hint">Esta página atualiza automaticamente enquanto você estiver com ela aberta.</p></div><p><a class="text-link" href="/contato">Voltar ao contato</a></p></section>'
            return self.page('Atendimento', content, user)
        if path in ('/privacidade', '/termos'):
            return self.page('Informações legais', '<section class="wrap section"><h1>' + ('Política de privacidade' if path == '/privacidade' else 'Termos de uso') + '</h1><p><strong>Documento pendente de elaboração e validação jurídica.</strong> Esta aplicação é um ambiente local de testes e não deve receber dados reais de clientes.</p></section>', user)
        if path == '/entrar/mfa':
            if user:
                return self.redirect('/admin' if user['role'] != 'client' else '/cliente')
            token = self.mfa_token()
            moment = time.monotonic()
            with MFA_LOCK:
                challenge = MFA_CHALLENGES.get(token)
                if challenge and moment > challenge['expires']:
                    MFA_CHALLENGES.pop(token, None)
                    challenge = None
            if not challenge:
                return self.redirect('/entrar')
            body = '<section class="wrap section narrow"><p class="eyebrow">VERIFICAÇÃO EM DUAS ETAPAS</p><h1>Confirme seu acesso</h1>' + card('Código de segurança', '<p class="muted">Informe o código de 6 dígitos do app autenticador ou um dos códigos de recuperação.</p>' + form('/entrar/mfa', field('Código', 'code'), 'Verificar')) + '<p><a class="text-link" href="/entrar">Voltar ao login</a></p></section>'
            return self.page('Verificação em duas etapas', body, None)
        if path == '/entrar':
            if user:
                return self.redirect('/admin' if user['role'] != 'client' else '/cliente')
            login_fields = '<label>E-mail<input type="email" name="email" autocomplete="username" required></label><label>Senha<input type="password" name="password" autocomplete="current-password" required></label>'
            login_form = form('/entrar', login_fields, 'Acessar minha conta')
            content = f'''<section class="login-page"><div class="wrap login-layout"><div class="login-intro"><p class="eyebrow">BOMFIM & LACERDA ADVOCACIA</p><h1>Seu espaço de acompanhamento.</h1><p>Acesse os serviços do escritório e acompanhe as informações compartilhadas com você.</p><ul class="login-benefits"><li>{ui_icon("document")}<span>Documentos e atendimentos em um só lugar</span></li><li>{ui_icon("message")}<span>Mensagens com a equipe</span></li><li>{ui_icon("updates")}<span>Atualizações e compromissos</span></li></ul></div><div class="login-panel panel"><span class="login-lock">{ui_icon("lock")}</span><p class="eyebrow">ÁREA RESTRITA</p><h2>Entrar na sua conta</h2><p class="muted">Informe seu e-mail e senha para continuar.</p>{login_form}<p class="login-register">Ainda não tem cadastro? <a class="text-link" href="/cadastro">Criar conta de cliente</a></p><p class="muted login-help">Recuperação de senha: solicite ao administrador. Envio por e-mail ainda não configurado.</p><div class="notice">Ambiente de testes: utilize apenas dados fictícios.</div></div></div></section>'''
            return self.page('Acesso restrito', content, user)
        if path == '/cadastro':
            if user:
                return self.redirect('/admin' if user['role'] != 'client' else '/cliente')
            content = card('Cadastro de cliente', form('/cadastro', field('Nome', 'name') + field('E-mail', 'email', 'email') + field('Senha', 'password', 'password') + field('Confirmar senha', 'confirm', 'password') + '<label class="check"><input type="checkbox" name="consent" value="1" required> Li o aviso de privacidade e concordo com o contato.</label>', 'Criar conta') + '<p class="muted">Já tem cadastro? <a class="text-link" href="/entrar">Entrar</a>.</p>')
            return self.page('Criar conta', '<section class="wrap section narrow"><p class="eyebrow">ÁREA DO CLIENTE</p><h1>Criar conta</h1><p>Cadastre-se para enviar documentos, solicitar informações e acompanhar as atualizações compartilhadas pelo escritório.</p><div class="notice">Ambiente de testes: utilize apenas dados fictícios.</div>' + content + '</section>', user)
        if path == '/senha':
            if not user:
                return self.redirect('/entrar')
            content = card('Alterar senha', form('/senha', field('Senha atual', 'current', 'password') + field('Nova senha', 'new', 'password') + field('Confirmar nova senha', 'confirm', 'password'), 'Alterar senha') + '<p class="muted">Use ao menos 12 caracteres. A sessão atual continuará válida.</p>')
            return self.page('Alterar senha', '<section class="wrap section narrow"><h1>Alterar senha</h1>' + content + '</section>', user)
        if re.fullmatch(r'/conversas/\d+/mensagens', path):
            if not user:
                return self.forbidden()
            conversation_id = int(path.split('/')[2])
            with db() as c:
                conversation = self.conversation_access(c, user, conversation_id)
                if not conversation:
                    return self.forbidden()
                messages = c.execute('SELECT id,sender_id,sender_role FROM messages WHERE conversation_id=? ORDER BY id', (conversation_id,)).fetchall()
                for message in messages:
                    if message['sender_id'] != user['id']:
                        c.execute('INSERT OR IGNORE INTO message_reads(user_id,message_id) VALUES(?,?)', (user['id'], message['id']))
                if user['role'] == 'client':
                    c.execute("UPDATE messages SET read_by_client=1 WHERE conversation_id=? AND sender_role!='client'", (conversation_id,))
                else:
                    c.execute("UPDATE messages SET read_by_staff=1 WHERE conversation_id=? AND sender_role='client'", (conversation_id,))
                c.execute("UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND read_at='' AND url=? AND type NOT IN ('message','internal')", (user['id'], '/conversas/' + str(conversation_id)))
                html, _ = self.conversation_messages_html(c, user, conversation_id)
                totals = conversation_unread_totals(c, user)
                remaining = conversation_unread(c, user, conversation_id)
            return self.send_json({'ok': True, 'html': html, 'unread_client': totals['client'], 'unread_internal': totals['internal'], 'conversation_unread': remaining, 'last_id': messages[-1]['id'] if messages else 0})
        if re.fullmatch(r'/conversas/\d+', path):
            if not user:
                return self.forbidden()
            conversation_id = int(path.rsplit('/', 1)[-1])
            with db() as c:
                conversation = self.conversation_access(c, user, conversation_id)
                if not conversation:
                    return self.forbidden()
                messages = c.execute('SELECT m.*,u.name AS sender_name FROM messages m LEFT JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=? ORDER BY m.id', (conversation_id,)).fetchall()
                attachment_rows = c.execute("SELECT ma.* FROM message_attachments ma JOIN messages m ON m.id=ma.message_id WHERE m.conversation_id=? ORDER BY ma.id", (conversation_id,)).fetchall()
                attachments_by_message = {}
                for attachment in attachment_rows:
                    attachments_by_message.setdefault(attachment['message_id'], []).append(attachment)
                can_reply = self.can_reply_conversation(c, user, conversation)
                unread = conversation_unread(c, user, conversation_id)
            messages_html = []
            is_internal = conversation['visibility'] == 'internal'
            for message in messages:
                if message['sender_id'] == user['id']:
                    sender = 'Você'
                elif user['role'] == 'client' and message['sender_role'] != 'client' and not message['reveal_identity']:
                    sender = 'Suporte do escritório'
                else:
                    sender = message['sender_name'] or 'Escritório'
                file_links = ''.join('<a class="message-attachment" href="/anexo/' + str(attachment['id']) + '">' + panel_icon('documents') + esc(attachment['filename']) + '</a>' for attachment in attachments_by_message.get(message['id'], []))
                task_link = ''
                if user['role'] in ('admin', 'staff') and is_internal:
                    task_link = '<button type="button" class="task-from-message" data-task-from-message="' + str(message['id']) + '" data-task-case="' + str(conversation['case_id'] or '') + '" data-task-client="' + str(conversation['client_id']) + '" data-task-body="' + esc(message['body'][:200]) + '">' + panel_icon('tasks') + 'Criar tarefa a partir desta mensagem</button>'
                side = 'client' if message['sender_role'] == 'client' else ('internal' if is_internal else 'office')
                if is_internal and message['sender_role'] == 'client':
                    side = 'client'
                unread_mark = '<span class="unread-mark" title="Não lida pela equipe"></span>' if not message['read_by_staff'] and user['role'] != 'client' and message['sender_id'] != user['id'] else ''
                created = esc((message['created'] or '')[:16])
                messages_html.append('<div class="message ' + side + '" data-avatar="' + esc(initials(sender)) + '">' +
                    '<span class="message-avatar" aria-hidden="true">' + esc(initials(sender)) + '</span>' +
                    '<div class="message-body"><p class="message-meta"><strong>' + esc(sender) + '</strong> · <time>' + created + '</time>' + unread_mark + '</p>' +
                    '<div class="bubble"><p>' + highlight_mentions(message['body']) + '</p>' + file_links + '</div>' +
                    ('<div class="message-tools">' + task_link + '</div>' if task_link else '') + '</div></div>')
            hidden = '<input type="hidden" name="conversation_id" value="' + str(conversation_id) + '">'
            reply_fields = hidden + '<label>Resposta<textarea name="body" rows="4"></textarea></label><label>Anexo (opcional)<input type="file" name="file"></label><p class="muted chat-attachment-hint">Permitidos: PDF, PNG, JPG e TXT, até 10 MB.</p>'
            if user['role'] != 'client' and conversation['visibility'] == 'client':
                reply_fields += '<label class="check"><input type="checkbox" name="reveal_identity" value="1"> Mostrar meu nome ao cliente</label>'
            reason = ('Este histórico anterior foi preservado para consulta.' if conversation['status'] == 'legacy' else 'Esta conversa está encerrada.' if conversation['status'] == 'closed' else 'Consulta disponível. Respostas e encerramento dependem de atribuição e permissão da equipe.')
            reply = '<div class="conversation-composer">' + form('/conversas/responder', reply_fields, 'Enviar resposta', 'multipart/form-data') + '</div>' if can_reply else '<p class="muted">' + reason + '</p>'
            if user['role'] == 'client' and conversation['status'] != 'open':
                new_url = '/cliente/mensagens' + ('?case_id=' + str(conversation['case_id']) if conversation['case_id'] else '?novo=1')
                reply += '<p><a class="text-link" href="' + new_url + '">Iniciar nova conversa →</a></p>'
            close = form('/conversas/encerrar', hidden, 'Encerrar conversa') if can_reply and user['role'] in ('staff', 'admin') else ''
            last_shown_id = messages[-1]['id'] if messages else 0
            mark = form('/conversas/ler', hidden + '<input type="hidden" name="last_message_id" value="' + str(last_shown_id) + '">', 'Marcar como lida')
            status = {'open': 'Em andamento', 'closed': 'Encerrada', 'legacy': 'Histórico anterior'}[conversation['status']]
            back = '/cliente/mensagens' if user['role'] == 'client' else '/admin/mensagens'
            context = (esc(conversation['client_name']) + ' · ') if user['role'] != 'client' else ''
            context += esc(conversation['case_title'] or 'Contato geral')
            if user['role'] != 'client' and conversation['case_id']:
                context += ' · Responsável: ' + esc(conversation['responsible_name'] or 'Não atribuído')
            if conversation['visibility'] == 'internal':
                context += ' · Relato interno'
            body = '<section class="wrap section"><a class="text-link" href="' + back + '">← Voltar às conversas</a><article class="conversation-view panel" id="conversation-view" data-conversation-id="' + str(conversation_id) + '" data-conversation-endpoint="/conversas/' + str(conversation_id) + '/mensagens"><p class="eyebrow">' + esc(status) + '</p><h1>' + esc(conversation['title']) + '</h1><p class="muted">' + context + '</p><div class="thread conversation-thread">' + (''.join(messages_html) or '<p class="muted">Nenhuma mensagem.</p>') + '</div>' + reply + close + '<div class="conversation-mark">' + mark + '</div></article></section>'
            return self.page('Conversa', body, user)
        if path == '/perfil':
            if not user:
                return self.forbidden()
            avatar_preview = '<img class="profile-avatar-preview" src="/perfil/imagem/' + str(user['id']) + '/avatar" alt="Foto de perfil">' if user['avatar'] else '<span class="profile-avatar-preview profile-avatar-fallback">' + esc(initials(user['name'])) + '</span>'
            cover_preview = '<img class="profile-cover-preview" src="/perfil/imagem/' + str(user['id']) + '/cover" alt="Capa do perfil">' if user['cover'] else '<div class="profile-cover-preview profile-cover-fallback"></div>'
            profile_form = form('/perfil', input_field('Nome', 'name', user['name']) + input_field('Telefone', 'phone', user['phone'], required=False) + '<label>Foto de perfil<input type="file" name="avatar" accept="image/png,image/jpeg,image/webp"></label><label>Capa<input type="file" name="cover" accept="image/png,image/jpeg,image/webp"></label><label class="check"><input type="checkbox" name="remove_avatar" value="1"> Restaurar foto padrão institucional</label><label class="check"><input type="checkbox" name="remove_cover" value="1"> Restaurar capa padrão institucional</label>', 'Salvar perfil', 'multipart/form-data')
            content = '<section class="client-home"><div class="profile-cover-wrap">' + cover_preview + '</div><div class="profile-heading">' + avatar_preview + '<div><p class="eyebrow">MEU PERFIL</p><h1>' + esc(user['name']) + '</h1><p class="muted">' + esc(role_label(user)) + ' · ' + esc(user['email']) + '</p></div></div>' + card('Dados e imagens', profile_form) + '<p><a class="text-link" href="/senha">Alterar senha</a></p></section>'
            return self.page('Meu perfil', content, user)
        if re.fullmatch(r'/perfil/imagem/\d+/(avatar|cover)', path):
            if not user:
                return self.forbidden()
            parts = path.strip('/').split('/')
            target_id = int(parts[2])
            kind = parts[3]
            if user['role'] == 'client' and target_id != user['id']:
                return self.forbidden()
            with db() as c:
                target = c.execute('SELECT avatar,cover FROM users WHERE id=? AND deleted_at=\'\'', (target_id,)).fetchone()
            if not target:
                return self.send('Não encontrado', 404)
            stored = target['avatar' if kind == 'avatar' else 'cover']
            if not stored:
                return self.send('Não encontrado', 404)
            file_path = UP / stored
            if not file_path.is_file():
                return self.send('Não encontrado', 404)
            return self.send_file(file_path, mimetypes.guess_type(stored)[0] or 'application/octet-stream', cache='private, max-age=3600')
        if path.startswith('/cliente/atendimento/'):
            if not user or user['role'] != 'client':
                return self.forbidden()
            try:
                case_id = int(path.rsplit('/', 1)[-1])
            except ValueError:
                return self.forbidden()
            with db() as c:
                case_row = c.execute("SELECT * FROM cases WHERE id=? AND client_id=? AND deleted_at=''", (case_id, user['id'])).fetchone()
                if not case_row:
                    return self.forbidden()
                events = c.execute('SELECT * FROM case_events WHERE case_id=? AND visible_to_client=1 ORDER BY id ASC', (case_id,)).fetchall()
                case_conversations = conversation_rows(c, user, case_id=case_id)
                case_docs = c.execute("SELECT * FROM documents WHERE case_id=? AND client_id=? AND deleted_at='' ORDER BY id DESC", (case_id, user['id'])).fetchall()
                case_updates = c.execute('SELECT * FROM updates WHERE case_id=? AND client_id=? ORDER BY id DESC', (case_id, user['id'])).fetchall()
                case_apps = c.execute("SELECT * FROM appointments WHERE case_id=? AND client_id=? AND privacy='client' AND deleted_at='' ORDER BY when_at", (case_id, user['id'])).fetchall()
                case_reqs = c.execute('SELECT * FROM requests WHERE case_id=? AND client_id=? ORDER BY id DESC', (case_id, user['id'])).fetchall()
            event_html = ''.join('<div class="request"><strong>' + esc(event['created']) + ' — ' + esc(event['description'] or event['event_type']) + '</strong>' + ('<p>Status: ' + esc(event['from_status']) + ' → ' + esc(event['to_status']) + '</p>' if event['from_status'] or event['to_status'] else '') + '</div>' for event in events) or '<p>Nenhum evento registrado.</p>'
            doc_html = ''.join('<li><a href="/arquivo/' + str(doc['id']) + '">' + esc(doc['filename']) + '</a> <small>(' + esc(doc['source']) + ')</small> ' + document_badge(doc['status']) + ((' · análise: ' + esc(doc['analysis_notes'])) if doc['analysis_notes'] else '') + '</li>' for doc in case_docs) or '<li>Nenhum documento.</li>'
            update_html = ''.join(card(update['title'], '<p class="muted">' + esc(update['created']) + '</p><p>' + esc(update['body']) + '</p>') for update in case_updates) or '<p>Nenhuma atualização.</p>'
            app_html = ''.join('<li><strong>' + esc(fmt_when(app['when_at'])) + '</strong> — ' + esc(app['title']) + ' — ' + esc(app['notes']) + '</li>' for app in case_apps) or '<li>Nenhum compromisso.</li>'
            req_html = ''.join(card(req['subject'], '<p>' + esc(req['body']) + '</p>' + status_badge(req['status']) + '<p>' + esc(req['response']) + '</p>') for req in case_reqs) or '<p>Nenhuma solicitação.</p>'
            detail = '<p><strong>Status:</strong> ' + status_badge(case_row['status']) + '</p><p><strong>Assunto informado:</strong> ' + esc(case_row['original_title'] or case_row['title']) + '</p><p><strong>Criado em:</strong> ' + esc(case_row['created']) + '</p><p>' + esc(case_row['description']) + '</p>'
            content = '<section class="wrap section"><p class="eyebrow">MEU ATENDIMENTO</p><h1>' + esc(case_row['title']) + '</h1>' + card('Resumo', detail) + card('Conversas', conversation_cards(case_conversations, user) + '<p><a class="text-link" href="/cliente/mensagens?case_id=' + str(case_id) + '">Iniciar novo assunto →</a></p>') + card('Documentos', '<ul>' + doc_html + '</ul>') + card('Atualizações', update_html) + card('Compromissos', '<ul>' + app_html + '</ul>') + card('Solicitações', req_html) + card('Histórico', event_html) + '<p><a class="text-link" href="/cliente/atendimentos">Voltar aos atendimentos</a></p></section>'
            return self.page('Meu atendimento', content, user)
        if path == '/cliente/atendimentos':
            if not user or user['role'] != 'client':
                return self.forbidden()
            with db() as c:
                cases = self.scoped_cases(c, user)
                stale_hours = max(1, int(setting(c, 'stale_hours', '48') or 48))
            content = '<section class="client-home"><div class="client-hero"><p class="eyebrow">MEUS ATENDIMENTOS</p><h1>Meus atendimentos</h1><p>Consulte todos os seus casos e acompanhe a situação de cada um.</p></div><div class="client-actions"><a class="btn" href="/cliente/novo">Novo atendimento</a><a class="btn dark" href="/cliente">Voltar ao início</a></div><div class="client-grid"><div>' + client_case_cards(cases, stale_hours) + '</div><div>' + card('Resumo', '<p>Em andamento: ' + str(sum(1 for case in cases if status_color(case['status']) == 'yellow')) + '</p><p>Aguardando você: ' + str(sum(1 for case in cases if status_color(case['status']) == 'blue')) + '</p><p>Concluídos: ' + str(sum(1 for case in cases if status_color(case['status']) == 'green')) + '</p>') + '</div></div></section>'
            return self.page('Meus atendimentos', content, user)
        if path == '/cliente/mensagens':
            if not user or user['role'] != 'client':
                return self.forbidden()
            with db() as c:
                cases = self.scoped_cases(c, user)
                conversations = conversation_rows(c, user)
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            selected_case = query.get('case_id', [''])[0]
            open_form = bool(query.get('novo') or any(str(case['id']) == selected_case for case in cases))
            message_form = form('/cliente/mensagem', field('Assunto', 'subject') + client_case_select(cases, selected_case) + '<label>Mensagem<textarea name="body" required></textarea></label>', 'Iniciar conversa')
            active = [row for row in conversations if row['status'] == 'open']
            archived = [row for row in conversations if row['status'] != 'open']
            selected_conversation = query.get('conversa', [''])[0]
            selected_id = int(selected_conversation) if selected_conversation.isdigit() else ((active or archived)[0]['id'] if (active or archived) else 0)
            pane_html = ''
            if selected_id:
                with db() as c:
                    pane_html = self.conversation_view_html(c, user, selected_id) or ''
            pane_html = pane_html or '<div class="conversation-empty"><p class="eyebrow">CONVERSAS</p><h2>Selecione um assunto</h2><p>Escolha uma conversa para consultar o histórico.</p></div>'
            inbox_html = conversation_cards(active, user, '/cliente/mensagens?conversa=', dialog=False)
            archived_html = conversation_cards(archived, user, '/cliente/mensagens?conversa=', dialog=False)
            content = '<section class="client-home"><div class="client-hero"><p class="eyebrow">MENSAGENS</p><h1>Conversas com o escritório</h1><p>Escolha um assunto para consultar ou responder.</p></div><details class="conversation-new"' + (' open' if open_form else '') + '><summary>Iniciar novo assunto</summary>' + message_form + '</details><div class="conversation-workspace"><aside class="conversation-inbox"><div class="conversation-inbox-head"><h2>Em andamento</h2></div><div class="conversation-list">' + inbox_html + '</div><details class="conversation-history"><summary>Encerradas e histórico (' + str(len(archived)) + ')</summary><div class="conversation-list">' + archived_html + '</div></details></aside><section class="conversation-pane">' + pane_html + '</section></div></section>'
            return self.page('Mensagens', content, user)
        if path == '/cliente/documentos':
            if not user or user['role'] != 'client':
                return self.forbidden()
            with db() as c:
                cases = self.scoped_cases(c, user)
                documents = c.execute("SELECT d.*, ca.title AS case_title FROM documents d LEFT JOIN cases ca ON ca.id=d.case_id WHERE d.client_id=? AND d.deleted_at='' AND (d.case_id IS NULL OR d.case_id IN (SELECT id FROM cases WHERE deleted_at='')) ORDER BY d.id DESC", (user['id'],)).fetchall()
                pendencies = c.execute("SELECT * FROM pendencies WHERE client_id=? AND visible_to_client=1 AND status='Aberta' AND (case_id IS NULL OR case_id IN (SELECT id FROM cases WHERE deleted_at='')) ORDER BY id DESC", (user['id'],)).fetchall()
                c.execute("UPDATE documents SET seen_by_client=1 WHERE client_id=? AND source='escritório' AND seen_by_client=0", (user['id'],))
            upload = form('/cliente/documento', client_case_select(cases) + client_pendency_select(pendencies) + field('Arquivo', 'file', 'file'), 'Enviar documento', 'multipart/form-data')
            doc_items = ''.join('<li><a href="/arquivo/' + str(document['id']) + '">' + esc(document['filename']) + '</a> <small>(' + esc(document['source']) + ')</small> · ' + esc(document['case_title'] or 'Caso geral') + ' ' + document_badge(document['status']) + (' <span class="status-badge status-red">Novo</span>' if document['source'] == 'escritório' and not document['seen_by_client'] else '') + ((' · análise: ' + esc(document['analysis_notes'])) if document['analysis_notes'] else '') + '</li>' for document in documents) or '<li>Nenhum documento.</li>'
            pendency_items = ''.join('<div class="request status-border-' + pendency_color(pendency['status']) + '"><strong>' + esc(pendency['title']) + '</strong><p>' + esc(pendency['description']) + '</p><p>' + pendency_badge(pendency['status']) + '</p><p><a class="text-link" href="/cliente/pendencias">Enviar documento desta pendência →</a></p></div>' for pendency in pendencies) or '<p class="muted">Nenhuma pendência aberta.</p>'
            content = '<section class="client-home"><div class="client-hero"><p class="eyebrow">DOCUMENTOS</p><h1>Documentos</h1><p>Envie arquivos e consulte os documentos disponibilizados pelo escritório.</p></div><div class="client-grid"><div>' + card('Meus documentos', '<ul>' + doc_items + '</ul><p><a class="text-link" href="/cliente/pendencias">Ver pendências e documentos solicitados →</a></p>') + '</div><div>' + card('Enviar documento', '<p class="muted">Permitidos: PDF, PNG, JPG e TXT, até 10 MB.</p>' + upload) + card('Documentos solicitados', pendency_items) + '</div></div><p><a class="text-link" href="/cliente">Voltar ao início</a></p></section>'
            return self.page('Documentos', content, user)
        if path == '/cliente/compromissos':
            if not user or user['role'] != 'client':
                return self.forbidden()
            with db() as c:
                appointments = c.execute("SELECT a.*, ca.title AS case_title FROM appointments a LEFT JOIN cases ca ON ca.id=a.case_id WHERE a.client_id=? AND a.privacy='client' AND a.deleted_at='' AND (a.case_id IS NULL OR a.case_id IN (SELECT id FROM cases WHERE deleted_at='')) ORDER BY a.when_at", (user['id'],)).fetchall()
            items = ''.join('<li><strong>' + esc(fmt_when(appointment['when_at'])) + '</strong> — ' + esc(appointment['title']) + ((' · ' + esc(appointment['case_title'])) if appointment['case_title'] else '') + ' ' + appointment_badge(appointment['status']) + '<br><small>' + esc(appointment['notes']) + '</small></li>' for appointment in appointments) or '<li>Nenhum compromisso informado.</li>'
            content = '<section class="client-home"><div class="client-hero"><p class="eyebrow">COMPROMISSOS</p><h1>Compromissos</h1><p>Datas, horários e orientações compartilhadas pelo escritório.</p></div>' + card('Agenda', '<ul>' + items + '</ul>') + '<p><a class="text-link" href="/cliente">Voltar ao início</a></p></section>'
            return self.page('Compromissos', content, user)
        if path == '/cliente/atualizacoes':
            if not user or user['role'] != 'client':
                return self.forbidden()
            with db() as c:
                updates = c.execute("SELECT up.*, ca.title AS case_title FROM updates up LEFT JOIN cases ca ON ca.id=up.case_id WHERE up.client_id=? AND (up.case_id IS NULL OR up.case_id IN (SELECT id FROM cases WHERE deleted_at='')) ORDER BY up.id DESC", (user['id'],)).fetchall()
                c.execute('UPDATE updates SET seen_by_client=1 WHERE client_id=? AND seen_by_client=0', (user['id'],))
            items = ''.join(card(update['title'], '<p class="muted">' + esc(update['case_title'] or 'Caso geral') + ' · ' + esc(update['created']) + '</p><p>' + esc(update['body']) + '</p>') for update in updates) or '<p>Nenhuma atualização publicada.</p>'
            content = '<section class="client-home"><div class="client-hero"><p class="eyebrow">ATUALIZAÇÕES</p><h1>Atualizações</h1><p>Informações e movimentações compartilhadas pelo escritório.</p></div>' + items + '<p><a class="text-link" href="/cliente">Voltar ao início</a></p></section>'
            return self.page('Atualizações', content, user)
        if path == '/cliente/novo':
            if not user or user['role'] != 'client':
                return self.forbidden()
            new_form = form('/cliente/novo', field('Assunto', 'subject') + '<label>Descreva sua necessidade<textarea name="description" required></textarea></label>', 'Abrir atendimento')
            content = '<section class="client-home"><div class="client-hero"><p class="eyebrow">NOVO ATENDIMENTO</p><h1>Como podemos ajudar?</h1><p>Informe o assunto e descreva sua necessidade. A equipe fará a análise inicial e atribuirá o atendimento a um advogado.</p></div>' + card('Abrir atendimento', new_form) + '<p><a class="text-link" href="/cliente">Voltar ao início</a></p></section>'
            return self.page('Novo atendimento', content, user)
        if path == '/cliente/exportar':
            if not user or user['role'] != 'client':
                return self.forbidden()
            with db() as c:
                payload = client_export(c, user['id'])
            if not payload:
                return self.forbidden()
            data = json.dumps(payload, ensure_ascii=False, indent=2)
            return self.send(data, ctype='application/json; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="dados-titular-' + str(user['id']) + '.json"'})
        if path == '/cliente/perfil':
            if not user or user['role'] != 'client':
                return self.forbidden()
            profile_form = form('/cliente/perfil', input_field('Nome', 'name', user['name']) + input_field('Telefone', 'phone', user['phone'], required=False) + '<p class="muted">E-mail de acesso: ' + esc(user['email']) + '. Para alterar o e-mail, envie uma solicitação à equipe.</p>', 'Salvar perfil')
            content = '<section class="client-home"><div class="client-hero"><p class="eyebrow">MEU PERFIL</p><h1>Meus dados</h1><p>Mantenha seus dados de contato atualizados.</p></div>' + card('Dados cadastrais', profile_form + '<p><a class="btn ghost" href="/cliente/exportar">Baixar meus dados (JSON)</a></p>') + '<p><a class="text-link" href="/cliente">Voltar ao início</a></p></section>'
            return self.page('Meu perfil', content, user)
        if path == '/cliente/pendencias':
            if not user or user['role'] != 'client':
                return self.forbidden()
            with db() as c:
                pendencies = c.execute("SELECT p.*, ca.title AS case_title, d.filename AS document_name FROM pendencies p LEFT JOIN cases ca ON ca.id=p.case_id LEFT JOIN documents d ON d.id=p.document_id WHERE p.client_id=? AND p.visible_to_client=1 AND (p.case_id IS NULL OR p.case_id IN (SELECT id FROM cases WHERE deleted_at='')) ORDER BY p.id DESC", (user['id'],)).fetchall()
            items = []
            for pendency in pendencies:
                upload = form('/cliente/documento', '<input type="hidden" name="pendency_id" value="' + str(pendency['id']) + '">' + field('Arquivo', 'file', 'file'), 'Enviar documento da pendência', 'multipart/form-data') if pendency['status'] == 'Aberta' else ''
                items.append('<div class="request status-border-' + pendency_color(pendency['status']) + '"><strong>' + esc(pendency['title']) + '</strong><p>' + esc(pendency['description']) + '</p><p>' + pendency_badge(pendency['status']) + ((' · caso: ' + esc(pendency['case_title'])) if pendency['case_title'] else '') + ((' · documento: ' + esc(pendency['document_name'])) if pendency['document_name'] else '') + ((' · prazo: ' + esc(pendency['due_at'])) if pendency['due_at'] else '') + ((' · análise: ' + esc(pendency['review_notes'])) if pendency['review_notes'] else '') + '</p>' + upload + '</div>')
            content = '<section class="client-home"><div class="client-hero"><p class="eyebrow">PENDÊNCIAS</p><h1>Pendências do cliente</h1><p>Documentos ou informações que o escritório aguarda de você.</p></div>' + (''.join(items) or '<p>Nenhuma pendência no momento.</p>') + '<p><a class="text-link" href="/cliente">Voltar ao início</a></p></section>'
            return self.page('Pendências do cliente', content, user)
        if path == '/cliente':
            if not user or user['role'] != 'client':
                return self.forbidden()
            with db() as c:
                cases = self.scoped_cases(c, user)
                conversations = conversation_rows(c, user)
                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
                apps = c.execute("SELECT * FROM appointments WHERE client_id=? AND privacy='client' AND status='pendente' AND deleted_at='' AND replace(when_at,'T',' ')>=? AND (case_id IS NULL OR case_id IN (SELECT id FROM cases WHERE deleted_at='')) ORDER BY replace(when_at,'T',' ') LIMIT 3", (user['id'], now)).fetchall()
                pendencies = c.execute("SELECT p.*, ca.title AS case_title FROM pendencies p LEFT JOIN cases ca ON ca.id=p.case_id WHERE p.client_id=? AND p.visible_to_client=1 AND p.status='Aberta' AND (p.case_id IS NULL OR p.case_id IN (SELECT id FROM cases WHERE deleted_at='')) ORDER BY p.id DESC", (user['id'],)).fetchall()
                unread_messages = sum(row['unread'] for row in conversations)
                stale_hours = max(1, int(setting(c, 'stale_hours', '48') or 48))
            counts = {'yellow': 0, 'blue': 0, 'green': 0}
            for case in cases:
                color = status_color(case['status'])
                if color in counts:
                    counts[color] += 1
            hero = '<section class="client-hero"><div><p class="eyebrow">MEU ESPAÇO</p><h1>Olá, ' + esc(user['name']) + '!</h1><p>Acompanhe seus atendimentos, envie documentos e converse com a equipe do escritório.</p></div><img src="/static/img/office_meeting.webp" alt=""></section>'
            kpis = [('Em andamento', counts['yellow'], 'yellow', '/cliente/atendimentos'), ('Aguardando você', counts['blue'], 'blue', '/cliente/pendencias'), ('Concluídos', counts['green'], 'green', '/cliente/atendimentos'), ('Mensagens não lidas', unread_messages, 'red', '/cliente/mensagens')]
            kpi_html = ''.join('<a class="client-kpi kpi-' + color + '" href="' + href + '"><strong' + (' data-unread-client' if label == 'Mensagens não lidas' else '') + '>' + str(value) + '</strong><span>' + label + '</span><small>Abrir →</small></a>' for label, value, color, href in kpis)
            alert = ''
            if unread_messages:
                alert = '<div class="client-alert client-alert-urgent"><span><strong>Você tem ' + str(unread_messages) + ' nova(s) mensagem(ns) do escritório!</strong><small>Mensagens não lidas: <span data-unread-count>' + str(unread_messages) + '</span></small></span><a class="btn" href="/cliente/mensagens">Ver mensagens →</a></div>'
            pending_notice = '<div class="client-alert"><strong>Precisa da sua atenção:</strong> ' + ' · '.join('<a class="text-link" href="/cliente/pendencias">' + esc(item['title']) + '</a>' for item in pendencies[:3]) + '</div>' if pendencies else ''
            active = [row for row in conversations if row['status'] == 'open']
            message_card = panel_card('Conversas recentes', conversation_cards(active[:3], user) + '<p><a class="text-link" href="/cliente/mensagens">Ver conversas e histórico →</a></p>')
            cases_card = panel_card('Meus atendimentos', client_case_cards(cases[:3], stale_hours) + '<p><a class="text-link" href="/cliente/atendimentos">Ver todos os atendimentos →</a></p>', '<a class="text-link" href="/cliente/novo">Novo atendimento →</a>')
            app_items = ''.join('<div class="panel-appointment"><span class="panel-date">' + esc(fmt_when(appointment['when_at'])) + '</span><span><strong>' + esc(appointment['title']) + '</strong><small>Compromisso do escritório</small></span></div>' for appointment in apps) or '<p class="muted">Nenhum compromisso próximo.</p>'
            quick = [('/cliente/mensagens', 'Mensagens', 'messages'), ('/cliente/documentos', 'Documentos', 'documents'), ('/cliente/compromissos', 'Agenda', 'calendar'), ('/cliente/novo', 'Novo atendimento', 'add')]
            quick_html = ''.join('<a class="panel-quick" href="' + href + '">' + panel_icon(icon) + '<strong>' + label + '</strong><small>Enviar ou consultar</small></a>' for href, label, icon in quick)
            body = '<section class="client-home"><div class="client-home-head">' + hero + '</div>' + alert + pending_notice + scam_notice() + '<div class="client-kpis">' + kpi_html + '</div><div class="client-grid"><div>' + cases_card + '</div><div>' + panel_card('Próximos compromissos', '<div class="panel-agenda-list">' + app_items + '</div>', '<a class="text-link" href="/cliente/compromissos">Ver todos →</a>') + message_card + '</div></div><div class="panel-card panel-client-quick"><div class="panel-card-head"><h2>Acesso rápido</h2></div><div class="panel-quick-grid">' + quick_html + '</div></div></section>'
            return self.page('Meu Espaço', body, user)
        if re.fullmatch(r'/anexo/\d+', path):
            if not user:
                return self.forbidden()
            attachment_id = int(path.rsplit('/', 1)[-1])
            with db() as c:
                attachment = c.execute("SELECT ma.*,m.conversation_id FROM message_attachments ma JOIN messages m ON m.id=ma.message_id WHERE ma.id=?", (attachment_id,)).fetchone()
                if not attachment or not self.conversation_access(c, user, attachment['conversation_id']):
                    return self.forbidden()
            target = UP / attachment['stored']
            if not target.is_file():
                return self.send('Não encontrado', 404)
            return self.send_file(target, attachment['mime'], download=attachment['filename'])
        if re.fullmatch(r'/interno/\d+', path):
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            document_id = int(path.rsplit('/', 1)[-1])
            with db() as c:
                document = c.execute("SELECT * FROM internal_documents WHERE id=? AND deleted_at=''", (document_id,)).fetchone()
                if not document or not self.can_view_internal_document(c, user, document):
                    return self.forbidden()
                self.audit_action(c, user['id'], 'baixar documento interno', document['title'], entity='internal_document', entity_id=document_id, client_id=document['client_id'], case_id=document['case_id'])
            target = UP / document['stored']
            if not target.is_file():
                return self.send('Não encontrado', 404)
            return self.send_file(target, document['mime'], download=document['filename'])
        if path.startswith('/arquivo/'):
            if not user:
                return self.forbidden()
            try:
                docid = int(path.rsplit('/', 1)[-1])
            except ValueError:
                return self.forbidden()
            with db() as c:
                document = c.execute('SELECT * FROM documents WHERE id=?', (docid,)).fetchone()
                if not document:
                    allowed = False
                elif document['deleted_at'] and not is_super(user):
                    allowed = False
                elif user['role'] != 'client' and document['case_id']:
                    allowed = self.can_view_case(c, user, document['case_id'])
                else:
                    allowed = self.can_manage(c, user, document['client_id'])
            if not document or not allowed:
                return self.forbidden()
            target = UP / document['stored']
            if not target.is_file():
                return self.send('Arquivo indisponível', 404)
            return self.send_file(target, 'application/octet-stream', download=document['filename'], cache='no-store')
        if path == '/admin/lixeira':
            if not user or not is_super(user):
                return self.forbidden()
            with db() as c:
                deleted_clients = c.execute("SELECT id,name,email,deleted_at FROM users WHERE role='client' AND deleted_at<>'' ORDER BY deleted_at DESC").fetchall()
                deleted_cases = c.execute("SELECT ca.id,ca.title,ca.status,ca.deleted_at,u.name AS client FROM cases ca JOIN users u ON u.id=ca.client_id WHERE ca.deleted_at<>'' ORDER BY ca.deleted_at DESC").fetchall()
                deleted_docs = c.execute("SELECT d.id,d.filename,d.source,d.deleted_at,u.name AS client,ca.title AS case_title FROM documents d JOIN users u ON u.id=d.client_id LEFT JOIN cases ca ON ca.id=d.case_id WHERE d.deleted_at<>'' ORDER BY d.deleted_at DESC").fetchall()
            def trash_actions(entity, record_id):
                restore = form('/admin/restore', '<input type="hidden" name="entity" value="' + entity + '"><input type="hidden" name="record_id" value="' + str(record_id) + '">', 'Restaurar')
                purge = form('/admin/purge', '<input type="hidden" name="entity" value="' + entity + '"><input type="hidden" name="record_id" value="' + str(record_id) + '">' + input_field('Digite EXCLUIR para confirmar', 'confirm'), 'Excluir definitivamente')
                return restore + purge
            client_rows = ''.join('<tr><td>' + esc(x['name']) + '<br><small>' + esc(x['email']) + '</small></td><td>' + esc(x['deleted_at']) + '</td><td>' + trash_actions('client', x['id']) + '</td></tr>' for x in deleted_clients) or '<tr><td colspan="3">Nenhum cliente na lixeira.</td></tr>'
            case_rows = ''.join('<tr><td>#' + str(x['id']) + ' — ' + esc(x['title']) + '</td><td>' + esc(x['client']) + ' · ' + status_badge(x['status']) + '</td><td>' + esc(x['deleted_at']) + '</td><td>' + trash_actions('case', x['id']) + '</td></tr>' for x in deleted_cases) or '<tr><td colspan="4">Nenhum caso na lixeira.</td></tr>'
            doc_rows = ''.join('<tr><td>' + esc(x['filename']) + '<br><small>' + esc(x['client']) + ' · ' + esc(x['case_title'] or 'Caso geral') + '</small></td><td>' + esc(x['source']) + '</td><td>' + esc(x['deleted_at']) + '</td><td>' + trash_actions('document', x['id']) + '</td></tr>' for x in deleted_docs) or '<tr><td colspan="4">Nenhum documento na lixeira.</td></tr>'
            content = '<section class="wrap section">' + self.admin_nav(user) + '<h1>Lixeira</h1><p class="muted">Registros excluídos podem ser restaurados. A exclusão definitiva remove também os arquivos e registros vinculados e não pode ser desfeita.</p><h2>Clientes</h2><div class="table-wrap"><table class="table"><thead><tr><th>Cliente</th><th>Excluído em</th><th>Ações</th></tr></thead><tbody>' + client_rows + '</tbody></table></div><h2>Casos</h2><div class="table-wrap"><table class="table"><thead><tr><th>Caso</th><th>Cliente / status</th><th>Excluído em</th><th>Ações</th></tr></thead><tbody>' + case_rows + '</tbody></table></div><h2>Documentos</h2><div class="table-wrap"><table class="table"><thead><tr><th>Arquivo</th><th>Origem</th><th>Excluído em</th><th>Ações</th></tr></thead><tbody>' + doc_rows + '</tbody></table></div><p><a class="text-link" href="/admin">Voltar ao painel</a></p></section>'
            return self.page('Lixeira', content, user)
        if path == '/admin/auditoria':
            if not user or not is_super(user):
                return self.forbidden()
            page = self.page_number()
            per = 25
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            export = query.get('export', [''])[0]
            filters = {key: query.get(key, [''])[0].strip() for key in ('actor', 'entity', 'action', 'from', 'to')}
            conditions = []
            params = []
            if filters['actor'].isdigit():
                conditions.append('a.user_id=?')
                params.append(int(filters['actor']))
            if filters['entity']:
                conditions.append('a.entity=?')
                params.append(filters['entity'])
            if filters['action']:
                conditions.append('a.action LIKE ?')
                params.append('%' + filters['action'] + '%')
            if len(filters['from']) == 10 and filters['from'][4] == '-':
                conditions.append('substr(a.created,1,10)>=?')
                params.append(filters['from'])
            if len(filters['to']) == 10 and filters['to'][4] == '-':
                conditions.append('substr(a.created,1,10)<=?')
                params.append(filters['to'])
            where = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''
            with db() as c:
                total = c.execute('SELECT COUNT(*) FROM audit a LEFT JOIN users u ON u.id=a.user_id' + where, tuple(params)).fetchone()[0]
                if export == 'csv':
                    rows = c.execute('SELECT a.*, u.name AS actor FROM audit a LEFT JOIN users u ON u.id=a.user_id' + where + ' ORDER BY a.id DESC LIMIT 10000', tuple(params)).fetchall()
                else:
                    rows = c.execute('SELECT a.*, u.name AS actor FROM audit a LEFT JOIN users u ON u.id=a.user_id' + where + ' ORDER BY a.id DESC LIMIT ? OFFSET ?', tuple(params) + (per, (page - 1) * per)).fetchall()
                actor_rows = c.execute('SELECT id,name,email FROM users ORDER BY name').fetchall()
                entity_rows = c.execute("SELECT DISTINCT entity FROM audit WHERE entity<>'' ORDER BY entity").fetchall()
            if export == 'csv':
                buffer = io.StringIO()
                writer = csv.writer(buffer)
                writer.writerow(['Data', 'Ator', 'Acao', 'Entidade', 'Entidade ID', 'Cliente ID', 'Caso ID', 'Detalhe', 'Antes', 'Depois', 'IP'])
                for row in rows:
                    writer.writerow([row['created'], row['actor'] or 'Sistema', row['action'], row['entity'] or '', row['entity_id'] or '', row['client_id'] or '', row['case_id'] or '', row['detail'], row['before'] or '', row['after'] or '', row['ip'] or ''])
                return self.send(buffer.getvalue(), ctype='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="auditoria.csv"'})
            pages = max(1, (total + per - 1) // per)
            items = ''.join('<tr><td>' + esc(x['created']) + '</td><td>' + esc(x['actor'] or 'Sistema') + '</td><td>' + esc(x['action']) + '</td><td>' + esc(x['entity'] or '') + (' #' + str(x['entity_id']) if x['entity_id'] else '') + '</td><td>' + esc(x['client_id'] or '') + ' / ' + esc(x['case_id'] or '') + '</td><td>' + esc(x['detail']) + '</td><td>' + esc((x['before'] or '')[:300]) + '</td><td>' + esc((x['after'] or '')[:300]) + '</td><td>' + esc(x['ip']) + '</td></tr>' for x in rows) or '<tr><td colspan="9">Nenhum registro.</td></tr>'
            actor_options = '<option value="">Todos os atores</option>' + ''.join('<option value="' + str(x['id']) + '"' + (' selected' if filters['actor'] == str(x['id']) else '') + '>' + esc(x['name']) + ' (' + esc(x['email']) + ')</option>' for x in actor_rows)
            entity_options = '<option value="">Todas as entidades</option>' + ''.join('<option value="' + esc(x['entity']) + '"' + (' selected' if filters['entity'] == x['entity'] else '') + '>' + esc(x['entity']) + '</option>' for x in entity_rows)
            filter_form = '<form method="get" action="/admin/auditoria"><label>Ator<select name="actor">' + actor_options + '</select></label><label>Entidade<select name="entity">' + entity_options + '</select></label><label>Ação<input name="action" value="' + esc(filters['action']) + '"></label><label>De<input type="date" name="from" value="' + esc(filters['from']) + '"></label><label>Até<input type="date" name="to" value="' + esc(filters['to']) + '"></label><button class="btn" type="submit">Filtrar</button></form>'
            export_query = urllib.parse.urlencode({key: value for key, value in filters.items() if value} | {'export': 'csv'})
            filter_base = '/admin/auditoria?' + urllib.parse.urlencode({key: value for key, value in filters.items() if value})
            body = f'<section class="wrap section">{self.admin_nav(user)}<h1>Auditoria</h1><p>{total} registro(s). <a class="text-link" href="/admin/auditoria?{esc(export_query)}">Exportar CSV</a></p>{card("Filtros", filter_form)}<div class="table-wrap"><table class="table"><thead><tr><th>Data</th><th>Ator</th><th>Ação</th><th>Entidade</th><th>Cliente / Caso</th><th>Detalhe</th><th>Antes</th><th>Depois</th><th>IP</th></tr></thead><tbody>{items}</tbody></table></div>{self.pager(filter_base, page, pages)}<p><a class="text-link" href="/admin">Voltar ao painel</a></p></section>'
            return self.page('Auditoria', body, user)
        if path == '/admin/contatos':
            if not user or not is_super(user):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            state = query.get('status', ['ativos'])[0]
            term = query.get('q', [''])[0].strip()[:150]
            with db() as c:
                rows = c.execute('SELECT ct.*,u.name AS responsible_name,gs.id AS guest_id FROM contacts ct LEFT JOIN users u ON u.id=ct.responsible_id LEFT JOIN guest_sessions gs ON gs.contact_id=ct.id ORDER BY ct.id DESC').fetchall()
                staff = c.execute("SELECT id,name FROM users WHERE role='admin' AND is_super=1 AND active=1 AND deleted_at='' ORDER BY name").fetchall()
            statuses = {'novo': 'Novo', 'em_atendimento': 'Em atendimento', 'respondido': 'Respondido', 'nao_classificado': 'Não classificado'}
            if state == 'ativos':
                rows = [row for row in rows if row['status'] != 'respondido']
            elif state in statuses:
                rows = [row for row in rows if row['status'] == state]
            if term:
                needle = term.casefold()
                rows = [row for row in rows if needle in (row['name'] + ' ' + row['email'] + ' ' + row['message']).casefold()]
            rows, pagination, total = self.paginate_rows(rows)
            items = []
            for row in rows:
                status_options = ''.join('<option value="' + key + '"' + (' selected' if row['status'] == key else '') + '>' + label + '</option>' for key, label in statuses.items())
                staff_options = '<option value="">Sem responsável</option>' + ''.join('<option value="' + str(person['id']) + '"' + (' selected' if person['id'] == row['responsible_id'] else '') + '>' + esc(person['name']) + '</option>' for person in staff)
                fields = '<input type="hidden" name="contact_id" value="' + str(row['id']) + '"><label>Situação<select name="status">' + status_options + '</select></label><label>Responsável<select name="responsible_id">' + staff_options + '</select></label>'
                email_url = 'mailto:' + urllib.parse.quote(row['email'], safe='@.+-_') + '?subject=' + urllib.parse.quote('Retorno - Bomfim & Lacerda')
                chat_link = ('<a class="btn" href="/admin/atendimento-visitante?guest_id=' + str(row['guest_id']) + '">Abrir conversa e responder</a> ' if row['guest_id'] else '')
                items.append('<article class="case-box contact-queue"><h3>' + esc(row['name']) + ' <span class="contact-state">' + esc(statuses.get(row['status'], 'Não classificado')) + '</span></h3><p class="case-meta">' + esc(row['email']) + ' · ' + esc(row['created']) + ' · Responsável: ' + esc(row['responsible_name'] or 'Não atribuído') + '</p><p>' + esc(row['message']) + '</p><div class="quick-actions">' + chat_link + '<a class="text-link" href="' + esc(email_url) + '">Abrir resposta por e-mail →</a></div><details class="admin-secondary"><summary>Atualizar acompanhamento</summary>' + form('/admin/contato/status', fields, 'Salvar acompanhamento') + '</details></article>')
            status_options = ''.join('<option value="' + key + '"' + (' selected' if state == key else '') + '>' + label + '</option>' for key, label in [('ativos', 'Em aberto'), ('todos', 'Todos')] + list(statuses.items()))
            filters = '<form method="get" action="/admin/contatos" class="admin-filters"><label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Nome, e-mail ou mensagem"></label><label>Situação<select name="status">' + status_options + '</select></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/contatos">Limpar</a></form>'
            body = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Mensagens de contato</h1><p class="muted">A fila e seus responsáveis são restritos aos super administradores. Abra a conversa para responder pelo próprio sistema; o e-mail continua disponível como alternativa.</p>' + filters + '<p class="muted">' + str(total) + ' contato(s) encontrado(s).</p>' + (''.join(items) or '<p>Nenhuma mensagem encontrada.</p>') + pagination + '</section>'
            return self.page('Mensagens de contato', body, user, description='Mensagens recebidas pelo formulário público.')
        if path == '/admin/chat-equipe':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            with db() as c:
                members = c.execute("SELECT id,name FROM users WHERE role IN ('admin','staff') AND active=1 AND deleted_at='' ORDER BY name").fetchall()
                thread = team_chat_html(c, user)
                team_chat_read(c, user)
            mention_buttons = ''.join('<button type="button" class="mention-chip" data-mention="' + esc(row['name']) + '">@' + esc(row['name'].split()[0]) + '</button>' for row in members if row['id'] != user['id'])
            composer = form('/admin/chat-equipe', '<div class="mention-chips">' + mention_buttons + '</div><label>Mensagem<textarea name="body" rows="3" placeholder="Digite uma mensagem para a equipe..."></textarea></label><label>Anexo (opcional)<input type="file" name="file"></label>', 'Enviar', 'multipart/form-data')
            content = '<section class="wrap section admin-workspace team-chat-page"><p class="eyebrow">COMUNICAÇÃO INTERNA</p><h1>Chat da equipe</h1><p class="muted">Canal geral da equipe, sem vínculo com cliente ou caso. Use @nome para mencionar alguém.</p><div class="team-chat-layout"><aside class="team-chat-members"><h2>Equipe</h2>' + ''.join('<div class="team-chat-member"><span class="panel-avatar">' + esc(initials(row['name'])) + '</span><span>' + esc(row['name']) + '</span></div>' for row in members) + '</aside><section class="team-chat-main panel"><div class="chat-thread team-chat-thread" id="team-chat-thread" data-team-chat-endpoint="/admin/chat-equipe/mensagens">' + thread + '</div><div class="team-chat-composer">' + composer + '</div></section></div></section>'
            return self.page('Chat da equipe', content, user)
        if path == '/admin/chat-equipe/mensagens':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.send_json({'error': 'unauthorized'}, 403)
            with db() as c:
                thread = team_chat_html(c, user)
                unread = team_chat_unread(c, user)
                team_chat_read(c, user)
            return self.send_json({'ok': True, 'html': thread, 'unread': unread})
        if re.fullmatch(r'/admin/chat-equipe/anexo/\d+', path):
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            message_id = int(path.rsplit('/', 1)[-1])
            with db() as c:
                message = c.execute('SELECT * FROM team_chat_messages WHERE id=?', (message_id,)).fetchone()
            if not message or not message['attachment_stored']:
                return self.send('Não encontrado', 404)
            target = UP / message['attachment_stored']
            if not target.is_file():
                return self.send('Não encontrado', 404)
            return self.send_file(target, message['attachment_mime'], download=message['attachment_filename'])
        if path == '/admin/chats/alertas':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.send_json({'error': 'unauthorized'}, 403)
            with db() as c:
                count = c.execute("SELECT COUNT(*) FROM guest_messages gm JOIN guest_sessions gs ON gs.id=gm.guest_id WHERE gm.sender_role='guest' AND gm.read_by_staff=0 AND gs.status='open'").fetchone()[0]
                latest = c.execute("SELECT gm.id,gm.guest_id,gm.body,gm.created,gs.name,gs.email FROM guest_messages gm JOIN guest_sessions gs ON gs.id=gm.guest_id WHERE gm.sender_role='guest' AND gm.read_by_staff=0 AND gs.status='open' ORDER BY gm.id DESC LIMIT 1").fetchone()
            return self.send_json({'ok': True, 'count': count, 'latest': ({'id': latest['id'], 'guest_id': latest['guest_id'], 'name': latest['name'], 'email': latest['email'], 'body': latest['body'][:160], 'created': latest['created']} if latest else None)})
        if path == '/admin/chats':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            state = query.get('status', ['abertos'])[0]
            term = query.get('q', [''])[0].strip()[:150]
            with db() as c:
                sessions = c.execute("SELECT gs.*,u.name AS client_name,ct.name AS contact_name,(SELECT COUNT(*) FROM guest_messages gm WHERE gm.guest_id=gs.id AND gm.sender_role='guest' AND gm.read_by_staff=0) AS unread,(SELECT body FROM guest_messages gm WHERE gm.guest_id=gs.id ORDER BY gm.id DESC LIMIT 1) AS last_body,(SELECT MAX(created) FROM guest_messages gm WHERE gm.guest_id=gs.id) AS last_message FROM guest_sessions gs LEFT JOIN users u ON u.id=gs.user_id LEFT JOIN contacts ct ON ct.id=gs.contact_id ORDER BY gs.updated DESC,gs.id DESC").fetchall()
            if state == 'abertos':
                sessions = [row for row in sessions if row['status'] == 'open']
            elif state == 'encerrados':
                sessions = [row for row in sessions if row['status'] == 'closed']
            if term:
                needle = term.casefold()
                sessions = [row for row in sessions if needle in ' '.join(str(row[key] or '') for key in ('name', 'email', 'client_name', 'contact_name', 'last_body')).casefold()]
            sessions, pagination, total = self.paginate_rows(sessions)
            items = []
            for session in sessions:
                kind = 'Cliente logado' if session['user_id'] else 'Visitante'
                unread = ' <span class="conversation-unread">' + str(session['unread']) + ' nova(s)</span>' if session['unread'] else ''
                items.append('<a class="conversation-card" href="/admin/atendimento-visitante?guest_id=' + str(session['id']) + '"><span class="conversation-card-top"><strong>' + esc(session['name']) + '</strong><span class="conversation-status">' + ('Em atendimento' if session['status'] == 'open' else 'Encerrado') + '</span></span><span class="conversation-context">' + esc(kind) + ' · ' + esc(session['email']) + ((' · ' + esc(session['contact_name'])) if session['contact_name'] else '') + '</span><span class="conversation-preview">' + esc((session['last_body'] or 'Sem mensagens ainda.')[:160]) + '</span><span class="conversation-meta">' + esc(session['last_message'] or session['created']) + unread + '</span></a>')
            options = ''.join('<option value="' + value + '"' + (' selected' if state == value else '') + '>' + label + '</option>' for value, label in (('abertos', 'Em aberto'), ('encerrados', 'Encerrados'), ('todos', 'Todos')))
            filters = '<form method="get" action="/admin/chats" class="admin-filters"><label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Nome, e-mail ou mensagem"></label><label>Situação<select name="status">' + options + '</select></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/chats">Limpar</a></form>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<p class="eyebrow">CHAT AO VIVO</p><h1>Atendimentos do chat</h1><p class="muted">Conversas de clientes logados e visitantes. A atualização da página de atendimento é automática.</p>' + filters + '<p class="muted">' + str(total) + ' atendimento(s) encontrado(s).</p><div class="conversation-list" data-admin-chat-list>' + (''.join(items) or '<p class="muted">Nenhum atendimento encontrado.</p>') + '</div>' + pagination + '</section>'
            return self.page('Chat ao vivo', content, user)
        if path == '/admin/atendimento-visitante' or path == '/admin/atendimento-visitante/mensagens':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                guest_id = int(query.get('guest_id', ['0'])[0])
            except (TypeError, ValueError):
                guest_id = 0
            with db() as c:
                session = c.execute("SELECT gs.*,ct.status AS contact_status,ct.responsible_id,ct.message AS initial_message,ct.id AS contact_id_value,ru.name AS responsible_name,cu.name AS logged_client FROM guest_sessions gs LEFT JOIN contacts ct ON ct.id=gs.contact_id LEFT JOIN users ru ON ru.id=ct.responsible_id LEFT JOIN users cu ON cu.id=gs.user_id WHERE gs.id=?", (guest_id,)).fetchone()
                if not session:
                    return self.forbidden()
                messages = c.execute('SELECT * FROM guest_messages WHERE guest_id=? ORDER BY id', (guest_id,)).fetchall()
                c.execute("UPDATE guest_messages SET read_by_staff=1 WHERE guest_id=? AND sender_role='guest'", (guest_id,))
            if path.endswith('/mensagens'):
                return self.send_json({'ok': True, 'status': session['status'], 'html': guest_thread_html(session, messages, staff_view=True), 'updated': messages[-1]['created'] if messages else session['created']})
            status_label = 'Em atendimento' if session['status'] == 'open' else 'Atendimento encerrado'
            reply_form = form('/admin/atendimento-visitante/responder', '<input type="hidden" name="guest_id" value="' + str(guest_id) + '"><label>Resposta<textarea name="body" rows="4" required></textarea></label>', 'Enviar resposta') if session['status'] == 'open' else '<p class="muted">Este atendimento está encerrado.</p>'
            close_form = form('/admin/atendimento-visitante/encerrar', '<input type="hidden" name="guest_id" value="' + str(guest_id) + '">', 'Encerrar atendimento') if session['status'] == 'open' else ''
            details = '<p><strong>Nome:</strong> ' + esc(session['name']) + (' · cliente logado' if session['user_id'] else ' · visitante') + '</p><p><strong>E-mail:</strong> ' + esc(session['email']) + (' · <strong>Telefone:</strong> ' + esc(session['phone']) if session['phone'] else '') + '</p><p><strong>Status:</strong> ' + esc(status_label) + ((' · Responsável: ' + esc(session['responsible_name'])) if session['responsible_name'] else '') + '</p><p><strong>Primeira mensagem:</strong> ' + esc(session['initial_message'] or '') + '</p>'
            back_link = '/admin/contatos' if is_super(user) else '/admin/chats'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<a class="text-link" href="' + back_link + '">← Atendimentos</a><p class="eyebrow">ATENDIMENTO DE VISITANTE</p><h1>' + esc(session['name']) + '</h1><div class="panel-dash-grid"><div class="panel-col">' + panel_card('Dados do contato', details) + '</div><div class="panel-col">' + panel_card('Conversa', '<div class="guest-chat panel" id="guest-chat" data-guest-endpoint="/admin/atendimento-visitante/mensagens?guest_id=' + str(guest_id) + '"><div class="guest-chat-head"><strong>' + esc(status_label) + '</strong><small>' + esc(session['email']) + '</small></div><div class="thread guest-thread" data-guest-thread>' + guest_thread_html(session, messages, staff_view=True) + '</div>' + reply_form + '</div>', '') + (panel_card('Encerrar', '<p class="muted">O visitante deixa de enviar mensagens por este link.</p>' + close_form) if close_form else '') + '</div></div></section>'
            return self.page('Atendimento de visitante', content, user)
        if path == '/admin/permissoes':
            if not user or not is_super(user):
                return self.forbidden()
            with db() as c:
                permission_users = c.execute("SELECT id,name,email,role,is_super FROM users WHERE role IN ('admin','staff') AND deleted_at='' ORDER BY role,name").fetchall()
                blocks = []
                for target in permission_users:
                    if target['is_super']:
                        continue
                    checkboxes = ''.join('<label class="check"><input type="checkbox" name="' + action + '" value="1"' + (' checked' if has_permission(c, target, action) else '') + '> ' + label + '</label>' for action, label in PERMISSION_ACTIONS)
                    blocks.append('<div class="case-box"><h3>' + esc(target['name']) + '</h3><p class="case-meta">' + esc(target['email']) + ' · ' + esc(target['role']) + '</p>' + form('/admin/permissoes', '<input type="hidden" name="user_id" value="' + str(target['id']) + '">' + checkboxes, 'Salvar permissões') + '</div>')
            content = '<section class="wrap section">' + self.admin_nav(user) + '<h1>Permissões</h1><p class="muted">Ajuste as permissões individuais. Super admins têm acesso total. Desmarcar uma permissão nega a ação mesmo que seja padrão do perfil.</p>' + (''.join(blocks) or '<p>Nenhum usuário interno para configurar.</p>') + '<p><a class="text-link" href="/admin">Voltar ao painel</a></p></section>'
            return self.page('Permissões', content, user)
        if path == '/admin/configuracoes':
            if not user or not is_super(user):
                return self.forbidden()
            with db() as c:
                values = {r['key']: r['value'] for r in c.execute('SELECT key,value FROM settings')}
            form_html = form('/admin/configuracoes', input_field('Horas para mensagem não visualizada', 'unread_hours', values.get('unread_hours', '24'), 'number') + input_field('Horas sem movimentação', 'stale_hours', values.get('stale_hours', '48'), 'number') + input_field('Horas de antecedência de compromisso', 'appointment_reminder_hours', values.get('appointment_reminder_hours', '24'), 'number') + '<label class="check"><input type="checkbox" name="email_notifications" value="1"' + (' checked' if values.get('email_notifications') == '1' else '') + '> Notificações por e-mail (requer SMTP configurado)</label><label class="check"><input type="checkbox" name="chat_online" value="1"' + (' checked' if values.get('chat_online', '1') == '1' else '') + '> Chat do site online</label><p class="muted">Quando desmarcado, o balãozinho continua aceitando mensagens e informa que o atendimento responderá depois.</p>', 'Salvar configurações')
            content = '<section class="wrap section">' + self.admin_nav(user) + '<h1>Configurações</h1><p class="muted">Parâmetros gerais de alertas e notificações. O e-mail ainda depende de configuração técnica de SMTP.</p>' + card('Parâmetros', form_html) + '<p><a class="text-link" href="/admin">Voltar ao painel</a></p></section>'
            return self.page('Configurações', content, user)
        if path == '/admin/cliente/exportar':
            if not user or not is_super(user):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                client_id = int(query.get('client_id', ['0'])[0])
            except (TypeError, ValueError):
                client_id = 0
            with db() as c:
                payload = client_export(c, client_id)
            if not payload:
                return self.forbidden()
            data = json.dumps(payload, ensure_ascii=False, indent=2)
            return self.send(data, ctype='application/json; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="dados-titular-' + str(client_id) + '.json"'})
        if path == '/admin/cliente':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            raw_id = query.get('client_id', [''])[0]
            if not raw_id.isdigit():
                return self.forbidden()
            client_id = int(raw_id)
            with db() as c:
                client = c.execute("SELECT u.id,u.name,u.email,u.phone,u.active,u.portal_enabled,u.owner_staff_id,owner.name AS owner_name FROM users u LEFT JOIN users owner ON owner.id=u.owner_staff_id WHERE u.id=? AND u.role='client' AND u.deleted_at=''", (client_id,)).fetchone()
                if not client:
                    return self.forbidden()
                cases = [row for row in self.visible_cases(c, user) if row['client_id'] == client_id]
                conversations = [row for row in conversation_rows(c, user) if row['client_id'] == client_id]
                manageable = self.can_manage(c, user, client_id)
                can_cases = manageable and has_permission(c, user, 'manage_cases')
                can_message = manageable and has_permission(c, user, 'send_messages')
                can_documents = manageable and has_permission(c, user, 'manage_documents')
                team = c.execute('SELECT a.id AS assignment_id,u.id,u.name FROM assignments a JOIN users u ON u.id=a.staff_id WHERE a.client_id=? AND u.deleted_at=\'\' ORDER BY u.name', (client_id,)).fetchall()
                available_staff = c.execute("SELECT id,name FROM users WHERE role IN ('staff','admin') AND active=1 AND deleted_at='' ORDER BY name").fetchall() if (is_super(user) or user['role'] == 'admin') else []
                docs = c.execute("SELECT id,filename,status,case_id FROM documents WHERE client_id=? AND deleted_at='' AND (case_id IS NULL OR case_id IN (SELECT id FROM cases WHERE deleted_at='')) AND (case_id IS NOT NULL OR ?=1) ORDER BY id DESC LIMIT 10", (client_id, int(manageable))).fetchall()
                pending = c.execute("SELECT title,status,case_id FROM pendencies WHERE client_id=? AND status!='Atendida' AND (case_id IS NULL OR case_id IN (SELECT id FROM cases WHERE deleted_at='')) AND (case_id IS NOT NULL OR ?=1) ORDER BY id DESC LIMIT 10", (client_id, int(manageable))).fetchall()
                apps = c.execute("SELECT title,when_at,case_id FROM appointments WHERE client_id=? AND privacy='client' AND status='pendente' AND deleted_at='' AND replace(when_at,'T',' ')>=? AND (case_id IS NULL OR case_id IN (SELECT id FROM cases WHERE deleted_at='')) AND (case_id IS NOT NULL OR ?=1) ORDER BY replace(when_at,'T',' ') LIMIT 5", (client_id, datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), int(manageable))).fetchall()
            case_items = ''.join('<li><a class="text-link" href="/admin/caso/historico?case_id=' + str(row['id']) + '">' + esc(row['title']) + '</a> · ' + status_badge(row['status']) + '</li>' for row in cases) or '<li>Nenhum atendimento.</li>'
            portal_html = ('<p><strong>Portal:</strong> acesso habilitado · <a class="text-link" href="mailto:' + esc(client['email']) + '">' + esc(client['email']) + '</a></p>' if client['portal_enabled'] else '<p><strong>Portal:</strong> sem acesso ao portal.</p>')
            details = portal_html + '<p><strong>Telefone:</strong> ' + esc(client['phone'] or 'Não informado') + '</p><p><strong>Responsável principal:</strong> ' + esc(client['owner_name'] or 'Não atribuído') + '</p><p><strong>Equipe vinculada:</strong> ' + esc(', '.join(row['name'] for row in team) or 'Nenhuma') + '</p>'
            if not client['portal_enabled'] and manageable:
                details += '<details class="admin-secondary"><summary>Habilitar acesso ao portal</summary><p class="muted">Valide a identidade do cliente antes de habilitar. O e-mail não pode estar em outra conta.</p>' + form('/admin/cliente/portal', '<input type="hidden" name="client_id" value="' + str(client_id) + '">' + field('E-mail de acesso', 'email', 'email') + field('Senha inicial', 'password', 'password') + field('Confirmar senha', 'confirm', 'password'), 'Habilitar acesso') + '</details>'
            if is_super(user) or user['role'] == 'admin':
                team_ids = {row['id'] for row in team}
                choices = ''.join('<option value="' + str(row['id']) + '">' + esc(row['name']) + '</option>' for row in available_staff if row['id'] not in team_ids)
                context = '<input type="hidden" name="client_id" value="' + str(client_id) + '"><input type="hidden" name="return_to" value="' + esc(admin_context_return(client_id=client_id)) + '">'
                add = form('/admin/assign', context + '<label>Profissional<select name="staff_id" required><option value="">Selecione</option>' + choices + '</select></label>', 'Vincular profissional') if choices else '<p class="muted">Não há outros profissionais disponíveis.</p>'
                removals = ''.join('<li>' + esc(row['name']) + (' · responsável principal' if row['id'] == client['owner_staff_id'] else form('/admin/unassign', context + '<input type="hidden" name="assignment_id" value="' + str(row['assignment_id']) + '">', 'Remover vínculo')) + '</li>' for row in team) or '<li>Nenhum profissional vinculado.</li>'
                details += '<details class="admin-secondary"><summary>Gerenciar equipe vinculada</summary><ul>' + removals + '</ul>' + add + '</details>'
            doc_items = ''.join('<li><a class="text-link" href="/arquivo/' + str(row['id']) + '">' + esc(row['filename']) + '</a> ' + document_badge(row['status']) + '</li>' for row in docs) or '<li>Nenhum documento.</li>'
            pending_items = ''.join('<li>' + esc(row['title']) + ' ' + pendency_badge(row['status']) + '</li>' for row in pending) or '<li>Nenhuma pendência aberta.</li>'
            app_items = ''.join('<li><strong>' + esc(fmt_when(row['when_at'])) + '</strong> · ' + esc(row['title']) + '</li>' for row in apps) or '<li>Nenhum compromisso próximo.</li>'
            actions = admin_context_actions(client_id, can_message=can_message, can_cases=can_cases, can_documents=can_documents)
            new_case = ''
            if can_cases:
                status_choices = ''.join('<option>' + status + '</option>' for status in ('Em andamento', 'Aguardando cliente', 'Concluído', 'Informativo', 'Suspenso'))
                new_case = '<details class="conversation-new"><summary>Cadastrar novo caso para este cliente</summary>' + form('/admin/caso', '<input type="hidden" name="client_id" value="' + str(client_id) + '"><input type="hidden" name="return_to" value="' + esc(admin_context_return(client_id=client_id)) + '">' + field('Título do caso', 'title') + field('Número do processo', 'case_number', required=False) + field('Área', 'area', required=False) + '<label>Status<select name="status">' + status_choices + '</select></label><label>Descrição<textarea name="description"></textarea></label>', 'Cadastrar caso') + '</details>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<a class="text-link" href="/admin/clientes">← Clientes</a><p class="eyebrow">FICHA DO CLIENTE</p><h1>' + esc(client['name']) + '</h1>' + actions + new_case + '<div class="dashboard"><div>' + card('Atendimentos', '<ul>' + case_items + '</ul>') + card('Conversas', conversation_cards(conversations[:5], user) + '<p><a class="text-link" href="/admin/mensagens?client_id=' + str(client_id) + '">Ver conversas do cliente →</a></p>') + card('Documentos recentes', '<ul>' + doc_items + '</ul>') + '</div><div>' + card('Contato e equipe', details) + card('Pendências', '<ul>' + pending_items + '</ul>') + card('Próximos compromissos', '<ul>' + app_items + '</ul>') + '</div></div></section>'
            return self.page('Ficha do cliente', content, user)
        if path == '/admin/clientes':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            term = query.get('q', [''])[0].strip()[:150]
            state = query.get('status', [''])[0]
            responsible = query.get('responsavel', [''])[0]
            with db() as c:
                editable_clients = {row['id'] for row in self.scoped_clients(c, user)}
                clients = c.execute("SELECT * FROM users WHERE role='client' AND deleted_at='' ORDER BY name").fetchall()
                can_create = has_permission(c, user, 'create_clients')
                staff_rows = c.execute("SELECT id,name FROM users WHERE role IN ('staff','admin') AND active=1 AND deleted_at='' ORDER BY name").fetchall()
            if term:
                needle = term.casefold()
                clients = [row for row in clients if needle in (row['name'] + ' ' + row['email'] + ' ' + (row['phone'] or '')).casefold()]
            if state in ('ativo', 'inativo'):
                clients = [row for row in clients if bool(row['active']) == (state == 'ativo')]
            if responsible == 'sem':
                clients = [row for row in clients if not row['owner_staff_id']]
            elif responsible.isdigit():
                clients = [row for row in clients if row['owner_staff_id'] == int(responsible)]
            clients, pagination, total = self.paginate_rows(clients)
            owner_names = {x['id']: x['name'] for x in staff_rows}
            if user['role'] == 'admin':
                owner_options = ''.join(f'<option value="{x["id"]}">{esc(x["name"])}</option>' for x in staff_rows)
                create_owner = '<label>Responsável<select name="owner_staff_id"><option value="">Sem responsável</option>' + owner_options + '</select></label>'
            else:
                create_owner = f'<input type="hidden" name="owner_staff_id" value="{user["id"]}">'
            create_form = form('/admin/cliente', field('Nome', 'name') + field('E-mail', 'email', 'email') + field('Telefone', 'phone', required=False) + field('Senha inicial', 'password', 'password') + field('Confirmar senha', 'confirm', 'password') + create_owner, 'Cadastrar cliente')
            internal_form = form('/admin/cliente/interno', field('Nome', 'name') + field('Telefone', 'phone', required=False) + create_owner, 'Cadastrar cliente interno')
            blocks = []
            for x in clients:
                owner = owner_names.get(x['owner_staff_id'], '')
                portal_enabled = bool(x['portal_enabled'])
                if user['role'] == 'admin':
                    owner_options = ''.join(f'<option value="{s["id"]}"' + (' selected' if x['owner_staff_id'] == s['id'] else '') + f'>{esc(s["name"])}</option>' for s in staff_rows)
                    owner_field = '<label>Responsável principal<select name="owner_staff_id"><option value="">Sem responsável</option>' + owner_options + '</select></label><p class="muted">Alterar o responsável não remove outros vínculos. Gerencie a equipe na ficha do cliente.</p>'
                    email_input = input_field('E-mail', 'email', x['email'], 'email') if portal_enabled else '<p class="case-meta">Sem acesso ao portal. Habilite o acesso na ficha do cliente.</p>'
                else:
                    owner_field = ''
                    email_input = ('<p class="case-meta">E-mail: ' + esc(x['email']) + '</p>') if portal_enabled else '<p class="case-meta">Sem acesso ao portal.</p>'
                edit_fields = f'<input type="hidden" name="client_id" value="{x["id"]}">' + input_field('Nome', 'name', x['name']) + email_input + input_field('Telefone', 'phone', x['phone'], required=False) + '<label class="check"><input type="checkbox" name="active" value="1"' + (' checked' if x['active'] else '') + '> Ativo</label>' + owner_field + input_field('Nova senha (opcional)', 'password', '', 'password', required=False)
                lgpd_link = ('<p><a class="text-link" href="/admin/cliente/exportar?client_id=' + str(x['id']) + '">Exportar dados do titular (JSON)</a></p>') if is_super(user) else ''
                edit = '<details class="conversation-new"><summary>Editar cadastro</summary>' + form('/admin/cliente/editar', edit_fields, 'Salvar alterações') + lgpd_link + (form('/admin/delete', '<input type="hidden" name="entity" value="client"><input type="hidden" name="record_id" value="' + str(x['id']) + '">', 'Mover para lixeira') if is_super(user) else '') + '</details>' if can_create and x['id'] in editable_clients else ''
                blocks.append('<div class="case-box"><h3>' + esc(x['name']) + '</h3><p class="case-meta">' + (esc(x['email']) if portal_enabled else 'Sem acesso ao portal') + ' · ' + ('Ativo' if x['active'] else 'Inativo') + (' · responsável: ' + esc(owner) if owner else '') + '</p><p><a class="text-link" href="/admin/cliente?client_id=' + str(x['id']) + '">Abrir ficha do cliente →</a></p>' + edit + '</div>')
            create = ('<details class="conversation-new"><summary>Cadastrar cliente com acesso ao portal</summary>' + create_form + '</details><details class="conversation-new"><summary>Cadastrar cliente interno (sem acesso ao portal)</summary>' + internal_form + '<p class="muted">O acesso ao portal pode ser habilitado depois na ficha do cliente, com validação de identidade.</p></details>') if can_create else ''
            status_options = ''.join('<option value="' + value + '"' + (' selected' if state == value else '') + '>' + label + '</option>' for value, label in (('', 'Todos'), ('ativo', 'Ativos'), ('inativo', 'Inativos')))
            owner_filter = '<option value="">Todos</option><option value="sem"' + (' selected' if responsible == 'sem' else '') + '>Sem responsável</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if responsible == str(row['id']) else '') + '>' + esc(row['name']) + '</option>' for row in staff_rows)
            filters = '<form method="get" action="/admin/clientes" class="admin-filters"><label>Buscar cliente<input type="search" name="q" value="' + esc(term) + '" placeholder="Nome, e-mail ou telefone"></label><label>Situação<select name="status">' + status_options + '</select></label><label>Responsável<select name="responsavel">' + owner_filter + '</select></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/clientes">Limpar</a></form>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Clientes</h1><p class="muted">Consulte clientes e atendimentos. As alterações seguem suas permissões.</p>' + create + filters + '<h2>Clientes cadastrados <small class="result-count">' + str(total) + '</small></h2>' + (''.join(blocks) or '<p>Nenhum cliente encontrado.</p>') + pagination + '</section>'
            return self.page('Clientes', content, user)
        if path == '/admin/seguranca':
            if not user or not is_super(user):
                return self.forbidden()
            with db() as c:
                return self.security_page(user, c)
        if path == '/admin/usuarios':
            if not user or not is_super(user):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            term = query.get('q', [''])[0].strip()[:150]
            role_filter = query.get('perfil', [''])[0]
            state = query.get('status', [''])[0]
            with db() as c:
                user_rows = c.execute("SELECT id,name,email,role,staff_kind,active,is_super,must_change,totp_enabled,created FROM users WHERE deleted_at='' ORDER BY role,name").fetchall()
            role_labels = {'client': 'Cliente', 'staff': 'Advogado/Funcionário', 'admin': 'Administrador'}
            if term:
                needle = term.casefold()
                user_rows = [row for row in user_rows if needle in (row['name'] + ' ' + row['email']).casefold()]
            if role_filter in role_labels:
                user_rows = [row for row in user_rows if row['role'] == role_filter]
            if state in ('ativo', 'inativo'):
                user_rows = [row for row in user_rows if bool(row['active']) == (state == 'ativo')]
            user_rows, pagination, total = self.paginate_rows(user_rows)
            blocks = []
            for x in user_rows:
                role_options = ''.join(f'<option value="{r}"' + (' selected' if x['role'] == r else '') + f'>{role_labels[r]}</option>' for r in ('client', 'staff', 'admin'))
                kind = x['staff_kind'] if x['staff_kind'] in ('lawyer', 'employee') else 'lawyer'
                kind_options = ''.join('<option value="' + value + '"' + (' selected' if kind == value else '') + '>' + label + '</option>' for value, label in (('lawyer', 'Advogado'), ('employee', 'Funcionário')))
                active_checked = ' checked' if x['active'] else ''
                super_checked = ' checked' if x['is_super'] else ''
                kind_label = (' · ' + ('Advogado' if kind == 'lawyer' else 'Funcionário')) if x['role'] == 'staff' else ''
                edit = input_field('Nome', 'name', x['name']) + input_field('E-mail', 'email', x['email'], 'email') + '<label>Perfil<select name="role">' + role_options + '</select></label><label>Função na equipe<select name="staff_kind">' + kind_options + '</select></label><label class="check"><input type="checkbox" name="active" value="1"' + active_checked + '> Ativo</label><label class="check"><input type="checkbox" name="is_super" value="1"' + super_checked + '> Super admin</label>' + input_field('Nova senha (opcional)', 'password', '', 'password', required=False)
                mfa_reset = form('/admin/user/mfa-reset', '<input type="hidden" name="user_id" value="' + str(x['id']) + '">', 'Redefinir MFA') if x['totp_enabled'] else ''
                blocks.append('<div class="case-box"><h3>' + esc(x['name']) + (' — super admin' if x['is_super'] else '') + '</h3><p class="case-meta">' + esc(x['email']) + ' · ' + role_labels.get(x['role'], x['role']) + kind_label + ' · ' + ('Ativo' if x['active'] else 'Inativo') + (' · MFA ativado' if x['totp_enabled'] else '') + ' · criado em ' + esc(x['created']) + '</p><details class="admin-secondary"><summary>Editar conta</summary>' + form('/admin/user/edit', '<input type="hidden" name="user_id" value="' + str(x['id']) + '">' + edit, 'Salvar alterações') + mfa_reset + '</details></div>')
            create_form = form('/admin/user', field('Nome', 'name') + field('E-mail', 'email', 'email') + field('Senha inicial', 'password', 'password') + '<label>Perfil<select name="role"><option value="client">Cliente</option><option value="staff">Advogado ou funcionário</option><option value="admin">Administrador</option></select></label><label>Função na equipe<select name="staff_kind"><option value="lawyer">Advogado</option><option value="employee">Funcionário</option></select></label><label class="check"><input type="checkbox" name="is_super" value="1"> Super admin</label>', 'Cadastrar')
            role_options = '<option value="">Todos</option>' + ''.join('<option value="' + key + '"' + (' selected' if role_filter == key else '') + '>' + value + '</option>' for key, value in role_labels.items())
            state_options = ''.join('<option value="' + value + '"' + (' selected' if state == value else '') + '>' + label + '</option>' for value, label in (('', 'Todos'), ('ativo', 'Ativos'), ('inativo', 'Inativos')))
            filters = '<form method="get" action="/admin/usuarios" class="admin-filters"><label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Nome ou e-mail"></label><label>Perfil<select name="perfil">' + role_options + '</select></label><label>Situação<select name="status">' + state_options + '</select></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/usuarios">Limpar</a></form>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Usuários</h1><p class="muted">Gestão de contas, perfis e super admins. Toda alteração é auditada.</p><details class="conversation-new"><summary>Cadastrar usuário</summary>' + create_form + '</details>' + filters + '<h2>Contas cadastradas <small class="result-count">' + str(total) + '</small></h2>' + (''.join(blocks) or '<p>Nenhuma conta encontrada.</p>') + pagination + '</section>'
            return self.page('Usuários', content, user)
        if path == '/admin/caso/historico':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                case_id = int(query.get('case_id', ['0'])[0])
            except (TypeError, ValueError):
                case_id = 0
            with db() as c:
                case_row = c.execute("SELECT ca.*, u.name AS client_name, ru.name AS responsible_name FROM cases ca JOIN users u ON u.id=ca.client_id LEFT JOIN users ru ON ru.id=ca.responsible_id WHERE ca.id=? AND ca.deleted_at=''", (case_id,)).fetchone()
                if not case_row or not self.can_view_case(c, user, case_id):
                    return self.forbidden()
                events = c.execute('SELECT e.*, u.name AS actor FROM case_events e LEFT JOIN users u ON u.id=e.actor_id WHERE e.case_id=? ORDER BY e.id ASC', (case_id,)).fetchall()
                conversations = conversation_rows(c, user, case_id=case_id)
                internal_conversations = [row for row in conversations if row['visibility'] == 'internal']
                client_conversations = [row for row in conversations if row['visibility'] == 'client']
                case_tasks = [row for row in self.task_rows(c, user) if row['case_id'] == case_id]
                documents = c.execute("SELECT id,filename,status FROM documents WHERE case_id=? AND deleted_at='' ORDER BY id DESC", (case_id,)).fetchall()
                pendencies = c.execute('SELECT title,status FROM pendencies WHERE case_id=? ORDER BY id DESC', (case_id,)).fetchall()
                appointments = c.execute("SELECT * FROM appointments WHERE case_id=? AND deleted_at='' ORDER BY when_at", (case_id,)).fetchall()
                appointments = [row for row in appointments if self.can_view_appointment(c, user, row)]
                updates = c.execute('SELECT title,body FROM updates WHERE case_id=? ORDER BY id DESC', (case_id,)).fetchall()
                assigned = c.execute("SELECT u.id,u.name FROM case_assignments ca JOIN users u ON u.id=ca.staff_id WHERE ca.case_id=? AND u.deleted_at='' ORDER BY u.name", (case_id,)).fetchall()
                can_manage_case = self.can_access_case(c, user, case_id)
                can_cases = can_manage_case and has_permission(c, user, 'manage_cases')
                can_message = can_manage_case and has_permission(c, user, 'send_messages')
                can_documents = can_manage_case and has_permission(c, user, 'manage_documents')
                staff = c.execute("SELECT id,name,active,deleted_at FROM users WHERE role IN ('staff','admin') AND ((active=1 AND deleted_at='') OR id=?) ORDER BY name", (case_row['responsible_id'],)).fetchall() if user['role'] == 'admin' else []
            event_items = []
            for event in events:
                detail = event['description'] or event['event_type']
                if event['from_status'] or event['to_status']:
                    detail += ' (' + (event['from_status'] or '—') + ' → ' + (event['to_status'] or '—') + ')'
                if event['old_title'] or event['new_title']:
                    detail += ' (' + (event['old_title'] or '—') + ' → ' + (event['new_title'] or '—') + ')'
                event_items.append('<div class="request"><strong>' + esc(event['created']) + ' — ' + esc(event['event_type']) + '</strong><p>' + esc(detail) + '</p><p class="muted">' + esc(event['actor'] or 'Sistema') + ' · ' + ('visível ao cliente' if event['visible_to_client'] else 'interno') + '</p></div>')
            details = '<p><strong>Cliente:</strong> <a class="text-link" href="/admin/cliente?client_id=' + str(case_row['client_id']) + '">' + esc(case_row['client_name']) + '</a></p><p><strong>Título original:</strong> ' + esc(case_row['original_title'] or case_row['title']) + '</p><p><strong>Responsável principal:</strong> ' + esc(case_row['responsible_name'] or 'Sem responsável') + '</p><p><strong>Equipe vinculada:</strong> ' + esc(', '.join(row['name'] for row in assigned) or 'Nenhuma') + '</p><p><strong>Status:</strong> ' + status_badge(case_row['status']) + '</p><p><strong>Origem:</strong> ' + esc(case_row['source'] or 'interno') + '</p><p><strong>Criado em:</strong> ' + esc(case_row['created']) + ' · <strong>Atualizado em:</strong> ' + esc(case_row['updated'] or case_row['created']) + '</p><p>' + esc(case_row['description']) + '</p>'
            if (is_super(user) or user['role'] == 'admin') and can_cases:
                assigned_ids = {row['id'] for row in assigned}
                choices = ''.join('<option value="' + str(row['id']) + '">' + esc(row['name']) + '</option>' for row in staff if row['id'] not in assigned_ids and row['active'] and not row['deleted_at'])
                context = '<input type="hidden" name="case_id" value="' + str(case_id) + '"><input type="hidden" name="return_to" value="' + esc(admin_context_return(case_id=case_id)) + '">'
                add = form('/admin/caso/equipe', context + '<input type="hidden" name="operation" value="add"><label>Profissional<select name="staff_id" required><option value="">Selecione</option>' + choices + '</select></label>', 'Vincular profissional') if choices else '<p class="muted">Não há outros profissionais disponíveis.</p>'
                removals = ''.join('<li>' + esc(row['name']) + (' · responsável principal' if row['id'] == case_row['responsible_id'] else form('/admin/caso/equipe', context + '<input type="hidden" name="operation" value="remove"><input type="hidden" name="staff_id" value="' + str(row['id']) + '">', 'Remover vínculo')) + '</li>' for row in assigned) or '<li>Nenhum profissional vinculado.</li>'
                details += '<details class="admin-secondary"><summary>Gerenciar equipe vinculada</summary><ul>' + removals + '</ul>' + add + '</details>'
            document_items = ''.join('<li><a class="text-link" href="/arquivo/' + str(doc['id']) + '">' + esc(doc['filename']) + '</a> ' + document_badge(doc['status']) + (' · <a class="text-link" href="/admin/documento?doc_id=' + str(doc['id']) + '&amp;retorno=1">Analisar</a>' if can_documents else '') + '</li>' for doc in documents) or '<li>Nenhum documento.</li>'
            pending_items = ''.join('<li>' + esc(item['title']) + ' · ' + pendency_badge(item['status']) + '</li>' for item in pendencies) or '<li>Nenhuma pendência.</li>'
            appointment_items = ''.join('<li>' + esc(fmt_when(item['when_at'])) + ' · ' + esc(item['title']) + ' ' + appointment_badge(item['status']) + '</li>' for item in appointments) or '<li>Nenhum compromisso.</li>'
            update_items = ''.join('<li><strong>' + esc(item['title']) + '</strong> — ' + esc(item['body']) + '</li>' for item in updates) or '<li>Nenhuma atualização.</li>'
            edit = ''
            if can_cases:
                statuses = ('Em andamento', 'Aguardando cliente', 'Concluído', 'Informativo', 'Suspenso')
                choices = ''.join('<option' + (' selected' if case_row['status'] == status else '') + '>' + esc(status) + '</option>' for status in statuses)
                responsible = ''
                if user['role'] == 'admin':
                    choices_staff = ''.join('<option value="' + str(row['id']) + '"' + (' selected' if row['id'] == case_row['responsible_id'] else '') + '>' + esc(row['name']) + (' (inativo)' if not row['active'] or row['deleted_at'] else '') + '</option>' for row in staff)
                    responsible = '<label>Responsável principal<select name="responsible_id"><option value="">Sem responsável</option>' + choices_staff + '</select></label><p class="muted">Alterar o responsável não remove os demais profissionais vinculados.</p>'
                fields = '<input type="hidden" name="case_id" value="' + str(case_id) + '"><input type="hidden" name="return_to" value="' + esc(admin_context_return(case_id=case_id)) + '">' + input_field('Título', 'title', case_row['title']) + input_field('Número do processo', 'case_number', case_row['case_number'], required=False) + input_field('Área', 'area', case_row['area'], required=False) + '<label>Status<select name="status">' + choices + '</select></label><label>Descrição<textarea name="description">' + esc(case_row['description']) + '</textarea></label>' + responsible
                edit = '<details class="conversation-new"><summary>Editar dados e responsável</summary>' + form('/admin/caso/editar', fields, 'Salvar alterações') + '</details>'
            actions = admin_context_actions(case_row['client_id'], case_id, can_message, can_cases, can_documents)
            history = '<details class="conversation-history"><summary>Histórico de eventos</summary>' + (''.join(event_items) or '<p>Nenhum evento registrado.</p>') + '</details>'
            pending_link = '<p><a class="text-link" href="/admin/pendencias?case_id=' + str(case_id) + '&amp;client_id=' + str(case_row['client_id']) + '&amp;status=todas">Gerenciar pendências →</a></p>' if can_cases else ''
            internal_form = ''
            if can_message:
                internal_form = form('/admin/mensagem', '<input type="hidden" name="client_id" value="' + str(case_row['client_id']) + '"><input type="hidden" name="case_id" value="' + str(case_id) + '"><input type="hidden" name="visibility" value="internal">' + field('Assunto interno', 'subject') + '<label>Mensagem interna<textarea name="body" rows="3" required></textarea></label>', 'Enviar à equipe')
            internal_html = '<div class="case-channel case-channel-internal"><div class="case-channel-head"><span class="conversation-channel internal">Comunicação interna</span><span class="muted">Somente a equipe autorizada do caso visualiza estas mensagens.</span></div><div class="conversation-list">' + conversation_cards(internal_conversations, user) + '</div><p><a class="text-link" href="/admin/mensagens?tipo=interno&case_id=' + str(case_id) + '">Abrir histórico interno →</a></p>' + internal_form + '</div>'
            client_channel_html = '<div class="case-channel case-channel-client"><div class="case-channel-head"><span class="conversation-channel client">Conversa com o cliente</span><span class="muted">Mensagens visíveis ao cliente na Área do Cliente.</span></div><div class="conversation-list">' + conversation_cards(client_conversations, user) + '</div></div>'
            task_items = ''.join('<li><a class="text-link" href="/admin/tarefa?task_id=' + str(task['id']) + '">' + esc(task['title']) + '</a> ' + task_status_badge(task) + task_priority_badge(task['priority']) + '</li>' for task in case_tasks) or '<li>Nenhuma tarefa vinculada.</li>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<a class="text-link" href="/admin/casos">← Casos</a><p class="eyebrow">FICHA DO ATENDIMENTO</p><h1>' + esc(case_row['title']) + '</h1>' + actions + edit + '<div class="dashboard"><div>' + card('Dados do caso', details) + card('Comunicação com o cliente', client_channel_html) + card('Comunicação interna', internal_html) + card('Documentos', '<ul>' + document_items + '</ul>') + '</div><div>' + card('Tarefas e prazos', '<ul>' + task_items + '</ul><p><a class="text-link" href="/admin/tarefas?case_id=' + str(case_id) + '">Gerenciar tarefas →</a></p>') + card('Pendências', '<ul>' + pending_items + '</ul>' + pending_link) + card('Compromissos', '<ul>' + appointment_items + '</ul><p><a class="text-link" href="/admin/compromissos?case_id=' + str(case_id) + '">Abrir agenda →</a></p>') + card('Atualizações', '<ul>' + update_items + '</ul>') + history + '</div></div></section>'
            return self.page('Histórico do caso', content, user)
        if path == '/admin/casos':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            admin = user['role'] == 'admin'
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            term = query.get('q', [''])[0].strip()[:150]
            case_status = query.get('status', [''])[0]
            responsible = query.get('responsavel', [''])[0]
            client_filter = query.get('client_id', [''])[0]
            with db() as c:
                can_edit_cases = has_permission(c, user, 'manage_cases')
                clients = self.scoped_clients(c, user)
                editable_ids = {row['id'] for row in self.scoped_cases(c, user)} if can_edit_cases else set()
                cases = self.visible_cases(c, user)
                staff_only = c.execute("SELECT id,name,active,deleted_at FROM users WHERE role IN ('staff','admin') ORDER BY name").fetchall()
                stale_hours = max(1, int(setting(c, 'stale_hours', '48') or 48))
            statuses = ('Em andamento', 'Aguardando cliente', 'Concluído', 'Informativo', 'Suspenso')
            if term:
                needle = term.casefold()
                cases = [row for row in cases if needle in ' '.join(str(row[key] or '') for key in ('title', 'original_title', 'case_number', 'area', 'client_name')).casefold()]
            if case_status in statuses:
                cases = [row for row in cases if row['status'] == case_status]
            if responsible == 'sem':
                cases = [row for row in cases if not row['responsible_id'] and row['status'] not in ('Concluído', 'Suspenso')]
            elif responsible.isdigit():
                cases = [row for row in cases if row['responsible_id'] == int(responsible)]
            if client_filter.isdigit():
                cases = [row for row in cases if row['client_id'] == int(client_filter)]
            cases, pagination, total = self.paginate_rows(cases)
            client_options = ''.join(f'<option value="{x["id"]}">{esc(x["name"])} ({esc(x["email"])})</option>' for x in clients)
            client_select = '<label>Cliente<select name="client_id" required>' + client_options + '</select></label>' if clients else ''
            if admin:
                staff_options = ''.join(f'<option value="{x["id"]}">{esc(x["name"])}</option>' for x in staff_only if x['active'] and not x['deleted_at'])
                create_responsible = '<label>Responsável<select name="responsible_id"><option value="">Não atribuído</option>' + staff_options + '</select></label>'
            else:
                create_responsible = f'<input type="hidden" name="responsible_id" value="{user["id"]}">'
            status_options = ''.join(f'<option>{s}</option>' for s in statuses)
            create_form = form('/admin/caso', client_select + field('Título do caso', 'title') + field('Número do processo', 'case_number', required=False) + field('Área', 'area', required=False) + '<label>Status<select name="status">' + status_options + '</select></label><label>Descrição<textarea name="description"></textarea></label>' + create_responsible, 'Criar caso')
            blocks = []
            for x in cases:
                if admin:
                    responsible_options = ''.join(f'<option value="{s["id"]}"' + (' selected' if x['responsible_id'] == s['id'] else '') + '>' + esc(s['name']) + (' (inativo)' if not s['active'] or s['deleted_at'] else '') + '</option>' for s in staff_only if (s['active'] and not s['deleted_at']) or x['responsible_id'] == s['id'])
                    responsible_field = '<label>Responsável principal<select name="responsible_id"><option value="">Não atribuído</option>' + responsible_options + '</select></label><p class="muted">Outros vínculos são preservados; gerencie a equipe na ficha do atendimento.</p>'
                else:
                    responsible_field = f'<input type="hidden" name="responsible_id" value="{user["id"]}">'
                case_status_select = ''.join(f'<option' + (' selected' if x['status'] == s else '') + f'>{s}</option>' for s in statuses)
                edit_fields = f'<input type="hidden" name="case_id" value="{x["id"]}">' + input_field('Título do caso', 'title', x['title']) + input_field('Número do processo', 'case_number', x['case_number'], required=False) + input_field('Área', 'area', x['area'], required=False) + '<label>Status<select name="status">' + case_status_select + '</select></label><label>Descrição<textarea name="description">' + esc(x['description']) + '</textarea></label>' + responsible_field
                edit_html = '<details class="conversation-new"><summary>Editar caso</summary>' + form('/admin/caso/editar', edit_fields, 'Salvar alterações') + '</details>' if x['id'] in editable_ids else '<p class="muted">Consulta disponível; alterações restritas ao responsável.</p>'
                trash = '<details class="admin-secondary"><summary>Mais ações</summary>' + form('/admin/delete', '<input type="hidden" name="entity" value="case"><input type="hidden" name="record_id" value="' + str(x['id']) + '">', 'Mover para lixeira') + '</details>' if is_super(user) else ''
                blocks.append('<div class="' + status_box_class('case-box', x['status'], x['last_activity_at'] or x['created'], stale_hours) + '"><h3>#' + str(x['id']) + ' — ' + esc(x['title']) + '</h3><p class="case-meta">' + esc(x['client_name']) + ' · ' + status_badge(x['status']) + ' · atualizado em ' + esc(x['updated'] or x['created']) + '</p>' + ('' if x['responsible_id'] else '<p><span class="status-badge status-yellow">Sem responsável</span></p>') + '<p><a class="text-link" href="/admin/caso/historico?case_id=' + str(x['id']) + '">Abrir ficha do atendimento →</a></p>' + edit_html + trash + '</div>')
            create_html = '<details class="conversation-new"><summary>Criar caso</summary>' + create_form + '</details>' if clients and can_edit_cases else ''
            status_filter = '<option value="">Todos</option>' + ''.join('<option value="' + esc(value) + '"' + (' selected' if case_status == value else '') + '>' + esc(value) + '</option>' for value in statuses)
            owner_filter = '<option value="">Todos</option><option value="sem"' + (' selected' if responsible == 'sem' else '') + '>Sem responsável</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if responsible == str(row['id']) else '') + '>' + esc(row['name']) + '</option>' for row in staff_only if row['active'] and not row['deleted_at'])
            client_hidden = '<input type="hidden" name="client_id" value="' + esc(client_filter) + '">' if client_filter.isdigit() else ''
            filters = '<form method="get" action="/admin/casos" class="admin-filters">' + client_hidden + '<label>Buscar caso<input type="search" name="q" value="' + esc(term) + '" placeholder="Cliente, título ou número"></label><label>Situação<select name="status">' + status_filter + '</select></label><label>Responsável<select name="responsavel">' + owner_filter + '</select></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/casos">Limpar</a></form>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Casos</h1><p class="muted">Consulte os atendimentos do escritório. As alterações seguem as permissões de cada responsável.</p>' + create_html + filters + '<h2>Casos do escritório <small class="result-count">' + str(total) + '</small></h2>' + (''.join(blocks) or '<p>Nenhum caso encontrado.</p>') + pagination + '</section>'
            return self.page('Casos', content, user)
        if path == '/admin/arquivos':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            admin = user['role'] == 'admin'
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            client_filter = query.get('client_id', [''])[0]
            direction_filter = query.get('direction', [''])[0]
            case_filter = query.get('case_id', [''])[0]
            document_status = query.get('status', [''])[0]
            term = query.get('q', [''])[0].strip()[:150]
            only_manageable = query.get('acao', [''])[0] == 'meus' and not admin
            with db() as c:
                if not has_permission(c, user, 'manage_documents'):
                    return self.forbidden()
                clients = self.scoped_clients(c, user)
                visible_clients = c.execute("SELECT id,name FROM users WHERE role='client' AND deleted_at='' ORDER BY name").fetchall()
                editable_cases = {row['id'] for row in self.scoped_cases(c, user)}
                editable_clients = {row['id'] for row in clients}
                cases = self.visible_cases(c, user)
                conditions = ["d.deleted_at=''", "u.deleted_at=''", "(d.case_id IS NULL OR ca.deleted_at='')"]
                params = []
                if not admin:
                    conditions.append("(d.case_id IN (SELECT id FROM cases WHERE deleted_at='') OR (" + self.scoped_condition('d') + '))')
                    params.extend([user['id'], user['id'], user['id']])
                if client_filter.isdigit():
                    conditions.append('d.client_id=?')
                    params.append(int(client_filter))
                if direction_filter in ('cliente', 'escritório'):
                    conditions.append('d.source=?')
                    params.append(direction_filter)
                if case_filter.isdigit():
                    conditions.append('d.case_id=?')
                    params.append(int(case_filter))
                if document_status in DOCUMENT_STATUS_LABELS:
                    conditions.append('d.status=?')
                    params.append(document_status)
                if term:
                    conditions.append('(d.filename LIKE ? OR u.name LIKE ?)')
                    params.extend(['%' + term + '%', '%' + term + '%'])
                where = ' AND '.join(conditions) if conditions else '1=1'
                rows = c.execute('SELECT d.*, u.name AS client, cu.name AS uploader, ca.title AS case_title FROM documents d JOIN users u ON u.id=d.client_id LEFT JOIN users cu ON cu.id=d.uploaded_by LEFT JOIN cases ca ON ca.id=d.case_id WHERE ' + where + ' ORDER BY d.id DESC', tuple(params)).fetchall()
            if only_manageable:
                rows = [row for row in rows if (row['case_id'] in editable_cases if row['case_id'] else row['client_id'] in editable_clients)]
            rows, pagination, total = self.paginate_rows(rows)
            client_options = '<option value="">Todos os clientes</option>' + ''.join(f'<option value="{x["id"]}"' + (' selected' if client_filter == str(x['id']) else '') + f'>{esc(x["name"])}</option>' for x in visible_clients)
            case_options = '<option value="">Todos os casos</option>' + ''.join(f'<option value="{x["id"]}"' + (' selected' if case_filter == str(x['id']) else '') + f'>#{x["id"]} — {esc(x["title"])} ({esc(x["client_name"])})</option>' for x in cases)
            direction_options = '<option value="">Todas as direções</option><option value="cliente"' + (' selected' if direction_filter == 'cliente' else '') + '>Recebidos do cliente</option><option value="escritório"' + (' selected' if direction_filter == 'escritório' else '') + '>Enviados pelo escritório</option>'
            status_options = '<option value="">Todas</option>' + ''.join('<option value="' + esc(key) + '"' + (' selected' if document_status == key else '') + '>' + esc(label) + '</option>' for key, label in DOCUMENT_STATUS_LABELS.items())
            filters = '<form method="get" action="/admin/arquivos" class="admin-filters">' + ('<input type="hidden" name="acao" value="meus">' if only_manageable else '') + '<label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Arquivo ou cliente"></label><label>Cliente<select name="client_id">' + client_options + '</select></label><label>Tipo<select name="direction">' + direction_options + '</select></label><label>Caso<select name="case_id">' + case_options + '</select></label><label>Situação<select name="status">' + status_options + '</select></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/arquivos">Limpar</a></form>'
            upload_cases = [row for row in cases if row['id'] in editable_cases]
            valid_client = client_filter if any(str(row['id']) == client_filter for row in clients) else ''
            valid_case = case_filter if any(str(row['id']) == case_filter and str(row['client_id']) == valid_client for row in upload_cases) else ''
            context = admin_context_hidden(clients, upload_cases, valid_client, valid_case)
            upload_form = form('/admin/document', context + admin_client_select(clients, valid_client) + admin_case_select(upload_cases, valid_case) + field('Arquivo', 'file', 'file'), 'Enviar arquivo', 'multipart/form-data') if clients else '<p class="muted">Nenhum cliente atribuído.</p>'
            rows_html = ''.join('<tr><td>' + esc(x['created']) + '</td><td>' + esc(x['client']) + '</td><td>' + esc(x['case_title'] or 'Caso geral') + '</td><td><a href="/arquivo/' + str(x['id']) + '">' + esc(x['filename']) + '</a>' + (' <small><a class="text-link" href="/admin/documento?doc_id=' + str(x['id']) + '">Analisar</a></small>' if admin or (x['case_id'] in editable_cases if x['case_id'] else x['client_id'] in editable_clients) else '') + ('<details class="admin-secondary"><summary>Mais ações</summary>' + form('/admin/delete', '<input type="hidden" name="entity" value="document"><input type="hidden" name="record_id" value="' + str(x['id']) + '">', 'Mover para lixeira') + '</details>' if is_super(user) else '') + '</td><td>' + ('Recebido do cliente' if x['source'] == 'cliente' else 'Enviado pelo escritório') + '</td><td>' + esc(x['uploader'] or x['source']) + '</td><td>' + document_badge(x['status']) + '</td></tr>' for x in rows) or '<tr><td colspan="7">Nenhum arquivo encontrado.</td></tr>'
            upload_section = '<details class="conversation-new"' + (' open' if query.get('novo') else '') + '><summary>Disponibilizar documento</summary>' + upload_form + '</details>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Central de arquivos</h1><p class="muted">Controle dos arquivos recebidos e enviados, por cliente e por caso.</p>' + upload_section + filters + ('<p class="muted">Exibindo apenas documentos que você pode analisar.</p>' if only_manageable else '') + '<p class="muted">' + str(total) + ' documento(s) encontrado(s).</p><div class="table-wrap"><table class="table"><thead><tr><th>Data</th><th>Cliente</th><th>Caso</th><th>Arquivo</th><th>Direção</th><th>Enviado por</th><th>Revisão</th></tr></thead><tbody>' + rows_html + '</tbody></table></div>' + pagination + '</section>'
            return self.page('Central de arquivos', content, user)
        if path == '/admin/mensagens':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            selected_client = query.get('client_id', [''])[0]
            selected_case = query.get('case_id', [''])[0]
            term = query.get('q', [''])[0].strip()[:150]
            category = query.get('tipo', [''])[0]
            unread_only = query.get('filtro', [''])[0] == 'nao_lidas'
            view = query.get('status', ['abertas'])[0]
            with db() as c:
                if not has_permission(c, user, 'send_messages'):
                    return self.forbidden()
                clients = self.scoped_clients(c, user)
                cases = self.scoped_cases(c, user)
                conversations = conversation_rows(c, user)
            if selected_client.isdigit():
                conversations = [row for row in conversations if row['client_id'] == int(selected_client)]
            if selected_case.isdigit():
                conversations = [row for row in conversations if row['case_id'] == int(selected_case)]
            if category in ('cliente', 'interno'):
                conversations = [row for row in conversations if row['visibility'] == ('client' if category == 'cliente' else 'internal')]
            if unread_only:
                conversations = [row for row in conversations if row['unread']]
            if term:
                needle = term.casefold()
                conversations = [row for row in conversations if needle in ' '.join(str(row[key] or '') for key in ('title', 'client_name', 'case_title', 'last_body')).casefold()]
            if view == 'historico':
                conversations = [row for row in conversations if row['status'] in ('closed', 'legacy')]
            elif view != 'todas':
                conversations = [row for row in conversations if row['status'] == 'open']
                view = 'abertas'
            conversations, pagination, total = self.paginate_rows(conversations)
            valid_client = selected_client if any(str(row['id']) == selected_client for row in clients) else ''
            valid_case = selected_case if any(str(row['id']) == selected_case and str(row['client_id']) == valid_client for row in cases) else ''
            select = admin_client_select(clients, valid_client) if clients else ''
            case_select = admin_case_select(cases, valid_case)
            context = admin_context_hidden(clients, cases, valid_client, valid_case)
            compose_client = form('/admin/mensagem', context + select + case_select + field('Assunto', 'subject') + '<label>Mensagem ao cliente<textarea name="body" required></textarea></label><label class="check"><input type="checkbox" name="reveal_identity" value="1"> Mostrar meu nome ao cliente</label>', 'Iniciar conversa') if clients else '<p class="muted">Nenhum cliente atribuído para envio.</p>'
            compose_internal = form('/admin/mensagem', context + select + case_select + field('Assunto', 'subject') + '<input type="hidden" name="visibility" value="internal"><label>Relato interno<textarea name="body" required></textarea></label>', 'Iniciar relato interno') if clients else ''
            view_options = ''.join('<option value="' + value + '"' + (' selected' if view == value else '') + '>' + label + '</option>' for value, label in (('abertas', 'Em andamento'), ('historico', 'Encerradas e histórico'), ('todas', 'Todas')))
            type_options = ''.join('<option value="' + value + '"' + (' selected' if category == value else '') + '>' + label + '</option>' for value, label in (('', 'Todos'), ('cliente', 'Com cliente'), ('interno', 'Relatos internos')))
            filters = '<form method="get" action="/admin/mensagens" class="admin-filters"><label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Cliente, caso ou assunto"></label><label>Situação<select name="status">' + view_options + '</select></label><label>Tipo<select name="tipo">' + type_options + '</select></label><label class="check"><input type="checkbox" name="filtro" value="nao_lidas"' + (' checked' if unread_only else '') + '> Apenas não lidas</label>' + ('<input type="hidden" name="client_id" value="' + esc(selected_client) + '">' if selected_client.isdigit() else '') + ('<input type="hidden" name="case_id" value="' + esc(selected_case) + '">' if selected_case.isdigit() else '') + '<button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/mensagens">Limpar</a></form>'
            selected_conversation = query.get('conversa', [''])[0]
            selected_id = int(selected_conversation) if selected_conversation.isdigit() else (conversations[0]['id'] if conversations else 0)
            pane_html = ''
            if selected_id:
                with db() as c:
                    pane_html = self.conversation_view_html(c, user, selected_id) or ''
            pane_html = pane_html or '<div class="conversation-empty"><p class="eyebrow">CONVERSAS</p><h2>Selecione um assunto</h2><p>Escolha uma conversa à esquerda para consultar o histórico e responder.</p></div>'
            inbox_html = conversation_cards(conversations, user, '/admin/mensagens?conversa=', dialog=False)
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<p class="eyebrow">CAIXA DE ENTRADA</p><h1>Conversas e relatos</h1><p class="muted">Abra um assunto para consultar ou responder. Relatos internos não são visíveis ao cliente.</p><details class="conversation-new"' + (' open' if query.get('novo') else '') + '><summary>Iniciar conversa ou relato</summary>' + card('Enviar mensagem ao cliente', compose_client) + card('Relatos internos', compose_internal) + '</details>' + filters + '<div class="conversation-workspace"><aside class="conversation-inbox"><div class="conversation-inbox-head"><h2>Conversas <small class="result-count">' + str(total) + '</small></h2></div><div class="conversation-list">' + inbox_html + '</div>' + pagination + '</aside><section class="conversation-pane">' + pane_html + '</section></div></section>'
            return self.page('Mensagens e relatos', content, user)
        if path == '/admin/documento':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                document_id = int(query.get('doc_id', ['0'])[0])
            except (TypeError, ValueError):
                document_id = 0
            with db() as c:
                if not has_permission(c, user, 'manage_documents'):
                    return self.forbidden()
                document = c.execute("SELECT d.*, u.name AS client, cu.name AS uploader, ru.name AS reviewer, ca.title AS case_title FROM documents d JOIN users u ON u.id=d.client_id LEFT JOIN users cu ON cu.id=d.uploaded_by LEFT JOIN users ru ON ru.id=d.reviewed_by LEFT JOIN cases ca ON ca.id=d.case_id WHERE d.id=? AND d.deleted_at=''", (document_id,)).fetchone()
                if not document:
                    return self.forbidden()
                allowed = self.can_access_case(c, user, document['case_id']) if document['case_id'] else self.can_manage(c, user, document['client_id'])
                if not allowed:
                    return self.forbidden()
            status_options = ''.join('<option value="' + key + '"' + (' selected' if document['status'] == key else '') + '>' + label + '</option>' for key, label in DOCUMENT_STATUS_LABELS.items())
            context = ''
            if query.get('retorno', [''])[0] == '1':
                context = '<input type="hidden" name="client_id" value="' + str(document['client_id']) + '">' + ('<input type="hidden" name="case_id" value="' + str(document['case_id']) + '">' if document['case_id'] else '') + '<input type="hidden" name="return_to" value="' + esc(admin_context_return(document['client_id'], document['case_id'])) + '">'
            status_form = form('/admin/documento/status', context + '<input type="hidden" name="doc_id" value="' + str(document_id) + '"><label>Status<select name="status">' + status_options + '</select></label><label>Análise do escritório<textarea name="analysis_notes">' + esc(document['analysis_notes']) + '</textarea></label>', 'Salvar análise')
            details = '<p><strong>Cliente:</strong> ' + esc(document['client']) + '</p><p><strong>Caso:</strong> ' + esc(document['case_title'] or 'Caso geral') + '</p><p><strong>Arquivo:</strong> <a class="text-link" href="/arquivo/' + str(document_id) + '">' + esc(document['filename']) + '</a></p><p><strong>Origem:</strong> ' + esc(document['source']) + ' · <strong>Enviado por:</strong> ' + esc(document['uploader'] or document['source']) + '</p><p><strong>Status:</strong> ' + document_badge(document['status']) + '</p><p><strong>Recebido em:</strong> ' + esc(document['created']) + ' · <strong>Analisado por:</strong> ' + esc(document['reviewer'] or '—') + ((' · ' + esc(document['reviewed_at'])) if document['reviewed_at'] else '') + '</p>'
            content = '<section class="wrap section">' + self.admin_nav(user) + '<h1>Análise de documento</h1>' + card('Documento', details) + card('Análise', status_form) + '<p><a class="text-link" href="/admin/arquivos">Voltar aos documentos</a></p></section>'
            return self.page('Análise de documento', content, user)
        if path == '/admin/pendencias':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            selected_client = query.get('client_id', [''])[0]
            selected_case = query.get('case_id', [''])[0]
            status_filter = query.get('status', ['ativas'])[0]
            pendency_filter = query.get('id', [''])[0]
            term = query.get('q', [''])[0].strip()[:150]
            with db() as c:
                if not has_permission(c, user, 'manage_cases'):
                    return self.forbidden()
                clients = self.scoped_clients(c, user)
                cases = self.scoped_cases(c, user)
                if user['role'] == 'admin':
                    pendencies = c.execute("SELECT p.*, u.name AS client, ca.title AS case_title, d.filename AS document_name, ru.name AS reviewer FROM pendencies p JOIN users u ON u.id=p.client_id LEFT JOIN cases ca ON ca.id=p.case_id LEFT JOIN documents d ON d.id=p.document_id LEFT JOIN users ru ON ru.id=p.reviewed_by WHERE u.deleted_at='' AND (p.case_id IS NULL OR ca.deleted_at='') ORDER BY p.id DESC").fetchall()
                else:
                    pendencies = c.execute("SELECT p.*, u.name AS client, ca.title AS case_title, d.filename AS document_name, ru.name AS reviewer FROM pendencies p JOIN users u ON u.id=p.client_id LEFT JOIN cases ca ON ca.id=p.case_id LEFT JOIN documents d ON d.id=p.document_id LEFT JOIN users ru ON ru.id=p.reviewed_by WHERE u.deleted_at='' AND (p.case_id IS NULL OR ca.deleted_at='') AND (" + self.scoped_condition('p') + ") ORDER BY p.id DESC", (user['id'], user['id'], user['id'])).fetchall()
            statuses = ('Aberta', 'Recebida', 'Em análise', 'Atendida')
            if pendency_filter.isdigit():
                pendencies = [row for row in pendencies if row['id'] == int(pendency_filter)]
            if status_filter == 'ativas':
                pendencies = [row for row in pendencies if row['status'] != 'Atendida']
            elif status_filter in statuses:
                pendencies = [row for row in pendencies if row['status'] == status_filter]
            if selected_client.isdigit():
                pendencies = [row for row in pendencies if row['client_id'] == int(selected_client)]
            if selected_case.isdigit():
                pendencies = [row for row in pendencies if row['case_id'] == int(selected_case)]
            if term:
                needle = term.casefold()
                pendencies = [row for row in pendencies if needle in ' '.join(str(row[key] or '') for key in ('title', 'client', 'case_title')).casefold()]
            pendencies, pagination, total = self.paginate_rows(pendencies)
            valid_client = selected_client if any(str(row['id']) == selected_client for row in clients) else ''
            valid_case = selected_case if any(str(row['id']) == selected_case and str(row['client_id']) == valid_client for row in cases) else ''
            create_form = form('/admin/pendencia', admin_context_hidden(clients, cases, valid_client, valid_case) + admin_client_select(clients, valid_client) + admin_case_select(cases, valid_case) + field('Título', 'title') + '<label>Descrição<textarea name="description"></textarea></label>' + field('Prazo', 'due_at', 'date', required=False), 'Criar pendência') if clients else '<p class="muted">Nenhum cliente atribuído.</p>'
            items = []
            for pendency in pendencies:
                status_options = ''.join('<option' + (' selected' if pendency['status'] == status else '') + '>' + status + '</option>' for status in statuses)
                status_form = form('/admin/pendencia/status', '<input type="hidden" name="pendency_id" value="' + str(pendency['id']) + '"><label>Status<select name="status">' + status_options + '</select></label><label>Análise do escritório<textarea name="review_notes">' + esc(pendency['review_notes']) + '</textarea></label>', 'Salvar análise')
                document_link = (' · <a class="text-link" href="/arquivo/' + str(pendency['document_id']) + '">' + esc(pendency['document_name'] or 'documento') + '</a>') if pendency['document_id'] else ''
                items.append('<div class="case-box status-border-' + pendency_color(pendency['status']) + '"><strong>' + esc(pendency['client']) + ' — ' + esc(pendency['title']) + '</strong><p>' + esc(pendency['description']) + '</p><p>' + pendency_badge(pendency['status']) + ((' · caso: ' + esc(pendency['case_title'])) if pendency['case_title'] else '') + ((' · prazo: ' + esc(pendency['due_at'])) if pendency['due_at'] else '') + document_link + '</p><details class="admin-secondary"><summary>Analisar pendência</summary>' + status_form + '</details></div>')
            status_options = ''.join('<option value="' + esc(value) + '"' + (' selected' if status_filter == value else '') + '>' + esc(label) + '</option>' for value, label in [('ativas', 'Ativas'), ('todas', 'Todas')] + [(item, item) for item in statuses])
            hidden = ('<input type="hidden" name="client_id" value="' + esc(selected_client) + '">' if selected_client.isdigit() else '') + ('<input type="hidden" name="case_id" value="' + esc(selected_case) + '">' if selected_case.isdigit() else '')
            filters = '<form method="get" action="/admin/pendencias" class="admin-filters">' + hidden + '<label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Cliente, caso ou título"></label><label>Situação<select name="status">' + status_options + '</select></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/pendencias">Limpar</a></form>'
            create = '<details class="conversation-new"' + (' open' if query.get('novo') else '') + '><summary>Nova pendência</summary>' + create_form + '</details>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Pendências</h1><p class="muted">Acompanhe solicitações de documentos ou informações.</p>' + create + filters + '<h2>Pendências <small class="result-count">' + str(total) + '</small></h2>' + (''.join(items) or '<p>Nenhuma pendência encontrada.</p>') + pagination + '</section>'
            return self.page('Pendências', content, user)
        if path == '/admin/tarefa/nova':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                message_id = int(query.get('message_id', ['0'])[0])
            except (TypeError, ValueError):
                message_id = 0
            with db() as c:
                message = c.execute("SELECT m.*,cv.visibility,cv.case_id FROM messages m JOIN conversations cv ON cv.id=m.conversation_id WHERE m.id=?", (message_id,)).fetchone()
                if not message or message['visibility'] != 'internal' or not has_permission(c, user, 'manage_cases'):
                    return self.forbidden()
                if message['case_id'] and not self.can_access_case(c, user, message['case_id']):
                    return self.forbidden()
                if not self.can_manage(c, user, message['client_id']):
                    return self.forbidden()
                case_row = c.execute('SELECT * FROM cases WHERE id=? AND deleted_at=\'\'', (message['case_id'],)).fetchone() if message['case_id'] else None
                staff = c.execute("SELECT id,name FROM users WHERE role IN ('staff','admin') AND active=1 AND deleted_at='' ORDER BY name").fetchall()
                collaborators = c.execute('SELECT user_id FROM task_collaborators WHERE task_id=?', (0,)).fetchall() if False else []
            prefill = '<input type="hidden" name="source_message_id" value="' + str(message_id) + '"><input type="hidden" name="client_id" value="' + str(message['client_id']) + '"><input type="hidden" name="case_id" value="' + str(message['case_id'] or '') + '"><input type="hidden" name="assigned_to" value="' + str(user['id']) + '">'
            assign_options = '<option value="">Atribuir a mim</option>' + ''.join('<option value="' + str(row['id']) + '">' + esc(row['name']) + '</option>' for row in staff if user['role'] != 'staff' or row['id'] == user['id'])
            task_form = form('/admin/tarefa', prefill + input_field('Título', 'title', message['body'][:120]) + '<label>Descrição<textarea name="description" rows="4">' + esc(message['body']) + '</textarea></label>' + field('Prazo', 'due_at', 'datetime-local', required=False) + '<label>Responsável<select name="assigned_to">' + assign_options + '</select></label><label>Prioridade<select name="priority"><option value="normal">Normal</option><option value="alta">Alta</option><option value="urgente">Urgente</option></select></label>', 'Criar tarefa vinculada')
            case_label = esc(case_row['title']) if case_row else 'Sem caso vinculado'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<a class="text-link" href="/conversas/' + str(message['conversation_id']) + '">← Voltar à conversa</a><p class="eyebrow">NOVA TAREFA</p><h1>Transformar mensagem em tarefa</h1><p class="muted">Caso: ' + case_label + '</p>' + card('Mensagem de origem', '<p>' + highlight_mentions(message['body']) + '</p>') + card('Tarefa', task_form) + '</section>'
            return self.page('Nova tarefa', content, user)
        if path == '/admin/tarefa':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                task_id = int(query.get('task_id', ['0'])[0])
            except (TypeError, ValueError):
                task_id = 0
            with db() as c:
                tasks = self.task_rows(c, user)
                task = next((row for row in tasks if row['id'] == task_id), None)
                if not task:
                    return self.forbidden()
                if user['role'] != 'admin' and task['assigned_to'] != user['id'] and task['created_by'] != user['id']:
                    return self.forbidden()
                clients = self.scoped_clients(c, user)
                cases = self.scoped_cases(c, user)
                staff = c.execute("SELECT id,name FROM users WHERE role IN ('staff','admin') AND active=1 AND deleted_at='' ORDER BY name").fetchall()
                collaborators = {row['user_id'] for row in c.execute('SELECT user_id FROM task_collaborators WHERE task_id=?', (task_id,)).fetchall()}
                collaborators_names = [row['name'] for row in c.execute('SELECT u.name FROM task_collaborators tc JOIN users u ON u.id=tc.user_id WHERE tc.task_id=? ORDER BY u.name', (task_id,)).fetchall()]
                subtasks = c.execute('SELECT * FROM task_subtasks WHERE task_id=? ORDER BY id', (task_id,)).fetchall()
                all_documents = c.execute("SELECT id,filename,client_id,case_id FROM documents WHERE deleted_at='' ORDER BY id DESC LIMIT 300").fetchall()
                documents = [row for row in all_documents if (self.can_access_case(c, user, row['case_id']) if row['case_id'] else self.can_manage(c, user, row['client_id']))]
                history = c.execute("SELECT a.*,u.name AS actor FROM audit a LEFT JOIN users u ON u.id=a.user_id WHERE a.entity='task' AND a.entity_id=? ORDER BY a.id DESC LIMIT 20", (task_id,)).fetchall()
            client_options = '<option value="">Sem cliente</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if task['client_id'] == row['id'] else '') + '>' + esc(row['name']) + '</option>' for row in clients)
            case_options = '<option value="">Sem caso específico</option>' + ''.join('<option value="' + str(row['id']) + '" data-client-id="' + str(row['client_id']) + '"' + (' selected' if task['case_id'] == row['id'] else '') + '>#' + str(row['id']) + ' — ' + esc(row['title']) + '</option>' for row in cases)
            assign_options = '<option value="">Atribuir a mim</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if task['assigned_to'] == row['id'] else '') + '>' + esc(row['name']) + '</option>' for row in staff if user['role'] != 'staff' or row['id'] == user['id'])
            priority_options = ''.join('<option value="' + value + '"' + (' selected' if task['priority'] == value else '') + '>' + label + '</option>' for value, label in TASK_PRIORITY_LABELS.items())
            status_options = ''.join('<option value="' + value + '"' + (' selected' if task['status'] == value else '') + '>' + label + '</option>' for value, label in TASK_STATUS_LABELS.items())
            due_value = str(task['due_at']).replace(' ', 'T')[:16] if task['due_at'] else ''
            collaborator_options = ''.join('<label class="check"><input type="checkbox" name="collaborator_' + str(row['id']) + '" value="1"' + (' checked' if row['id'] in collaborators else '') + '> ' + esc(row['name']) + '</label>' for row in staff)
            document_options = '<option value="">Sem documento vinculado</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if task['document_id'] == row['id'] else '') + '>' + esc(row['filename']) + '</option>' for row in documents)
            edit_form = form('/admin/tarefa/editar', '<input type="hidden" name="task_id" value="' + str(task_id) + '">' + input_field('Título', 'title', task['title']) + '<label>Descrição<textarea name="description" rows="4">' + esc(task['description']) + '</textarea></label>' + '<label>Cliente<select name="client_id" data-context-client>' + client_options + '</select></label><label>Caso<select name="case_id" data-context-case>' + case_options + '</select></label><label>Responsável<select name="assigned_to">' + assign_options + '</select></label><fieldset class="check-group"><legend>Colaboradores</legend>' + collaborator_options + '</fieldset><label>Documento vinculado (opcional)<select name="document_id">' + document_options + '</select></label><label>Prazo<input type="datetime-local" name="due_at" value="' + esc(due_value) + '"></label><label>Prioridade<select name="priority">' + priority_options + '</select></label><label>Situação<select name="status">' + status_options + '</select></label>', 'Salvar alterações')
            history_html = ''.join('<li><strong>' + esc(item['created']) + ' — ' + esc(item['action']) + '</strong><br><small>' + esc(item['actor'] or 'Sistema') + ' · ' + esc(item['detail']) + '</small></li>' for item in history) or '<li>Nenhuma alteração registrada.</li>'
            delete_form = form('/admin/tarefa/excluir', '<input type="hidden" name="task_id" value="' + str(task_id) + '">', 'Excluir tarefa')
            subtask_items = ''.join('<li><form method="post" action="/admin/tarefa/subtarefa" class="inline-form"><input type="hidden" name="csrf" value="' + CSRF_PLACEHOLDER + '"><input type="hidden" name="task_id" value="' + str(task_id) + '"><input type="hidden" name="subtask_id" value="' + str(item['id']) + '"><input type="hidden" name="operation" value="toggle"><button class="text-link" type="submit">' + ('✓ ' if item['completed'] else '○ ') + esc(item['title']) + '</button></form> <form method="post" action="/admin/tarefa/subtarefa" class="inline-form"><input type="hidden" name="csrf" value="' + CSRF_PLACEHOLDER + '"><input type="hidden" name="task_id" value="' + str(task_id) + '"><input type="hidden" name="subtask_id" value="' + str(item['id']) + '"><input type="hidden" name="operation" value="delete"><button class="text-link" type="submit" aria-label="Excluir subtarefa">×</button></form></li>' for item in subtasks) or '<li>Nenhuma subtarefa.</li>'
            subtask_form = form('/admin/tarefa/subtarefa', '<input type="hidden" name="task_id" value="' + str(task_id) + '"><input type="hidden" name="operation" value="add">' + field('Nova subtarefa', 'title'), 'Adicionar subtarefa')
            collaborator_html = ', '.join(esc(name) for name in collaborators_names) or 'Nenhum colaborador.'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<a class="text-link" href="/admin/tarefas">← Tarefas</a><p class="eyebrow">TAREFA</p><h1>' + esc(task['title']) + '</h1><div class="panel-kpis"><span class="panel-kpi tone-' + ('red' if task_is_overdue(task) else 'yellow') + '"><span class="panel-kpi-value">' + ('Atrasada' if task_is_overdue(task) else TASK_STATUS_LABELS.get(task['status'], task['status'])) + '</span><span class="panel-kpi-label">Situação</span></span><span class="panel-kpi tone-lavender"><span class="panel-kpi-value">' + TASK_PRIORITY_LABELS.get(task['priority'], task['priority']) + '</span><span class="panel-kpi-label">Prioridade</span></span></div><div class="panel-dash-grid"><div class="panel-col">' + panel_card('Editar tarefa', edit_form) + panel_card('Subtarefas', '<ul class="subtask-list">' + subtask_items + '</ul>' + subtask_form) + '</div><div class="panel-col">' + panel_card('Colaboradores', '<p>' + collaborator_html + '</p>') + panel_card('Histórico', '<ul class="panel-attention">' + history_html + '</ul>') + panel_card('Excluir', '<p class="muted">A tarefa deixa de aparecer nas listas e no painel.</p>' + delete_form) + '</div></div></section>'
            return self.page('Tarefa', content, user)
        if path == '/admin/tarefas':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            term = query.get('q', [''])[0].strip()[:150]
            state = query.get('status', ['abertas'])[0]
            client_filter = query.get('client_id', [''])[0]
            case_filter = query.get('case_id', [''])[0]
            responsible_filter = query.get('responsavel', [''])[0]
            with db() as c:
                if not has_permission(c, user, 'manage_cases'):
                    return self.forbidden()
                clients = self.scoped_clients(c, user)
                cases = self.scoped_cases(c, user)
                tasks = self.task_rows(c, user)
                staff = c.execute("SELECT id,name,active,deleted_at FROM users WHERE role IN ('staff','admin') AND active=1 AND deleted_at='' ORDER BY name").fetchall()
                all_documents = c.execute("SELECT id,filename,client_id,case_id FROM documents WHERE deleted_at='' ORDER BY id DESC LIMIT 300").fetchall()
                documents = [row for row in all_documents if (self.can_access_case(c, user, row['case_id']) if row['case_id'] else self.can_manage(c, user, row['client_id']))]
            if state == 'atrasadas':
                tasks = [task for task in tasks if task_is_overdue(task)]
            elif state in ('pendente', 'em_andamento', 'concluida'):
                tasks = [task for task in tasks if task['status'] == state and not (state != 'concluida' and task_is_overdue(task))]
            elif state == 'abertas':
                tasks = [task for task in tasks if task['status'] != 'concluida']
            if client_filter.isdigit():
                tasks = [task for task in tasks if task['client_id'] == int(client_filter)]
            if case_filter.isdigit():
                tasks = [task for task in tasks if task['case_id'] == int(case_filter)]
            if responsible_filter.isdigit():
                tasks = [task for task in tasks if task['assigned_to'] == int(responsible_filter)]
            if term:
                needle = term.casefold()
                tasks = [task for task in tasks if needle in ' '.join(str(task[key] or '') for key in ('title', 'description', 'client_name', 'case_title', 'responsible_name')).casefold()]
            tasks, pagination, total = self.paginate_rows(tasks)
            valid_client = client_filter if any(str(row['id']) == client_filter for row in clients) else ''
            valid_case = case_filter if any(str(row['id']) == case_filter and str(row['client_id']) == valid_client for row in cases) else ''
            client_options = '<option value="">Sem cliente</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if str(row['id']) == valid_client else '') + '>' + esc(row['name']) + '</option>' for row in clients)
            client_select = '<label>Cliente (opcional)<select name="client_id" data-context-client>' + client_options + '</select></label>'
            case_select = admin_case_select(cases, valid_case)
            assign_options = '<option value="">Atribuir a mim</option>' + ''.join('<option value="' + str(row['id']) + '">' + esc(row['name']) + '</option>' for row in staff if user['role'] != 'staff' or row['id'] == user['id'])
            assign_select = '<label>Responsável<select name="assigned_to">' + assign_options + '</select></label>'
            priority_options = ''.join('<option value="' + value + '">' + label + '</option>' for value, label in (('normal', 'Normal'), ('alta', 'Alta'), ('urgente', 'Urgente')))
            collaborator_options = ''.join('<label class="check"><input type="checkbox" name="collaborator_' + str(row['id']) + '" value="1"> ' + esc(row['name']) + '</label>' for row in staff)
            document_options = '<option value="">Sem documento vinculado</option>' + ''.join('<option value="' + str(row['id']) + '">' + esc(row['filename']) + '</option>' for row in documents)
            create_form = form('/admin/tarefa', field('Título', 'title') + '<label>Descrição<textarea name="description" rows="3"></textarea></label>' + field('Prazo', 'due_at', 'datetime-local', required=False) + '<label>Prioridade<select name="priority">' + priority_options + '</select></label>' + client_select + case_select + assign_select + '<fieldset class="check-group"><legend>Colaboradores</legend>' + collaborator_options + '</fieldset><label>Documento vinculado (opcional)<select name="document_id">' + document_options + '</select></label>', 'Criar tarefa')
            status_options = ''.join('<option value="' + value + '"' + (' selected' if state == value else '') + '>' + label + '</option>' for value, label in (('abertas', 'Em aberto'), ('atrasadas', 'Atrasadas'), ('pendente', 'Pendentes'), ('em_andamento', 'Em andamento'), ('concluida', 'Concluídas'), ('todas', 'Todas')))
            responsible_options = '<option value="">Todos</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if responsible_filter == str(row['id']) else '') + '>' + esc(row['name']) + '</option>' for row in staff)
            filters = '<form method="get" action="/admin/tarefas" class="admin-filters"><label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Tarefa, cliente ou caso"></label><label>Situação<select name="status">' + status_options + '</select></label><label>Responsável<select name="responsavel">' + responsible_options + '</select></label>' + ('<input type="hidden" name="client_id" value="' + esc(valid_client) + '">' if valid_client else '') + ('<input type="hidden" name="case_id" value="' + esc(valid_case) + '">' if valid_case else '') + '<button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/tarefas">Limpar</a></form>'
            task_items = []
            for task in tasks:
                can_update = user['role'] == 'admin' or task['assigned_to'] == user['id'] or task['created_by'] == user['id']
                status_form = form('/admin/tarefa/status', '<input type="hidden" name="task_id" value="' + str(task['id']) + '"><label>Atualizar<select name="status">' + ''.join('<option value="' + value + '"' + (' selected' if task['status'] == value else '') + '>' + label + '</option>' for value, label in TASK_STATUS_LABELS.items()) + '</select></label>', 'Salvar') if can_update else ''
                context = ' · '.join(item for item in (task['client_name'], task['case_title'], task['responsible_name']) if item)
                task_items.append('<div class="task-item status-border-' + ('red' if task_is_overdue(task) else {'pendente': 'yellow', 'em_andamento': 'blue', 'concluida': 'green'}.get(task['status'], 'gray')) + '"><div><div class="task-item-head"><strong>' + esc(task['title']) + '</strong>' + task_status_badge(task) + task_priority_badge(task['priority']) + '</div><p>' + esc(task['description']) + '</p><p class="task-meta">' + esc(context or 'Sem vínculo') + ((' · prazo ' + esc(fmt_when(task['due_at']))) if task['due_at'] else '') + '</p></div><div class="task-actions">' + status_form + '<a class="text-link" href="/admin/tarefa?task_id=' + str(task['id']) + '">Editar</a></div></div>')
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<p class="eyebrow">PRAZOS E TAREFAS</p><h1>Tarefas</h1><p class="muted">Organize prazos internos, atribuições e providências do escritório. Tarefas atrasadas aparecem em vermelho.</p><details class="conversation-new"' + (' open' if query.get('novo') else '') + '><summary>Nova tarefa</summary>' + create_form + '</details>' + filters + '<h2>Tarefas <small class="result-count">' + str(total) + '</small></h2><div class="task-list">' + (''.join(task_items) or '<p class="muted">Nenhuma tarefa encontrada.</p>') + '</div>' + pagination + '</section>'
            return self.page('Tarefas', content, user)
        if path == '/admin/documento-interno':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                document_id = int(query.get('doc_id', ['0'])[0])
            except (TypeError, ValueError):
                document_id = 0
            with db() as c:
                document = c.execute("SELECT d.*,u.name AS client_name,ca.title AS case_title,ru.name AS uploader FROM internal_documents d LEFT JOIN users u ON u.id=d.client_id LEFT JOIN cases ca ON ca.id=d.case_id LEFT JOIN users ru ON ru.id=d.uploaded_by WHERE d.id=? AND d.deleted_at=''", (document_id,)).fetchone()
                if not document or not self.can_view_internal_document(c, user, document):
                    return self.forbidden()
                can_edit = user['role'] == 'admin' or document['uploaded_by'] == user['id']
                clients = self.scoped_clients(c, user)
                cases = self.scoped_cases(c, user)
                history = c.execute("SELECT a.*,u.name AS actor FROM audit a LEFT JOIN users u ON u.id=a.user_id WHERE a.entity='internal_document' AND a.entity_id=? ORDER BY a.id DESC LIMIT 20", (document_id,)).fetchall()
            client_options = '<option value="">Sem cliente</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if document['client_id'] == row['id'] else '') + '>' + esc(row['name']) + '</option>' for row in clients)
            case_options = '<option value="">Sem caso específico</option>' + ''.join('<option value="' + str(row['id']) + '" data-client-id="' + str(row['client_id']) + '"' + (' selected' if document['case_id'] == row['id'] else '') + '>#' + str(row['id']) + ' — ' + esc(row['title']) + '</option>' for row in cases)
            visibility_options = ''.join('<option value="' + value + '"' + (' selected' if document['visibility'] == value else '') + '>' + label + '</option>' for value, label in (('equipe', 'Toda a equipe'), ('caso', 'Somente equipe do caso')))
            edit_form = form('/admin/documento-interno/editar', '<input type="hidden" name="doc_id" value="' + str(document_id) + '">' + input_field('Título', 'title', document['title']) + input_field('Categoria', 'category', document['category'], required=False) + '<label>Cliente<select name="client_id" data-context-client>' + client_options + '</select></label><label>Caso<select name="case_id" data-context-case>' + case_options + '</select></label><label>Visibilidade<select name="visibility">' + visibility_options + '</select></label>', 'Salvar alterações') if can_edit else '<p class="muted">Somente o autor ou um administrador pode editar este documento.</p>'
            history_html = ''.join('<li><strong>' + esc(item['created']) + ' — ' + esc(item['action']) + '</strong><br><small>' + esc(item['actor'] or 'Sistema') + ' · ' + esc(item['detail']) + '</small></li>' for item in history) or '<li>Nenhuma alteração registrada.</li>'
            delete_form = form('/admin/documento-interno/excluir', '<input type="hidden" name="doc_id" value="' + str(document_id) + '">', 'Remover documento') if can_edit else ''
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<a class="text-link" href="/admin/documentos-internos">← Documentos internos</a><p class="eyebrow">DOCUMENTO INTERNO</p><h1>' + esc(document['title']) + '</h1><p class="muted">' + esc(document['category'] or 'Documento interno') + ' · ' + esc(document['filename']) + ' · ' + esc(document['case_title'] or document['client_name'] or 'Uso interno') + ' · ' + ('Toda a equipe' if document['visibility'] == 'equipe' else 'Equipe do caso') + '</p><div class="quick-actions"><a class="btn" href="/interno/' + str(document_id) + '">Baixar arquivo</a></div><div class="panel-dash-grid"><div class="panel-col">' + panel_card('Editar informações', edit_form) + '</div><div class="panel-col">' + panel_card('Histórico', '<ul class="panel-attention">' + history_html + '</ul>') + (panel_card('Remover', '<p class="muted">O documento deixa de aparecer nas listas e não poderá mais ser baixado.</p>' + delete_form) if delete_form else '') + '</div></div></section>'
            return self.page('Documento interno', content, user)
        if path == '/admin/documentos-internos':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            term = query.get('q', [''])[0].strip()[:150]
            with db() as c:
                if not has_permission(c, user, 'manage_documents'):
                    return self.forbidden()
                clients = self.scoped_clients(c, user)
                cases = self.scoped_cases(c, user)
                all_documents = c.execute("SELECT d.*,u.name AS client_name,ca.title AS case_title,ru.name AS uploader FROM internal_documents d LEFT JOIN users u ON u.id=d.client_id LEFT JOIN cases ca ON ca.id=d.case_id LEFT JOIN users ru ON ru.id=d.uploaded_by WHERE d.deleted_at='' ORDER BY d.id DESC").fetchall()
                documents = [document for document in all_documents if self.can_view_internal_document(c, user, document)]
            if term:
                needle = term.casefold()
                documents = [document for document in documents if needle in ' '.join(str(document[key] or '') for key in ('title', 'category', 'filename', 'client_name', 'case_title')).casefold()]
            documents, pagination, total = self.paginate_rows(documents)
            client_options = '<option value="">Sem cliente</option>' + ''.join('<option value="' + str(row['id']) + '">' + esc(row['name']) + '</option>' for row in clients)
            client_select = '<label>Cliente (opcional)<select name="client_id" data-context-client>' + client_options + '</select></label>'
            case_select = admin_case_select(cases)
            visibility_options = '<option value="equipe">Toda a equipe</option><option value="caso">Somente equipe do caso</option>'
            upload_form = form('/admin/documento-interno', field('Título', 'title') + field('Categoria', 'category', required=False) + client_select + case_select + '<label>Visibilidade<select name="visibility">' + visibility_options + '</select></label>' + field('Arquivo', 'file', 'file'), 'Enviar documento interno', 'multipart/form-data')
            filters = '<form method="get" action="/admin/documentos-internos" class="admin-filters"><label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Título, categoria ou cliente"></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/documentos-internos">Limpar</a></form>'
            items = ''.join('<div class="internal-doc"><span class="internal-doc-icon">' + panel_icon('documents') + '</span><div><strong>' + esc(document['title']) + '</strong><p class="task-meta">' + esc(document['category'] or 'Documento interno') + ' · ' + esc(document['filename']) + '</p><p class="task-meta">' + esc(document['case_title'] or document['client_name'] or 'Uso interno') + ' · ' + ('Toda a equipe' if document['visibility'] == 'equipe' else 'Equipe do caso') + ' · enviado por ' + esc(document['uploader'] or '—') + ' em ' + esc(document['created']) + '</p></div><div class="internal-doc-actions"><a class="btn ghost" href="/interno/' + str(document['id']) + '">Baixar</a> <a class="text-link" href="/admin/documento-interno?doc_id=' + str(document['id']) + '">Editar</a></div></div>' for document in documents) or '<p class="muted">Nenhum documento interno encontrado.</p>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<p class="eyebrow">DOCUMENTOS INTERNOS</p><h1>Central de documentos internos</h1><p class="muted">Compartilhe pareceres, modelos e arquivos de apoio com a equipe. O cliente não acessa esta área.</p><details class="conversation-new"' + (' open' if query.get('novo') else '') + '><summary>Enviar documento interno</summary>' + upload_form + '</details>' + filters + '<h2>Documentos <small class="result-count">' + str(total) + '</small></h2><div class="internal-doc-list">' + items + '</div>' + pagination + '</section>'
            return self.page('Documentos internos', content, user)
        if path == '/admin/solicitacoes':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            term = query.get('q', [''])[0].strip()[:150]
            state = query.get('status', ['ativas'])[0]
            request_filter = query.get('id', [''])[0]
            with db() as c:
                if not has_permission(c, user, 'manage_cases'):
                    return self.forbidden()
                if user['role'] == 'admin':
                    request_rows = c.execute("SELECT r.*, u.name AS client, ca.title AS case_title, ru.name AS responder FROM requests r JOIN users u ON u.id=r.client_id LEFT JOIN cases ca ON ca.id=r.case_id LEFT JOIN users ru ON ru.id=r.responded_by WHERE u.deleted_at='' AND (r.case_id IS NULL OR ca.deleted_at='') ORDER BY r.id DESC").fetchall()
                else:
                    request_rows = c.execute("SELECT r.*, u.name AS client, ca.title AS case_title, ru.name AS responder FROM requests r JOIN users u ON u.id=r.client_id LEFT JOIN cases ca ON ca.id=r.case_id LEFT JOIN users ru ON ru.id=r.responded_by WHERE u.deleted_at='' AND (r.case_id IS NULL OR ca.deleted_at='') AND (" + self.scoped_condition('r') + ") ORDER BY r.id DESC", (user['id'], user['id'], user['id'])).fetchall()
                stale_hours = max(1, int(setting(c, 'stale_hours', '48') or 48))
            if request_filter.isdigit():
                request_rows = [row for row in request_rows if row['id'] == int(request_filter)]
            if state == 'ativas':
                request_rows = [row for row in request_rows if row['status'] in ('Pendente', 'Em andamento')]
            elif state in ('Pendente', 'Em andamento', 'Respondida', 'Concluída', 'Informativo'):
                request_rows = [row for row in request_rows if row['status'] == state]
            if term:
                needle = term.casefold()
                request_rows = [row for row in request_rows if needle in ' '.join(str(row[key] or '') for key in ('subject', 'body', 'client', 'case_title')).casefold()]
            request_rows, pagination, total = self.paginate_rows(request_rows)
            items = []
            for request in request_rows:
                reply_form = form('/admin/respond', f'<input type="hidden" name="request_id" value="{request["id"]}"><label>Resposta<textarea name="response">{esc(request["response"])}</textarea></label>' + status_select(request['status']), 'Salvar resposta')
                items.append('<div class="' + status_box_class('case-box', request['status'], request['last_activity_at'] or request['created'], stale_hours) + '"><strong>' + esc(request['client']) + ' — ' + esc(request['subject']) + '</strong><p>' + esc(request['body']) + '</p><p>' + status_badge(request['status']) + ((' · respondido por ' + esc(request['responder'])) if request['responder'] else '') + ((' · caso: ' + esc(request['case_title'])) if request['case_title'] else '') + '</p><details class="admin-secondary"><summary>Responder ou atualizar</summary>' + reply_form + '</details></div>')
            options = ''.join('<option value="' + esc(value) + '"' + (' selected' if state == value else '') + '>' + esc(label) + '</option>' for value, label in [('ativas', 'Em aberto'), ('todas', 'Todas')] + [(item, item) for item in ('Pendente', 'Em andamento', 'Respondida', 'Concluída', 'Informativo')])
            filters = '<form method="get" action="/admin/solicitacoes" class="admin-filters"><label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Cliente, caso ou assunto"></label><label>Situação<select name="status">' + options + '</select></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/solicitacoes">Limpar</a></form>'
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Solicitações</h1><p class="muted">Solicitações dos clientes e respostas da equipe.</p>' + filters + '<p class="muted">' + str(total) + ' solicitação(ões) encontrada(s).</p>' + (''.join(items) or '<p>Nenhuma solicitação encontrada.</p>') + pagination + '</section>'
            return self.page('Solicitações', content, user)
        if path == '/admin/compromisso':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                appointment_id = int(query.get('appointment_id', ['0'])[0])
            except (TypeError, ValueError):
                appointment_id = 0
            with db() as c:
                appointment = c.execute("SELECT a.*,u.name AS client_name,ca.title AS case_title,ru.name AS owner_name FROM appointments a LEFT JOIN users u ON u.id=a.client_id LEFT JOIN cases ca ON ca.id=a.case_id LEFT JOIN users ru ON ru.id=a.owner_id WHERE a.id=? AND a.deleted_at=''", (appointment_id,)).fetchone()
                if not appointment or not self.can_edit_appointment(c, user, appointment):
                    return self.forbidden()
                clients = self.scoped_clients(c, user)
                cases = self.scoped_cases(c, user)
                staff = c.execute("SELECT id,name FROM users WHERE role IN ('staff','admin') AND active=1 AND deleted_at='' ORDER BY name").fetchall()
                history = c.execute("SELECT a.*,u.name AS actor FROM audit a LEFT JOIN users u ON u.id=a.user_id WHERE a.entity='appointment' AND a.entity_id=? ORDER BY a.id DESC LIMIT 20", (appointment_id,)).fetchall()
                selected_participants = {row['user_id'] for row in c.execute('SELECT user_id FROM appointment_participants WHERE appointment_id=?', (appointment_id,)).fetchall()}
            client_options = '<option value="">Sem cliente (evento interno)</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if appointment['client_id'] == row['id'] else '') + '>' + esc(row['name']) + '</option>' for row in clients)
            case_options = '<option value="">Sem caso específico</option>' + ''.join('<option value="' + str(row['id']) + '" data-client-id="' + str(row['client_id']) + '"' + (' selected' if appointment['case_id'] == row['id'] else '') + '>#' + str(row['id']) + ' — ' + esc(row['title']) + '</option>' for row in cases)
            owner_options = '<option value="">Sem responsável</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if appointment['owner_id'] == row['id'] else '') + '>' + esc(row['name']) + '</option>' for row in staff)
            kind_options = ''.join('<option value="' + value + '"' + (' selected' if appointment['kind'] == value else '') + '>' + label + '</option>' for value, label in TASK_KIND_LABELS.items())
            reminder_options = ''.join('<option value="' + value + '"' + (' selected' if appointment['reminder_choice'] == value else '') + '>' + label + '</option>' for value, label in (('none', 'Sem lembrete'), ('1h', '1 hora antes'), ('1d', '1 dia antes'), ('global', 'Usar padrão do escritório')))
            privacy_options = ''.join('<option value="' + value + '"' + (' selected' if (appointment['privacy'] or 'internal') == value else '') + '>' + label + '</option>' for value, label in (('private', 'Pessoal — somente eu'), ('internal', 'Interno — toda a equipe'), ('client', 'Vinculado ao cliente/caso')))
            participants_options = ''.join('<option value="' + str(row['id']) + '"' + (' selected' if row['id'] in selected_participants else '') + '>' + esc(row['name']) + '</option>' for row in staff)
            participants_select = '<fieldset class="check-group"><legend>Participantes</legend>' + ''.join('<label class="check"><input type="checkbox" name="participant_' + str(row['id']) + '" value="1"' + (' checked' if row['id'] in selected_participants else '') + '> ' + esc(row['name']) + '</label>' for row in staff) + '</fieldset>'
            status_options = ''.join('<option value="' + value + '"' + (' selected' if appointment['status'] == value else '') + '>' + label + '</option>' for value, label in (('pendente', 'Pendente'), ('realizado', 'Realizado'), ('cancelado', 'Cancelado')))
            due_value = str(appointment['when_at']).replace(' ', 'T')[:16]
            form_html = form('/admin/compromisso/editar', '<input type="hidden" name="appointment_id" value="' + str(appointment_id) + '">' + input_field('Título do evento', 'title', appointment['title']) + '<label>Tipo<select name="kind">' + kind_options + '</select></label><label>Privacidade<select name="privacy">' + privacy_options + '</select></label>' + '<label>Cliente (opcional)<select name="client_id" data-context-client>' + client_options + '</select></label>' + '<label>Caso<select name="case_id" data-context-case>' + case_options + '</select></label>' + '<label>Responsável<select name="owner_id">' + owner_options + '</select></label>' + participants_select + '<label>Data e hora<input type="datetime-local" name="when_at" value="' + esc(due_value) + '" required></label>' + input_field('Local ou link', 'location', appointment['location'], required=False) + '<label>Lembrete<select name="reminder_choice">' + reminder_options + '</select></label><label>Situação<select name="status">' + status_options + '</select></label><label>Orientações<textarea name="notes">' + esc(appointment['notes']) + '</textarea></label>', 'Salvar alterações')
            history_html = ''.join('<li><strong>' + esc(item['created']) + ' — ' + esc(item['action']) + '</strong><br><small>' + esc(item['actor'] or 'Sistema') + ' · ' + esc(item['detail']) + '</small></li>' for item in history) or '<li>Nenhuma alteração registrada.</li>'
            cancel_form = form('/admin/compromisso/status', '<input type="hidden" name="appointment_id" value="' + str(appointment_id) + '"><input type="hidden" name="status" value="cancelado">', 'Cancelar evento') if appointment['status'] != 'cancelado' else ''
            delete_form = form('/admin/compromisso/excluir', '<input type="hidden" name="appointment_id" value="' + str(appointment_id) + '">', 'Excluir evento') if is_super(user) or appointment['created_by'] == user['id'] else ''
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<a class="text-link" href="/admin/compromissos">← Agenda</a><p class="eyebrow">EVENTO DA AGENDA</p><h1>' + esc(appointment['title']) + '</h1><p class="muted">' + esc(appointment['client_name'] or 'Evento interno') + ((' · ' + esc(appointment['case_title'])) if appointment['case_title'] else '') + ' · ' + esc(fmt_when(appointment['when_at'])) + ' · ' + esc(appointment['owner_name'] or 'Sem responsável') + '</p><div class="panel-dash-grid"><div class="panel-col">' + panel_card('Editar evento', form_html) + '</div><div class="panel-col">' + panel_card('Histórico', '<ul class="panel-attention">' + history_html + '</ul>') + panel_card('Ações', (cancel_form or '<p class="muted">Evento já cancelado.</p>') + (delete_form if delete_form else '<p class="muted">Somente o criador ou o administrador principal pode excluir.</p>')) + '</div></div></section>'
            return self.page('Evento da agenda', content, user)
        if path == '/admin/compromissos':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            selected_client = query.get('client_id', [''])[0]
            selected_case = query.get('case_id', [''])[0]
            state = query.get('status', ['pendente'])[0]
            view_mode = query.get('visao', ['lista'])[0]
            month_raw = query.get('mes', [''])[0]
            calendar_mode = view_mode == 'mes'
            kind_filter = query.get('tipo', [''])[0]
            term = query.get('q', [''])[0].strip()[:150]
            date_from = query.get('de', [''])[0]
            date_to = query.get('ate', [''])[0]
            with db() as c:
                if not has_permission(c, user, 'manage_cases'):
                    return self.forbidden()
                clients = self.scoped_clients(c, user)
                cases = self.scoped_cases(c, user)
                staff = c.execute("SELECT id,name FROM users WHERE role IN ('staff','admin') AND active=1 AND deleted_at='' ORDER BY name").fetchall()
                appointments = c.execute("SELECT a.*, u.name AS client, ca.title AS case_title, ru.name AS owner_name, (SELECT GROUP_CONCAT(pu.name, ', ') FROM appointment_participants ap JOIN users pu ON pu.id=ap.user_id WHERE ap.appointment_id=a.id) AS participants FROM appointments a LEFT JOIN users u ON u.id=a.client_id LEFT JOIN cases ca ON ca.id=a.case_id LEFT JOIN users ru ON ru.id=a.owner_id WHERE a.deleted_at='' ORDER BY a.when_at").fetchall()
                appointments = [row for row in appointments if self.can_view_appointment(c, user, row)]
                agenda_tasks = self.task_rows(c, user)
            if state in ('pendente', 'realizado', 'cancelado') and not calendar_mode:
                appointments = [row for row in appointments if row['status'] == state]
            if kind_filter in TASK_KIND_LABELS:
                appointments = [row for row in appointments if (row['kind'] or 'compromisso') == kind_filter]
            if selected_client.isdigit():
                appointments = [row for row in appointments if row['client_id'] == int(selected_client)]
            if selected_case.isdigit():
                appointments = [row for row in appointments if row['case_id'] == int(selected_case)]
            if term:
                needle = term.casefold()
                appointments = [row for row in appointments if needle in ' '.join(str(row[key] or '') for key in ('title', 'client', 'case_title')).casefold()]
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_from):
                appointments = [row for row in appointments if str(row['when_at'])[:10] >= date_from]
            else:
                date_from = ''
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_to):
                appointments = [row for row in appointments if str(row['when_at'])[:10] <= date_to]
            else:
                date_to = ''
            calendar_html = ''
            toggle_month = datetime.date.today().strftime('%Y-%m')
            if calendar_mode:
                if re.fullmatch(r'\d{4}-\d{2}', month_raw):
                    year, month = int(month_raw[:4]), int(month_raw[5:7])
                else:
                    today = datetime.date.today()
                    year, month = today.year, today.month
                month_key = f'{year:04d}-{month:02d}'
                toggle_month = month_key
                month_appointments = [appointment for appointment in appointments if str(appointment['when_at'])[:7] == month_key]
                total = len(month_appointments)
                pagination = ''
                by_day = {}
                tasks_by_day = {}
                for appointment in month_appointments:
                    by_day.setdefault(str(appointment['when_at'])[:10], []).append(appointment)
                for task in agenda_tasks:
                    if task['due_at'] and str(task['due_at'])[:7] == month_key and task['status'] != 'concluida':
                        tasks_by_day.setdefault(str(task['due_at'])[:10], []).append(task)
                total += sum(len(items) for items in tasks_by_day.values())
                month_names = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
                first_day = datetime.date(year, month, 1)
                days_in_month = calendar.monthrange(year, month)[1]
                cells = ['<td class="calendar-day is-empty"></td>'] * first_day.weekday()
                for day in range(1, days_in_month + 1):
                    date_key = f'{year:04d}-{month:02d}-{day:02d}'
                    day_events = ''.join('<a class="calendar-event status-border-' + status_color(appointment['status']) + '" href="' + ('/admin/caso/historico?case_id=' + str(appointment['case_id']) if appointment['case_id'] else '/admin/compromissos') + '"><strong>' + esc(str(appointment['when_at'])[11:16]) + '</strong> ' + esc(appointment['title']) + '<small>' + esc(appointment['client'] or 'Evento interno') + '</small></a>' for appointment in by_day.get(date_key, [])) + ''.join('<a class="calendar-event calendar-task status-border-' + ('red' if task_is_overdue(task) else 'yellow') + '" href="/admin/tarefa?task_id=' + str(task['id']) + '"><strong>Prazo</strong> ' + esc(task['title']) + '<small>' + esc(task['client_name'] or task['case_title'] or 'Tarefa interna') + '</small></a>' for task in tasks_by_day.get(date_key, []))
                    cells.append('<td class="calendar-day' + (' has-events' if day_events else '') + (' is-today' if date_key == datetime.date.today().strftime('%Y-%m-%d') else '') + '"><span class="calendar-day-number">' + str(day) + '</span><div class="calendar-events">' + day_events + '</div></td>')
                while len(cells) % 7:
                    cells.append('<td class="calendar-day is-empty"></td>')
                rows = ''.join('<tr>' + ''.join(cells[index:index + 7]) + '</tr>' for index in range(0, len(cells), 7))
                previous_month = (first_day - datetime.timedelta(days=1)).strftime('%Y-%m')
                next_month = (datetime.date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)).strftime('%Y-%m')
                calendar_html = '<div class="calendar-wrap"><div class="calendar-head"><a class="btn ghost" href="/admin/compromissos?visao=mes&mes=' + previous_month + '">← Anterior</a><h2>' + month_names[month] + ' de ' + str(year) + '</h2><a class="btn ghost" href="/admin/compromissos?visao=mes&mes=' + next_month + '">Próximo →</a></div><table class="calendar-grid"><thead><tr><th>Seg</th><th>Ter</th><th>Qua</th><th>Qui</th><th>Sex</th><th>Sáb</th><th>Dom</th></tr></thead><tbody>' + rows + '</tbody></table><div class="calendar-legend">' + ''.join('<span><i class="panel-dot ' + color + '"></i>' + label + '</span>' for color, label in (('yellow', 'Em andamento'), ('blue', 'Aguardando cliente'), ('green', 'Concluído'), ('gray', 'Informativo'))) + '</div></div>'
                items = ''
            else:
                appointments, pagination, total = self.paginate_rows(appointments)
            valid_client = selected_client if any(str(row['id']) == selected_client for row in clients) else ''
            valid_case = selected_case if any(str(row['id']) == selected_case and str(row['client_id']) == valid_client for row in cases) else ''
            kind_options = ''.join('<option value="' + value + '">' + label + '</option>' for value, label in TASK_KIND_LABELS.items())
            owner_options = '<option value="">Sem responsável específico</option>' + ''.join('<option value="' + str(row['id']) + '">' + esc(row['name']) + '</option>' for row in staff)
            client_options = '<option value="">Sem cliente (evento interno)</option>' + ''.join('<option value="' + str(row['id']) + '"' + (' selected' if str(row['id']) == valid_client else '') + '>' + esc(row['name']) + '</option>' for row in clients)
            client_select = '<label>Cliente (opcional)<select name="client_id" data-context-client>' + client_options + '</select></label>'
            reminder_options = ''.join('<option value="' + value + '"' + (' selected' if value == '1d' else '') + '>' + label + '</option>' for value, label in (('none', 'Sem lembrete'), ('1h', '1 hora antes'), ('1d', '1 dia antes'), ('global', 'Usar padrão do escritório')))
            reminder_select = '<label>Lembrete<select name="reminder_choice">' + reminder_options + '</select></label>'
            privacy_options = ''.join('<option value="' + value + '"' + (' selected' if value == 'internal' else '') + '>' + label + '</option>' for value, label in (('private', 'Pessoal — somente eu'), ('internal', 'Interno — toda a equipe'), ('client', 'Vinculado ao cliente/caso')))
            participants_options = ''.join('<option value="' + str(row['id']) + '">' + esc(row['name']) + '</option>' for row in staff)
            participants_select = '<fieldset class="check-group"><legend>Participantes</legend>' + ''.join('<label class="check"><input type="checkbox" name="participant_' + str(row['id']) + '" value="1"> ' + esc(row['name']) + '</label>' for row in staff) + '</fieldset>'
            create_form = form('/admin/appointment', admin_context_hidden(clients, cases, valid_client, valid_case) + client_select + admin_case_select(cases, valid_case) + field('Título do evento', 'title') + '<label>Tipo<select name="kind">' + kind_options + '</select></label><label>Privacidade<select name="privacy">' + privacy_options + '</select></label>' + field('Data e hora', 'when_at', 'datetime-local') + field('Local ou link', 'location', required=False) + '<label>Responsável interno<select name="owner_id">' + owner_options + '</select></label>' + participants_select + reminder_select + field('Orientações', 'notes', required=False), 'Cadastrar')
            items = ''.join('<div class="case-box"><strong>' + esc(fmt_when(appointment['when_at'])) + ' — ' + esc(appointment['title']) + '</strong><p>' + esc(appointment['client'] or 'Evento interno') + ((' · ' + esc(appointment['case_title'])) if appointment['case_title'] else '') + ' ' + appointment_badge(appointment['status']) + ' <span class="status-badge status-gray">' + TASK_KIND_LABELS.get(appointment['kind'] or 'compromisso', 'Compromisso') + '</span></p><p class="muted">' + (('Local: ' + esc(appointment['location']) + ' · ') if appointment['location'] else '') + (('Responsável: ' + esc(appointment['owner_name']) + ' · ') if appointment['owner_name'] else '') + (('Lembrete: ' + {'none': 'sem lembrete', '1h': '1 hora antes', '1d': '1 dia antes', 'global': 'padrão do escritório'}.get(appointment['reminder_choice'], appointment['reminder_choice']) + ' · ') if appointment['reminder_choice'] else '') + esc(appointment['notes']) + '</p><p><a class="text-link" href="/admin/compromisso?appointment_id=' + str(appointment['id']) + '">Editar evento →</a></p><details class="admin-secondary"><summary>Alterar situação</summary>' + form('/admin/compromisso/status', '<input type="hidden" name="appointment_id" value="' + str(appointment['id']) + '"><label>Status<select name="status">' + ''.join('<option' + (' selected' if appointment['status'] == s else '') + '>' + s + '</option>' for s in ('pendente','realizado','cancelado')) + '</select></label>', 'Salvar situação') + '</details></div>' for appointment in appointments) or '<p>Nenhum compromisso encontrado.</p>'
            status_options = ''.join('<option value="' + value + '"' + (' selected' if state == value else '') + '>' + label + '</option>' for value, label in (('pendente', 'Pendentes'), ('realizado', 'Realizados'), ('cancelado', 'Cancelados'), ('todos', 'Todos')))
            kind_filter_options = '<option value="">Todos os tipos</option>' + ''.join('<option value="' + value + '"' + (' selected' if kind_filter == value else '') + '>' + label + '</option>' for value, label in TASK_KIND_LABELS.items())
            hidden = ('<input type="hidden" name="client_id" value="' + esc(selected_client) + '">' if selected_client.isdigit() else '') + ('<input type="hidden" name="case_id" value="' + esc(selected_case) + '">' if selected_case.isdigit() else '')
            filters = '<form method="get" action="/admin/compromissos" class="admin-filters">' + hidden + '<label>Buscar<input type="search" name="q" value="' + esc(term) + '" placeholder="Cliente, caso ou título"></label><label>Situação<select name="status">' + status_options + '</select></label><label>Tipo<select name="tipo">' + kind_filter_options + '</select></label><label>De<input type="date" name="de" value="' + esc(date_from) + '"></label><label>Até<input type="date" name="ate" value="' + esc(date_to) + '"></label><button class="btn" type="submit">Filtrar</button><a class="text-link" href="/admin/compromissos">Limpar</a></form>'
            create = '<details class="conversation-new"' + (' open' if query.get('novo') else '') + '><summary>Novo compromisso</summary>' + create_form + '</details>'
            view_toggle = '<div class="view-toggle"><a class="' + ('active' if not calendar_mode else '') + '" href="/admin/compromissos?visao=lista">Lista</a><a class="' + ('active' if calendar_mode else '') + '" href="/admin/compromissos?visao=mes&mes=' + toggle_month + '">Calendário</a></div>'
            list_html = '<h2>Compromissos <small class="result-count">' + str(total) + '</small></h2>' + items + pagination
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Agenda</h1><p class="muted">Compromissos pendentes incluem datas já vencidas que ainda precisam de atualização.</p>' + create + filters + view_toggle + '<p><a class="text-link" href="/admin/tarefas">Ver prazos e tarefas →</a></p>' + (calendar_html if calendar_mode else list_html) + '</section>'
            return self.page('Compromissos', content, user)
        if path == '/admin/atualizacoes':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            with db() as c:
                if not has_permission(c, user, 'manage_cases'):
                    return self.forbidden()
                clients = self.scoped_clients(c, user)
                cases = self.scoped_cases(c, user)
                if user['role'] == 'admin':
                    update_rows = c.execute("SELECT up.*, u.name AS client, ca.title AS case_title FROM updates up JOIN users u ON u.id=up.client_id LEFT JOIN cases ca ON ca.id=up.case_id ORDER BY up.id DESC LIMIT 100").fetchall()
                else:
                    update_rows = c.execute("SELECT up.*, u.name AS client, ca.title AS case_title FROM updates up JOIN users u ON u.id=up.client_id LEFT JOIN cases ca ON ca.id=up.case_id WHERE (" + self.scoped_condition('up') + ") ORDER BY up.id DESC LIMIT 100", (user['id'], user['id'], user['id'])).fetchall()
            options = ''.join(f'<option value="{x["id"]}">{esc(x["name"])} ({esc(x["email"])})</option>' for x in clients)
            select = '<label>Cliente<select name="client_id" required>' + options + '</select></label>' if clients else ''
            case_options = '<option value="">Sem caso específico</option>' + ''.join(f'<option value="{x["id"]}">#{x["id"]} — {esc(x["title"])} ({esc(x["client_name"])})</option>' for x in cases)
            case_select = '<label>Caso<select name="case_id">' + case_options + '</select></label>'
            create_form = form('/admin/update', select + case_select + field('Título', 'title') + '<label>Descrição<textarea name="body" required></textarea></label>', 'Publicar') if clients else '<p class="muted">Nenhum cliente atribuído.</p>'
            items = ''.join(card(update['title'], '<p class="muted">' + esc(update['client']) + ' · ' + esc(update['case_title'] or 'Caso geral') + ' · ' + esc(update['created']) + '</p><p>' + esc(update['body']) + '</p>') for update in update_rows) or '<p>Nenhuma atualização.</p>'
            content = '<section class="wrap section">' + self.admin_nav(user) + '<h1>Atualizações</h1>' + card('Publicar atualização', create_form) + card('Publicações', items) + '<p><a class="text-link" href="/admin">Voltar ao painel</a></p></section>'
            return self.page('Atualizações', content, user)
        if path == '/admin/conteudos':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            with db() as c:
                posts = c.execute('SELECT * FROM posts ORDER BY id DESC').fetchall()
            create_form = form('/admin/post', field('Título', 'title') + field('Categoria', 'category') + '<label>Texto<textarea name="body" required></textarea></label><label class="check"><input type="checkbox" name="published" value="1"> Publicar no site</label>', 'Salvar conteúdo')
            items = ''.join('<li>' + esc(post['title']) + ' — ' + ('Publicado' if post['published'] else 'Rascunho') + ' — ' + esc(post['created']) + '</li>' for post in posts) or '<li>Nenhum conteúdo.</li>'
            content = '<section class="wrap section">' + self.admin_nav(user) + '<h1>Conteúdos jurídicos</h1>' + card('Novo conteúdo', create_form) + card('Publicações', '<ul>' + items + '</ul>') + '<p><a class="text-link" href="/admin">Voltar ao painel</a></p></section>'
            return self.page('Conteúdos jurídicos', content, user)
        if path == '/admin/faq':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            with db() as c:
                faqs = c.execute("SELECT * FROM faqs ORDER BY category,sort_order,id").fetchall()
            category_names = list(FAQ_CATEGORIES) + sorted({faq['category'] for faq in faqs if faq['category'] not in FAQ_CATEGORIES})
            category_options = ''.join('<option value="' + esc(name) + '">' + esc(name) + '</option>' for name in category_names)
            create_form = form('/admin/faq', '<label>Categoria<select name="category">' + category_options + '</select></label>' + field('Pergunta', 'question') + '<label>Resposta<textarea name="answer" required></textarea></label>' + input_field('Ordem', 'sort_order', '0', 'number', required=False) + '<label class="check"><input type="checkbox" name="published" value="1"> Publicar no site</label>', 'Salvar pergunta')
            items = []
            for faq in faqs:
                edit_form = form('/admin/faq/editar', '<input type="hidden" name="faq_id" value="' + str(faq['id']) + '">' + '<label>Categoria<select name="category">' + ''.join('<option value="' + esc(name) + '"' + (' selected' if name == faq['category'] else '') + '>' + esc(name) + '</option>' for name in category_names) + '</select></label>' + input_field('Pergunta', 'question', faq['question']) + '<label>Resposta<textarea name="answer" required>' + esc(faq['answer']) + '</textarea></label>' + input_field('Ordem', 'sort_order', faq['sort_order'], 'number', required=False) + '<label class="check"><input type="checkbox" name="published" value="1"' + (' checked' if faq['published'] else '') + '> Publicado</label>', 'Salvar alterações')
                items.append('<article class="faq-admin-item"><div class="faq-admin-head"><div><span class="contact-state">' + esc(faq['category'] or 'Geral') + '</span><h3>' + esc(faq['question']) + '</h3></div><span class="status-badge status-' + ('green' if faq['published'] else 'gray') + '">' + ('Publicado' if faq['published'] else 'Rascunho') + '</span></div><p class="muted">Ordem: ' + str(faq['sort_order']) + ' · atualizado em ' + esc(faq['updated'] or '—') + '</p><details class="admin-secondary"><summary>Editar pergunta</summary>' + edit_form + '</details></article>')
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Perguntas frequentes</h1><p class="muted">Gerencie categorias, ordem e publicação. A página pública exibe apenas perguntas publicadas.</p><div class="quick-actions"><a class="btn ghost" href="/faq">Ver página pública</a></div><details class="conversation-new"><summary>Nova pergunta</summary>' + create_form + '</details>' + ('<div class="faq-admin-list">' + ''.join(items) + '</div>' or '<p>Nenhuma pergunta cadastrada.</p>') + '</section>'
            return self.page('Perguntas frequentes', content, user)
        if path == '/admin/busca':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            term = query.get('q', [''])[0].strip()
            clients = []
            cases = []
            messages = []
            docs = []
            requests_found = []
            if len(term) >= 2:
                like = '%' + term + '%'
                with db() as c:
                    all_clients = c.execute("SELECT * FROM users WHERE role='client' AND deleted_at='' ORDER BY name").fetchall()
                    clients = [client for client in all_clients if term.lower() in (client['name'] + ' ' + client['email']).lower()][:20]
                    all_cases = self.visible_cases(c, user)
                    cases = [case for case in all_cases if term.lower() in (case['title'] + ' ' + (case['original_title'] or '') + ' ' + (case['case_number'] or '') + ' ' + case['client_name']).lower()][:20]
                    if user['role'] == 'admin':
                        messages = c.execute("SELECT m.*, u.name AS client, ca.title AS case_title FROM messages m JOIN users u ON u.id=m.client_id LEFT JOIN cases ca ON ca.id=m.case_id WHERE u.deleted_at='' AND (m.case_id IS NULL OR ca.deleted_at='') AND m.visibility='client' AND m.body LIKE ? ORDER BY m.id DESC LIMIT 20", (like,)).fetchall()
                        docs = c.execute("SELECT d.*, u.name AS client, ca.title AS case_title FROM documents d JOIN users u ON u.id=d.client_id LEFT JOIN cases ca ON ca.id=d.case_id WHERE u.deleted_at='' AND (d.case_id IS NULL OR ca.deleted_at='') AND d.deleted_at='' AND d.filename LIKE ? ORDER BY d.id DESC LIMIT 20", (like,)).fetchall()
                        requests_found = c.execute("SELECT r.*, u.name AS client, ca.title AS case_title FROM requests r JOIN users u ON u.id=r.client_id LEFT JOIN cases ca ON ca.id=r.case_id WHERE r.subject LIKE ? OR r.body LIKE ? ORDER BY r.id DESC LIMIT 20", (like, like)).fetchall()
                    else:
                        messages = c.execute("SELECT m.*, u.name AS client, ca.title AS case_title FROM messages m JOIN users u ON u.id=m.client_id LEFT JOIN cases ca ON ca.id=m.case_id WHERE u.deleted_at='' AND (m.case_id IS NULL OR ca.deleted_at='') AND m.visibility='client' AND (m.case_id IN (SELECT id FROM cases WHERE deleted_at='') OR (" + self.scoped_condition('m') + ")) AND m.body LIKE ? ORDER BY m.id DESC LIMIT 20", (user['id'], user['id'], user['id'], like)).fetchall()
                        docs = c.execute("SELECT d.*, u.name AS client, ca.title AS case_title FROM documents d JOIN users u ON u.id=d.client_id LEFT JOIN cases ca ON ca.id=d.case_id WHERE u.deleted_at='' AND (d.case_id IS NULL OR ca.deleted_at='') AND d.deleted_at='' AND (d.case_id IN (SELECT id FROM cases WHERE deleted_at='') OR (" + self.scoped_condition('d') + ")) AND d.filename LIKE ? ORDER BY d.id DESC LIMIT 20", (user['id'], user['id'], user['id'], like)).fetchall()
                        requests_found = c.execute("SELECT r.*, u.name AS client, ca.title AS case_title FROM requests r JOIN users u ON u.id=r.client_id LEFT JOIN cases ca ON ca.id=r.case_id WHERE (" + self.scoped_condition('r') + ") AND (r.subject LIKE ? OR r.body LIKE ?) ORDER BY r.id DESC LIMIT 20", (user['id'], user['id'], user['id'], like, like)).fetchall()
            search_form = '<form method="get" action="/admin/busca" class="admin-search"><label>Pesquisar<input type="search" name="q" value="' + esc(term) + '"></label><button class="btn" type="submit">Pesquisar</button></form>'
            client_html = ''.join('<li><a class="text-link" href="/admin/cliente?client_id=' + str(client['id']) + '">' + esc(client['name']) + '</a> — ' + esc(client['email']) + '</li>' for client in clients) or '<li>Nenhum cliente encontrado.</li>'
            case_html = ''.join('<li><a class="text-link" href="/admin/caso/historico?case_id=' + str(case['id']) + '">#' + str(case['id']) + ' — ' + esc(case['title']) + '</a> — ' + esc(case['client_name']) + '</li>' for case in cases) or '<li>Nenhum caso encontrado.</li>'
            message_html = ''.join('<li>' + esc(message['client']) + ' — ' + ('<a class="text-link" data-conversation-link href="/conversas/' + str(message['conversation_id']) + '">' + esc(message['body'][:160]) + '</a>' if message['conversation_id'] else esc(message['body'][:160])) + '</li>' for message in messages) or '<li>Nenhuma mensagem encontrada.</li>'
            doc_html = ''.join('<li>' + esc(doc['client']) + ' — <a class="text-link" href="/arquivo/' + str(doc['id']) + '">' + esc(doc['filename']) + '</a></li>' for doc in docs) or '<li>Nenhum documento encontrado.</li>'
            req_html = ''.join('<li>' + esc(request['client']) + ' — ' + esc(request['subject']) + '</li>' for request in requests_found) or '<li>Nenhuma solicitação encontrada.</li>'
            content = '<section class="wrap section">' + self.admin_nav(user) + '<h1>Busca</h1>' + search_form + '<div class="dashboard"><div>' + card('Clientes', '<ul>' + client_html + '</ul>') + card('Casos', '<ul>' + case_html + '</ul>') + '</div><div>' + card('Mensagens', '<ul>' + message_html + '</ul>') + card('Documentos', '<ul>' + doc_html + '</ul>') + card('Solicitações', '<ul>' + req_html + '</ul>') + '</div></div><p><a class="text-link" href="/admin">Voltar ao painel</a></p></section>'
            return self.page('Busca', content, user)
        if path == '/admin/relatorios':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            export = query.get('export', [''])[0]
            date_from = query.get('from', [''])[0].strip()
            date_to = query.get('to', [''])[0].strip()
            if not (len(date_from) == 10 and date_from[4] == '-'):
                date_from = ''
            if not (len(date_to) == 10 and date_to[4] == '-'):
                date_to = ''
            def in_period(value):
                day = str(value or '')[:10]
                return (not date_from or day >= date_from) and (not date_to or day <= date_to)
            with db() as c:
                if is_employee(user):
                    explicit = c.execute("SELECT allowed FROM permissions WHERE user_id=? AND action='view_reports'", (user['id'],)).fetchone()
                    if not explicit or not explicit['allowed']:
                        return self.forbidden()
                elif not has_permission(c, user, 'view_reports'):
                    return self.forbidden()
                cases = [case for case in self.scoped_cases(c, user) if in_period(case['created'])]
                staff_rows = c.execute("SELECT id,name FROM users WHERE role IN ('admin','staff') ORDER BY name").fetchall()
                staff_names = {row['id']: row['name'] for row in staff_rows}
                if user['role'] == 'admin':
                    doc_rows = c.execute("SELECT created FROM documents WHERE source='cliente' AND deleted_at='' AND (case_id IS NULL OR case_id IN (SELECT id FROM cases WHERE deleted_at=''))").fetchall()
                    message_rows = c.execute("SELECT created FROM messages WHERE visibility='client' AND sender_role='client' AND (case_id IS NULL OR case_id IN (SELECT id FROM cases WHERE deleted_at=''))").fetchall()
                    request_rows = c.execute("SELECT created,responded_at FROM requests WHERE responded_at<>'' AND (case_id IS NULL OR case_id IN (SELECT id FROM cases WHERE deleted_at=''))").fetchall()
                else:
                    doc_rows = c.execute("SELECT created FROM documents WHERE source='cliente' AND deleted_at='' AND (" + self.scoped_condition('documents') + ')', (user['id'], user['id'], user['id'])).fetchall()
                    message_rows = c.execute("SELECT created FROM messages WHERE visibility='client' AND sender_role='client' AND (" + self.scoped_condition('messages') + ')', (user['id'], user['id'], user['id'])).fetchall()
                    request_rows = c.execute("SELECT created,responded_at FROM requests WHERE responded_at<>'' AND (" + self.scoped_condition('requests') + ')', (user['id'], user['id'], user['id'])).fetchall()
            received_docs = sum(1 for row in doc_rows if in_period(row['created']))
            received_messages = sum(1 for row in message_rows if in_period(row['created']))
            response_hours = []
            for row in request_rows:
                if not in_period(row['created']):
                    continue
                start = parse_dt(row['created'])
                end = parse_dt(row['responded_at'])
                if start and end:
                    response_hours.append(max(0, (end - start).total_seconds() / 3600))
            avg_response = round(sum(response_hours) / len(response_hours), 1) if response_hours else None
            counts = {'yellow': 0, 'blue': 0, 'green': 0, 'gray': 0}
            by_responsible = {}
            for case in cases:
                color = status_color(case['status'])
                counts[color] = counts.get(color, 0) + 1
                responsible = case['responsible_id']
                key = responsible if responsible else 'sem'
                by_responsible[key] = by_responsible.get(key, 0) + 1
            if export == 'csv':
                buffer = io.StringIO()
                writer = csv.writer(buffer)
                writer.writerow(['ID', 'Cliente', 'Titulo', 'Status', 'Responsavel', 'Criado em', 'Ultima movimentacao'])
                for case in cases:
                    writer.writerow([case['id'], case['client_name'], case['title'], case['status'], staff_names.get(case['responsible_id'], 'Sem responsável'), case['created'], case['last_activity_at'] or case['created']])
                return self.send(buffer.getvalue(), ctype='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="relatorio-casos.csv"'})
            responsible_items = ''.join('<li>' + esc(staff_names.get(key, 'Sem responsável')) + ' — ' + str(value) + ' caso(s)</li>' for key, value in sorted(by_responsible.items(), key=lambda item: (-item[1], str(item[0])))) or '<li>Nenhum caso.</li>'
            items = ''.join('<li>#' + str(case['id']) + ' — ' + esc(case['title']) + ' — ' + status_badge(case['status']) + ' — ' + esc(case['client_name']) + ' — ' + esc(staff_names.get(case['responsible_id'], 'Sem responsável')) + '</li>' for case in cases) or '<li>Nenhum caso.</li>'
            kpi_html = '<div class="kpi-grid"><div class="kpi"><span class="kpi-value">' + str(len(cases)) + '</span><span class="kpi-label">Casos criados no período</span></div><div class="kpi"><span class="kpi-value">' + str(counts.get('yellow', 0)) + '</span><span class="kpi-label">Em andamento</span></div><div class="kpi"><span class="kpi-value">' + str(counts.get('blue', 0)) + '</span><span class="kpi-label">Aguardando cliente</span></div><div class="kpi"><span class="kpi-value">' + str(counts.get('green', 0)) + '</span><span class="kpi-label">Concluídos</span></div><div class="kpi"><span class="kpi-value">' + str(received_docs) + '</span><span class="kpi-label">Documentos recebidos</span></div><div class="kpi"><span class="kpi-value">' + str(received_messages) + '</span><span class="kpi-label">Mensagens de clientes</span></div><div class="kpi"><span class="kpi-value">' + (str(avg_response) if avg_response is not None else '—') + '</span><span class="kpi-label">Resposta média às solicitações (horas)</span></div></div>'
            filter_form = '<form method="get" action="/admin/relatorios"><label>De<input type="date" name="from" value="' + esc(date_from) + '"></label><label>Até<input type="date" name="to" value="' + esc(date_to) + '"></label><button class="btn" type="submit">Filtrar</button></form>'
            export_query = urllib.parse.urlencode({key: value for key, value in {'from': date_from, 'to': date_to}.items() if value} | {'export': 'csv'})
            content = '<section class="wrap section admin-workspace">' + self.admin_nav(user) + '<h1>Relatórios</h1><p class="muted">Os casos apresentados foram criados no período selecionado. <a class="text-link" href="/admin/relatorios?' + esc(export_query) + '">Exportar CSV</a></p>' + card('Período', filter_form) + kpi_html + '<p class="muted">A média considera apenas solicitações respondidas, do registro até a resposta; não inclui conversas. O traço indica que não há respostas no período.</p>' + card('Por responsável', '<ul>' + responsible_items + '</ul>') + card('Casos', '<ul>' + items + '</ul>') + '</section>'
            return self.page('Relatórios', content, user)
        if path == '/admin':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            return self.page('Administração', '<section class="wrap section admin-workspace">' + self.overview(user) + '</section>', user)
        if path == '/advogado':
            if not user or user['role'] not in ('admin', 'staff'):
                return self.forbidden()
            if user['role'] == 'admin':
                return self.redirect('/admin')
            return self.page('Painel do advogado', '<section class="wrap section admin-workspace">' + self.overview(user) + '</section>', user)
        self.send('Página não encontrada', 404)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        user = self.user()
        try:
            fields, files = self.read_post()
        except Exception:
            return self.error_page('Falha no envio', 'Não foi possível ler os dados enviados.', 400, user)
        try:
            if path in ('/chat/iniciar', '/chat/mensagem'):
                if not self.origin_ok() or not self.chat_csrf_ok(fields):
                    return self.forbidden()
                chat_user = self.user()
                if chat_user and chat_user['role'] != 'client':
                    return self.forbidden()
                with db() as c:
                    session = self.chat_session(c, chat_user)
                    if path == '/chat/iniciar':
                        if session:
                            return self.send_json({'ok': True, 'session': True, 'name': session['name'], 'status': session['status']})
                        token = secrets.token_urlsafe(32)
                        if chat_user:
                            name, email, phone, consent = chat_user['name'], chat_user['email'], chat_user['phone'], 1
                            user_id = chat_user['id']
                        else:
                            name = text_field(fields, 'name', 120, True, 'nome')
                            email = email_field(fields)
                            phone = text_field(fields, 'phone', 40)
                            if fields.get('consent') != '1':
                                raise ValidationError('É necessário aceitar o aviso de privacidade.')
                            consent = 1
                            user_id = None
                        guest_id = c.execute("INSERT INTO guest_sessions(contact_id,user_id,token_hash,name,email,phone,consent,ip,user_agent,status,last_seen,expires_at) VALUES(NULL,?,?,?,?,?,1,?,?,'open',CURRENT_TIMESTAMP,?)", (user_id, guest_token_hash(token), name, email, phone, self.client_ip(), self.headers.get('User-Agent', '')[:255], (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S'))).lastrowid
                        self.audit_action(c, chat_user['id'] if chat_user else None, 'iniciar chat', name, entity='guest_session', entity_id=guest_id)
                        c.commit()
                        return self.send_json({'ok': True, 'session': True, 'name': name, 'status': 'open'}, headers={'Set-Cookie': self.chat_cookie(token)})
                    if not session:
                        return self.send_json({'ok': False, 'error': 'session'}, 403)
                    body = text_field(fields, 'body', 3000, True, 'mensagem')
                    ip = self.client_ip()
                    if rate_limited('chat-message:ip:' + ip, CONTACT_LIMIT * 4, CONTACT_WINDOW):
                        return self.send_json({'ok': False, 'error': 'rate'}, 429)
                    message_id = c.execute("INSERT INTO guest_messages(guest_id,sender_role,sender_id,body) VALUES(?,'guest',?,?)", (session['id'], chat_user['id'] if chat_user else None, body)).lastrowid
                    c.execute('UPDATE guest_sessions SET updated=CURRENT_TIMESTAMP,last_seen=CURRENT_TIMESTAMP WHERE id=?', (session['id'],))
                    contact_id = session['contact_id']
                    if not contact_id and not session['user_id']:
                        contact_id = c.execute("INSERT INTO contacts(name,email,message,ip,consent,status) VALUES(?,?,?,?,1,'novo')", (session['name'], session['email'], body, ip)).lastrowid
                        c.execute('UPDATE guest_sessions SET contact_id=? WHERE id=?', (contact_id, session['id']))
                    elif contact_id:
                        c.execute("UPDATE contacts SET message=CASE WHEN message='' THEN ? ELSE message END,updated=CURRENT_TIMESTAMP WHERE id=?", (body, contact_id))
                    for admin_row in c.execute("SELECT id FROM users WHERE role IN ('admin','staff') AND active=1 AND deleted_at=''").fetchall():
                        notify(c, admin_row['id'], 'contact', 'Nova mensagem no chat', session['name'] + ': ' + body[:160], '/admin/atendimento-visitante?guest_id=' + str(session['id']), dedupe_key='chat-message-' + str(message_id) + '-u' + str(admin_row['id']))
                    self.audit_action(c, chat_user['id'] if chat_user else None, 'mensagem no chat', body[:200], entity='guest_session', entity_id=session['id'], after={'body': body})
                    c.commit()
                    return self.send_json({'ok': True, 'message_id': message_id})
            if path == '/entrar/mfa':
                if not self.origin_ok():
                    return self.forbidden()
                if not self.csrf_public_ok(fields):
                    return self.forbidden()
                if user:
                    return self.redirect('/admin' if user['role'] != 'client' else '/cliente')
                token = self.mfa_token()
                moment = time.monotonic()
                with MFA_LOCK:
                    challenge = MFA_CHALLENGES.get(token)
                    if challenge and moment > challenge['expires']:
                        MFA_CHALLENGES.pop(token, None)
                        challenge = None
                if not challenge:
                    return self.redirect('/entrar')
                code = text_field(fields, 'code', 40, True, 'código')
                valid = False
                account = None
                with db() as c:
                    account = c.execute("SELECT * FROM users WHERE id=? AND active=1 AND deleted_at=''", (challenge['uid'],)).fetchone()
                    if account and account['totp_enabled']:
                        step = verify_totp(account['totp_secret'], code, account['totp_last_step'])
                        if step:
                            c.execute('UPDATE users SET totp_last_step=? WHERE id=?', (step, account['id']))
                            valid = True
                        elif consume_recovery_code(c, account['id'], code):
                            valid = True
                            self.audit_action(c, account['id'], 'login com código de recuperação', account['email'])
                    if not valid:
                        with MFA_LOCK:
                            challenge['attempts'] = challenge.get('attempts', 0) + 1
                            if challenge['attempts'] >= 5:
                                MFA_CHALLENGES.pop(token, None)
                        self.audit_action(c, account['id'] if account else None, 'MFA falhou', account['email'] if account else '')
                        body = '<section class="wrap section narrow"><p class="eyebrow">VERIFICAÇÃO EM DUAS ETAPAS</p><h1>Código inválido</h1>' + card('Tentar novamente', '<p class="muted">Código incorreto ou expirado. Informe o código atual do app ou um código de recuperação.</p>' + form('/entrar/mfa', field('Código', 'code'), 'Verificar')) + '<p><a class="text-link" href="/entrar">Voltar ao login</a></p></section>'
                        return self.page('Código inválido', body, None, 401)
                    sid = secrets.token_urlsafe(32)
                    session_moment = time.monotonic()
                    with SESS_LOCK:
                        SESS[sid] = {'uid': account['id'], 'csrf': secrets.token_urlsafe(32), 'created': session_moment, 'last': session_moment}
                    self.audit_action(c, account['id'], 'login', account['email'])
                with MFA_LOCK:
                    MFA_CHALLENGES.pop(token, None)
                rate_reset('login:email:' + account['email'])
                target = '/senha' if account['must_change'] else ('/cliente' if account['role'] == 'client' else '/admin')
                return self.redirect(target, {'Set-Cookie': self.session_cookie(sid, SESSION_TTL)})
            if path == '/entrar':
                if not self.origin_ok():
                    return self.forbidden()
                email = email_field(fields)
                password = password_field(fields, 'password')
                ip = self.client_ip()
                if rate_limited('login:ip:' + ip, LOGIN_IP_LIMIT, LOGIN_WINDOW) or rate_limited('login:email:' + email, LOGIN_EMAIL_LIMIT, LOGIN_WINDOW):
                    return self.page('Muitas tentativas', '<section class="wrap section"><h1>Muitas tentativas</h1><p>Aguarde alguns minutos antes de tentar novamente.</p></section>', None, 429)
                with db() as c:
                    account = c.execute("SELECT * FROM users WHERE email=? AND active=1 AND portal_enabled=1 AND deleted_at=''", (email,)).fetchone()
                    if not account:
                        try:
                            hashlib.scrypt(password.encode(), salt=b'0' * 16, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=SCRYPT_MAXMEM, dklen=64)
                        except Exception:
                            pass
                        self.audit_action(c, None, 'login falhou', email)
                        return self.page('Acesso não autorizado', '<section class="wrap section"><h1>Credenciais inválidas</h1><a href="/entrar">Tentar novamente</a></section>', None, 401)
                    if not verify(password, account['password']):
                        self.audit_action(c, None, 'login falhou', email)
                        return self.page('Acesso não autorizado', '<section class="wrap section"><h1>Credenciais inválidas</h1><a href="/entrar">Tentar novamente</a></section>', None, 401)
                    if needs_rehash(account['password']):
                        c.execute('UPDATE users SET password=? WHERE id=?', (pwd(password), account['id']))
                    if account['totp_enabled']:
                        token = secrets.token_urlsafe(32)
                        moment = time.monotonic()
                        with MFA_LOCK:
                            for old_token, challenge in list(MFA_CHALLENGES.items()):
                                if moment > challenge['expires']:
                                    MFA_CHALLENGES.pop(old_token, None)
                            MFA_CHALLENGES[token] = {'uid': account['id'], 'expires': moment + MFA_TTL, 'attempts': 0}
                        self.audit_action(c, account['id'], 'login aguardando MFA', email)
                        return self.redirect('/entrar/mfa', {'Set-Cookie': self.mfa_cookie(token)})
                    sid = secrets.token_urlsafe(32)
                    moment = time.monotonic()
                    with SESS_LOCK:
                        SESS[sid] = {'uid': account['id'], 'csrf': secrets.token_urlsafe(32), 'created': moment, 'last': moment}
                    self.audit_action(c, account['id'], 'login', email)
                rate_reset('login:email:' + email)
                target = '/senha' if account['must_change'] else ('/cliente' if account['role'] == 'client' else '/admin')
                return self.redirect(target, {'Set-Cookie': self.session_cookie(sid, SESSION_TTL)})
            if path == '/contato':
                if not self.origin_ok():
                    return self.forbidden()
                if not self.csrf_public_ok(fields):
                    return self.forbidden()
                ip = self.client_ip()
                if rate_limited('contact:ip:' + ip, CONTACT_LIMIT, CONTACT_WINDOW):
                    return self.page('Muitas mensagens', '<section class="wrap section"><h1>Muitas mensagens</h1><p>Aguarde alguns minutos antes de enviar outra mensagem.</p></section>', user, 429)
                if fields.get('website'):
                    return self.page('Mensagem recebida', '<section class="wrap section"><h1>Mensagem registrada</h1><p>Mensagem armazenada neste ambiente de testes. Não há envio automático de e-mail.</p></section>', user)
                name = text_field(fields, 'name', 120, True, 'nome')
                email = email_field(fields)
                phone = text_field(fields, 'phone', 40)
                message = text_field(fields, 'message', 3000, True, 'mensagem')
                if fields.get('consent') != '1':
                    raise ValidationError('É necessário aceitar o aviso de privacidade.')
                token = secrets.token_urlsafe(32)
                with db() as c:
                    contact_id = c.execute('INSERT INTO contacts(name,email,message,ip,consent) VALUES(?,?,?,?,1)', (name, email, message, ip)).lastrowid
                    guest_id = c.execute("INSERT INTO guest_sessions(contact_id,token_hash,name,email,phone,consent,ip,user_agent,status,last_seen,expires_at) VALUES(?,?,?,?,?,1,?,?,'open',CURRENT_TIMESTAMP,?)", (contact_id, guest_token_hash(token), name, email, phone, ip, self.headers.get('User-Agent', '')[:255], (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S'))).lastrowid
                    c.execute("INSERT INTO guest_messages(guest_id,sender_role,body,read_by_guest) VALUES(?,'guest',?,1)", (guest_id, message))
                    for admin_row in c.execute("SELECT id FROM users WHERE role='admin' AND is_super=1 AND active=1 AND deleted_at=''").fetchall():
                        notify(c, admin_row['id'], 'contact', 'Novo contato pelo site', name + ' · ' + email, '/admin/atendimento-visitante?guest_id=' + str(guest_id), dedupe_key='contact-' + str(contact_id) + '-u' + str(admin_row['id']))
                link = '/atendimento/' + token
                body = '<section class="wrap section narrow"><h1>Mensagem registrada</h1><p>Recebemos sua mensagem. A equipe poderá responder por este mesmo canal.</p><div class="client-alert"><strong>Guarde este link para acompanhar a conversa:</strong><br><a class="text-link" href="' + esc(link) + '">' + esc(link) + '</a></div><p><a class="btn" href="' + esc(link) + '">Abrir conversa</a></p><p class="muted">O link é pessoal e dá acesso ao histórico desta conversa. Não compartilhe.</p></section>'
                return self.page('Mensagem recebida', body, user)
            if path == '/atendimento/responder':
                if not self.origin_ok() or not self.csrf_public_ok(fields):
                    return self.forbidden()
                token = str(fields.get('token', ''))
                body = text_field(fields, 'body', 3000, True, 'mensagem')
                ip = self.client_ip()
                if rate_limited('guest-message:ip:' + ip, CONTACT_LIMIT * 3, CONTACT_WINDOW):
                    return self.error_page('Muitas mensagens', 'Aguarde alguns minutos antes de enviar outra mensagem.', 429, user)
                with db() as c:
                    session = guest_session_by_token(c, token)
                    if not session or session['status'] != 'open':
                        return self.forbidden()
                    c.execute("INSERT INTO guest_messages(guest_id,sender_role,body) VALUES(?,'guest',?)", (session['id'], body))
                    c.execute('UPDATE guest_sessions SET updated=CURRENT_TIMESTAMP,last_seen=CURRENT_TIMESTAMP WHERE id=?', (session['id'],))
                    if session['contact_id']:
                        c.execute("UPDATE contacts SET status=CASE WHEN status='novo' THEN 'em_atendimento' ELSE status END,updated=CURRENT_TIMESTAMP WHERE id=?", (session['contact_id'],))
                    audience = [session['responsible_id']] if session['responsible_id'] else [row['id'] for row in c.execute("SELECT id FROM users WHERE role='admin' AND is_super=1 AND active=1 AND deleted_at=''")]
                    for uid in audience:
                        notify(c, uid, 'contact', 'Nova mensagem de visitante', session['name'] + ': ' + body[:160], '/admin/atendimento-visitante?guest_id=' + str(session['id']), dedupe_key='guest-message-' + str(session['id']) + '-' + str(c.execute('SELECT MAX(id) FROM guest_messages').fetchone()[0]) + '-u' + str(uid))
                return self.redirect('/atendimento/' + urllib.parse.quote(token))
            if path == '/cadastro':
                if user:
                    return self.redirect('/admin' if user['role'] != 'client' else '/cliente')
                if not self.origin_ok():
                    return self.forbidden()
                if not self.csrf_public_ok(fields):
                    return self.forbidden()
                ip = self.client_ip()
                if rate_limited('register:ip:' + ip, REGISTER_LIMIT, REGISTER_WINDOW):
                    return self.page('Muitas tentativas', '<section class="wrap section"><h1>Muitas tentativas</h1><p>Aguarde alguns minutos antes de tentar novamente.</p></section>', None, 429)
                name = text_field(fields, 'name', 150, True, 'nome')
                email = email_field(fields)
                password = password_field(fields, 'password')
                confirm = password_field(fields, 'confirm')
                if password != confirm:
                    raise ValidationError('A confirmação da senha não confere.')
                check_password_strength(password)
                if fields.get('consent') != '1':
                    raise ValidationError('É necessário aceitar o aviso de privacidade.')
                with db() as c:
                    try:
                        cursor = c.execute('INSERT INTO users(name,email,password,role,active) VALUES(?,?,?,?,1)', (name, email, pwd(password), 'client'))
                    except IntegrityError:
                        raise ValidationError('E-mail já cadastrado.')
                    account_id = cursor.lastrowid
                    sid = secrets.token_urlsafe(32)
                    moment = time.monotonic()
                    with SESS_LOCK:
                        SESS[sid] = {'uid': account_id, 'csrf': secrets.token_urlsafe(32), 'created': moment, 'last': moment}
                    self.audit_action(c, account_id, 'cadastro cliente', email, entity='user', entity_id=account_id, client_id=account_id, after={'name': name, 'email': email})
                    for admin_row in c.execute("SELECT id FROM users WHERE role='admin' AND is_super=1 AND active=1 AND deleted_at=''"):
                        notify(c, admin_row['id'], 'client', 'Novo cliente cadastrado', name + ' — ' + email, '/admin/clientes', account_id, None, 'registration-' + str(account_id) + '-u' + str(admin_row['id']))
                return self.redirect('/cliente', {'Set-Cookie': self.session_cookie(sid, SESSION_TTL)})
            data = self.session()
            if not data or not hmac.compare_digest(str(fields.get('csrf', '') or ''), data['csrf']):
                return self.forbidden()
            if not user:
                return self.forbidden()
            if path == '/notificacoes/ler':
                with db() as c:
                    if fields.get('all') == '1':
                        c.execute("UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND read_at=''", (user['id'],))
                    else:
                        notification_id = to_int(fields, 'id', required=False)
                        if notification_id:
                            c.execute("UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", (notification_id, user['id']))
                    unread = c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read_at=''", (user['id'],)).fetchone()[0]
                return self.send_json({'ok': True, 'unread': unread})
            if user['must_change'] and path != '/senha':
                return self.redirect('/senha')
            if path in ('/conversas/ler', '/conversas/responder', '/conversas/encerrar'):
                conversation_id = to_int(fields, 'conversation_id')
                with db() as c:
                    c.execute('BEGIN IMMEDIATE')
                    conversation = self.conversation_access(c, user, conversation_id)
                    if not conversation:
                        return self.forbidden()
                    if path == '/conversas/ler':
                        last_shown_id = to_int(fields, 'last_message_id', required=False, minvalue=0)
                        incoming = c.execute('SELECT id FROM messages WHERE conversation_id=? AND id<=? AND (sender_id IS NULL OR sender_id<>?)', (conversation_id, last_shown_id, user['id'])).fetchall()
                        for message in incoming:
                            c.execute('INSERT OR IGNORE INTO message_reads(user_id,message_id) VALUES(?,?)', (user['id'], message['id']))
                            keys = ('message-' + str(message['id']) + '-client', 'message-' + str(message['id']) + '-u' + str(user['id']), 'internal-' + str(message['id']) + '-u' + str(user['id']))
                            c.execute("UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND read_at='' AND dedupe_key IN (?,?,?)", (user['id'], *keys))
                        c.execute("UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND read_at='' AND url=? AND type NOT IN ('message','internal')", (user['id'], '/conversas/' + str(conversation_id)))
                        if user['role'] == 'client':
                            c.execute("UPDATE messages SET read_by_client=1 WHERE conversation_id=? AND id<=? AND sender_role!='client'", (conversation_id, last_shown_id))
                        conversation_counts = conversation_unread_totals(c, user)
                        unread_client = conversation_counts['client']
                        unread_internal = conversation_counts['internal']
                        remaining = unread_client + unread_internal
                        conversation_remaining = conversation_unread(c, user, conversation_id)
                        c.commit()
                        if 'application/json' in self.headers.get('Accept', ''):
                            return self.send_json({'ok': True, 'unread': remaining, 'unread_client': unread_client, 'unread_internal': unread_internal, 'conversation_unread': conversation_remaining})
                        return self.redirect('/conversas/' + str(conversation_id))
                    if not self.can_reply_conversation(c, user, conversation):
                        return self.forbidden()
                    if path == '/conversas/encerrar':
                        if user['role'] not in ('admin', 'staff'):
                            return self.forbidden()
                        c.execute("UPDATE conversations SET status='closed',closed_by=?,closed_at=CURRENT_TIMESTAMP,updated=CURRENT_TIMESTAMP WHERE id=? AND status='open'", (user['id'], conversation_id))
                        if conversation['visibility'] == 'client':
                            notify(c, conversation['client_id'], 'case', 'Conversa encerrada', conversation['title'], '/conversas/' + str(conversation_id), conversation['client_id'], conversation['case_id'], 'conversation-closed-' + str(conversation_id))
                        self.audit_action(c, user['id'], 'encerrar conversa', conversation['title'], entity='conversation', entity_id=conversation_id, client_id=conversation['client_id'], case_id=conversation['case_id'])
                    else:
                        filename, payload, _mime = files.get('file', ('', b'', ''))
                        has_attachment = bool(filename and payload)
                        body = text_field(fields, 'body', 5000, not has_attachment, 'mensagem')
                        stored = ''
                        temp = None
                        if has_attachment:
                            allowed = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.txt': 'text/plain'}
                            extension = Path(filename or '').suffix.lower()
                            if extension not in allowed or len(payload) > MAX_FILE:
                                raise ValidationError('Anexo inválido. Permitidos: PDF, PNG, JPG e TXT, até 10 MB.')
                            signatures = {'.pdf': payload.startswith(b'%PDF-'), '.png': payload.startswith(b'\x89PNG\r\n\x1a\n'), '.jpg': payload.startswith(b'\xff\xd8\xff'), '.jpeg': payload.startswith(b'\xff\xd8\xff'), '.txt': b'\x00' not in payload}
                            if not signatures[extension]:
                                raise ValidationError('O conteúdo do anexo não corresponde ao formato.')
                            stored = secrets.token_hex(24) + extension
                            temp = UP / (stored + '.tmp')
                            temp.write_bytes(payload)
                            if not scan_file(temp):
                                temp.unlink(missing_ok=True)
                                raise ValidationError('O anexo não passou na verificação de segurança.')
                        visibility = conversation['visibility']
                        reveal = 1 if user['role'] != 'client' and visibility == 'client' and fields.get('reveal_identity') == '1' else 0
                        cursor = c.execute('INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,reveal_identity,body,read_by_client,read_by_staff) VALUES(?,?,?,?,?,?,?,?,?,?)', (conversation['client_id'], conversation['case_id'], conversation_id, user['id'], user['role'], visibility, reveal, body, 1 if user['role'] == 'client' or visibility == 'internal' else 0, 1 if user['role'] != 'client' else 0))
                        message_id = cursor.lastrowid
                        if has_attachment:
                            os.replace(temp, UP / stored)
                            c.execute("INSERT INTO message_attachments(message_id,filename,stored,mime,size,uploaded_by) VALUES(?,?,?,?,?,?)", (message_id, Path(filename or '').name[:160], stored, allowed[extension], len(payload), user['id']))
                        c.execute('UPDATE conversations SET updated=CURRENT_TIMESTAMP WHERE id=?', (conversation_id,))
                        touch_case(c, conversation['case_id'])
                        if user['role'] == 'client' or visibility == 'internal':
                            for uid in client_audience(c, conversation['client_id'], conversation['case_id']):
                                if uid != user['id']:
                                    kind = 'internal' if visibility == 'internal' else 'message'
                                    notify(c, uid, kind, 'Novo relato interno' if kind == 'internal' else 'Nova mensagem de ' + user['name'], body[:200], '/conversas/' + str(conversation_id), conversation['client_id'], conversation['case_id'], kind + '-' + str(message_id) + '-u' + str(uid))
                            if visibility == 'internal':
                                for uid in mentioned_user_ids(c, body):
                                    c.execute('INSERT OR IGNORE INTO message_mentions(message_id,user_id) VALUES(?,?)', (message_id, uid))
                                    if uid != user['id']:
                                        notify(c, uid, 'mention', 'Você foi mencionado em uma conversa interna', body[:200], '/conversas/' + str(conversation_id), conversation['client_id'], conversation['case_id'], 'mention-' + str(message_id) + '-u' + str(uid))
                        else:
                            notify(c, conversation['client_id'], 'message', 'Nova mensagem do escritório', body[:200], '/conversas/' + str(conversation_id), conversation['client_id'], conversation['case_id'], 'message-' + str(message_id) + '-client')
                        self.audit_action(c, user['id'], 'responder conversa', conversation['title'], entity='conversation', entity_id=conversation_id, client_id=conversation['client_id'], case_id=conversation['case_id'])
                return self.redirect('/conversas/' + str(conversation_id))
            if path == '/sair':
                with SESS_LOCK:
                    for key, value in list(SESS.items()):
                        if value['uid'] == user['id']:
                            SESS.pop(key, None)
                with db() as c:
                    self.audit_action(c, user['id'], 'logout', user['email'])
                return self.redirect('/', {'Set-Cookie': self.session_cookie('', 0)})
            if path == '/senha':
                current = password_field(fields, 'current')
                new_password = password_field(fields, 'new')
                confirm = password_field(fields, 'confirm')
                check_password_strength(new_password)
                if new_password != confirm:
                    raise ValidationError('A confirmação da nova senha não confere.')
                if new_password == current:
                    raise ValidationError('A nova senha deve ser diferente da senha atual.')
                with db() as c:
                    account = c.execute('SELECT password FROM users WHERE id=?', (user['id'],)).fetchone()
                    if not account or not verify(current, account['password']):
                        raise ValidationError('Senha atual incorreta.')
                    c.execute('UPDATE users SET password=?,must_change=0 WHERE id=?', (pwd(new_password), user['id']))
                    self.audit_action(c, user['id'], 'alterar senha', user['email'], entity='user', entity_id=user['id'])
                return self.redirect('/admin' if user['role'] != 'client' else '/cliente')
            if path == '/perfil':
                name = text_field(fields, 'name', 150, True, 'nome')
                phone = text_field(fields, 'phone', 40)
                with db() as c:
                    current = c.execute('SELECT avatar,cover FROM users WHERE id=?', (user['id'],)).fetchone()
                    new_values = {'avatar': current['avatar'], 'cover': current['cover']}
                    for kind in ('avatar', 'cover'):
                        filename, payload, _mime = files.get(kind, ('', b'', ''))
                        if filename and payload:
                            extension = Path(filename).suffix.lower()
                            if extension not in ('.png', '.jpg', '.jpeg', '.webp') or len(payload) > MAX_FILE:
                                raise ValidationError('Use PNG, JPG ou WEBP de até 10 MB para foto e capa.')
                            signatures = {'.png': payload.startswith(b'\x89PNG\r\n\x1a\n'), '.jpg': payload.startswith(b'\xff\xd8\xff'), '.jpeg': payload.startswith(b'\xff\xd8\xff'), '.webp': payload.startswith(b'RIFF') and payload[8:12] == b'WEBP'}
                            if not signatures[extension]:
                                raise ValidationError('O conteúdo da imagem não corresponde ao formato.')
                            stored = 'perfil-' + kind + '-' + str(user['id']) + '-' + secrets.token_hex(12) + extension
                            temp = UP / (stored + '.tmp')
                            temp.write_bytes(payload)
                            if not scan_file(temp):
                                temp.unlink(missing_ok=True)
                                raise ValidationError('A imagem não passou na verificação de segurança.')
                            os.replace(temp, UP / stored)
                            old = new_values[kind]
                            new_values[kind] = stored
                            if old and old != stored:
                                (UP / old).unlink(missing_ok=True)
                        elif fields.get('remove_' + kind) == '1':
                            if new_values[kind]:
                                (UP / new_values[kind]).unlink(missing_ok=True)
                            new_values[kind] = ''
                    before = {'name': user['name'], 'phone': user['phone'], 'avatar': current['avatar'], 'cover': current['cover']}
                    c.execute('UPDATE users SET name=?,phone=?,avatar=?,cover=? WHERE id=?', (name, phone, new_values['avatar'], new_values['cover'], user['id']))
                    self.audit_action(c, user['id'], 'editar perfil', user['email'], entity='user', entity_id=user['id'], client_id=user['id'] if user['role'] == 'client' else None, before=before, after={'name': name, 'phone': phone, 'avatar': new_values['avatar'], 'cover': new_values['cover']})
                return self.redirect('/perfil')
            if path == '/cliente/perfil':
                if user['role'] != 'client':
                    return self.forbidden()
                name = text_field(fields, 'name', 150, True, 'nome')
                phone = text_field(fields, 'phone', 40)
                with db() as c:
                    before = {'name': user['name'], 'phone': user['phone']}
                    c.execute('UPDATE users SET name=?,phone=? WHERE id=?', (name, phone, user['id']))
                    self.audit_action(c, user['id'], 'editar perfil', user['email'], entity='user', entity_id=user['id'], client_id=user['id'], before=before, after={'name': name, 'phone': phone})
                return self.redirect('/cliente/perfil')
            if path == '/cliente/novo':
                if user['role'] != 'client':
                    return self.forbidden()
                subject = text_field(fields, 'subject', 200, True, 'assunto')
                description = text_field(fields, 'description', 10000, True, 'descrição')
                with db() as c:
                    cursor = c.execute("INSERT INTO cases(client_id,title,original_title,status,description,created_by,source,last_activity_at) VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)", (user['id'], subject, subject, 'Em andamento', description, user['id'], 'cliente'))
                    case_id = cursor.lastrowid
                    conversation_id = create_conversation(c, user['id'], case_id, subject, 'client', user['id'])
                    c.execute('INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,reveal_identity,body,read_by_client,read_by_staff) VALUES(?,?,?,?,?,?,?,?,1,0)', (user['id'], case_id, conversation_id, user['id'], 'client', 'client', 0, description))
                    case_event(c, case_id, user['id'], 'created', 'Atendimento aberto pelo cliente', visible_to_client=1)
                    for admin_row in c.execute("SELECT id FROM users WHERE role='admin' AND is_super=1 AND active=1 AND deleted_at=''"):
                        notify(c, admin_row['id'], 'case', 'Novo atendimento de ' + user['name'], subject, '/admin/casos', user['id'], case_id, 'new-case-' + str(case_id) + '-u' + str(admin_row['id']))
                    self.audit_action(c, user['id'], 'abrir atendimento', subject, entity='case', entity_id=case_id, client_id=user['id'], case_id=case_id, after={'title': subject, 'description': description})
                return self.redirect('/cliente')
            if path == '/cliente/mensagem':
                if user['role'] != 'client':
                    return self.forbidden()
                case_id = 0
                if str(fields.get('case_id', '')).strip():
                    case_id = to_int(fields, 'case_id')
                body = text_field(fields, 'body', 5000, True, 'mensagem')
                subject = text_field(fields, 'subject', 200, False, 'assunto')
                with db() as c:
                    if case_id and not self.can_access_case(c, user, case_id):
                        raise ValidationError('Caso inválido.')
                    case_row = c.execute('SELECT title FROM cases WHERE id=?', (case_id,)).fetchone() if case_id else None
                    conversation_id = create_conversation(c, user['id'], case_id, subject or (case_row['title'] if case_row else 'Contato geral'), 'client', user['id'])
                    cursor = c.execute('INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,reveal_identity,body,read_by_client,read_by_staff) VALUES(?,?,?,?,?,?,?,?,1,0)', (user['id'], case_id or None, conversation_id, user['id'], 'client', 'client', 0, body))
                    message_id = cursor.lastrowid
                    touch_case(c, case_id or None)
                    for uid in client_audience(c, user['id'], case_id or None):
                        if uid != user['id']:
                            notify(c, uid, 'message', 'Nova mensagem de ' + user['name'], body[:200], '/conversas/' + str(conversation_id), user['id'], case_id or None, 'message-' + str(message_id) + '-u' + str(uid))
                    self.audit_action(c, user['id'], 'mensagem ao escritório', body[:200], entity='message', client_id=user['id'], case_id=case_id or None)
                return self.redirect('/conversas/' + str(conversation_id))
            if path == '/cliente/solicitar':
                if user['role'] != 'client':
                    return self.forbidden()
                case_id = 0
                if str(fields.get('case_id', '')).strip():
                    case_id = to_int(fields, 'case_id')
                subject = text_field(fields, 'subject', 150, True, 'assunto')
                body = text_field(fields, 'body', 5000, True, 'mensagem')
                with db() as c:
                    if case_id and not self.can_access_case(c, user, case_id):
                        raise ValidationError('Caso inválido.')
                    cursor = c.execute('INSERT INTO requests(client_id,case_id,subject,body,last_activity_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)', (user['id'], case_id or None, subject, body))
                    request_id = cursor.lastrowid
                    touch_case(c, case_id or None)
                    for uid in client_audience(c, user['id'], case_id or None):
                        if uid != user['id']:
                            notify(c, uid, 'request', 'Nova solicitação de ' + user['name'], subject[:200], '/admin/solicitacoes?id=' + str(request_id), user['id'], case_id or None, 'request-' + str(request_id) + '-u' + str(uid))
                    self.audit_action(c, user['id'], 'criar solicitação', subject, entity='request', client_id=user['id'], case_id=case_id or None, after={'subject': subject, 'body': body})
                return self.redirect('/cliente')
            if path in ('/cliente/documento', '/admin/document'):
                if path.startswith('/cliente') and user['role'] != 'client':
                    return self.forbidden()
                if path.startswith('/admin') and user['role'] not in ('admin', 'staff'):
                    return self.forbidden()
                filename, payload, _mime = files.get('file', ('', b'', ''))
                allowed = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.txt': 'text/plain'}
                extension = Path(filename or '').suffix.lower()
                if extension not in allowed or not payload or len(payload) > MAX_FILE:
                    return self.error_page('Arquivo recusado', 'Permitidos: PDF, PNG, JPG e TXT, até 10 MB.', 400, user)
                signatures = {'.pdf': payload.startswith(b'%PDF-'), '.png': payload.startswith(b'\x89PNG\r\n\x1a\n'), '.jpg': payload.startswith(b'\xff\xd8\xff'), '.jpeg': payload.startswith(b'\xff\xd8\xff'), '.txt': b'\x00' not in payload}
                if not signatures[extension]:
                    return self.forbidden()
                client = user['id'] if user['role'] == 'client' else to_int(fields, 'client_id')
                stored = secrets.token_hex(24) + extension
                temp = UP / (stored + '.tmp')
                with db() as c:
                    if path.startswith('/admin') and not has_permission(c, user, 'manage_documents'):
                        return self.forbidden()
                    if not self.can_manage(c, user, client):
                        return self.forbidden()
                    case_id = 0
                    pendency_id = 0
                    pendency_row = None
                    if str(fields.get('case_id', '')).strip():
                        case_id = to_int(fields, 'case_id')
                        case_row = c.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
                        if not case_row or case_row['client_id'] != client or not self.can_access_case(c, user, case_id):
                            raise ValidationError('Caso inválido para este cliente.')
                    if path.startswith('/cliente') and str(fields.get('pendency_id', '')).strip():
                        pendency_id = to_int(fields, 'pendency_id')
                        pendency_row = c.execute("SELECT * FROM pendencies WHERE id=? AND client_id=? AND visible_to_client=1", (pendency_id, client)).fetchone()
                        if not pendency_row:
                            raise ValidationError('Pendência inválida.')
                        if pendency_row['case_id']:
                            if case_id and case_id != pendency_row['case_id']:
                                raise ValidationError('A pendência pertence a outro caso.')
                            case_id = pendency_row['case_id']
                            if not self.can_access_case(c, user, case_id):
                                raise ValidationError('Caso inválido para esta pendência.')
                    used = c.execute('SELECT COALESCE(SUM(size),0) FROM documents WHERE client_id=?', (client,)).fetchone()[0]
                    if used + len(payload) > MAX_CLIENT_STORAGE:
                        return self.error_page('Limite de armazenamento', 'O limite de armazenamento deste cliente foi atingido.', 400, user)
                    temp.write_bytes(payload)
                    if not scan_file(temp):
                        temp.unlink(missing_ok=True)
                        return self.error_page('Arquivo recusado', 'O arquivo não passou na verificação de segurança.', 400, user)
                    final = UP / stored
                    cursor = c.execute('INSERT INTO documents(client_id,case_id,filename,stored,mime,size,source,uploaded_by,seen_by_client,status) VALUES(?,?,?,?,?,?,?,?,?,?)', (client, case_id or None, Path(filename or '').name[:160], stored, allowed[extension], len(payload), 'cliente' if user['role'] == 'client' else 'escritório', user['id'], 1 if user['role'] == 'client' else 0, 'aguardando_analise' if user['role'] == 'client' else 'disponibilizado'))
                    document_id = cursor.lastrowid
                    touch_case(c, case_id or None)
                    if user['role'] == 'client':
                        if pendency_id:
                            for uid in client_audience(c, client, case_id or None):
                                if uid != user['id']:
                                    notify(c, uid, 'pendency', 'Pendência recebida', pendency_row['title'], '/admin/pendencias?id=' + str(pendency_id), client, case_id or None, 'pendency-received-' + str(pendency_id) + '-u' + str(uid))
                        else:
                            for uid in client_audience(c, client, case_id or None):
                                if uid != user['id']:
                                    notify(c, uid, 'document', 'Novo documento do cliente', Path(filename or '').name[:160], '/admin/documento?doc_id=' + str(document_id), client, case_id or None, 'doc-' + str(document_id) + '-u' + str(uid))
                    else:
                        notify(c, client, 'document', 'Novo documento disponível', Path(filename or '').name[:160], '/cliente', client, case_id or None, 'doc-' + str(document_id) + '-client')
                    if pendency_id:
                        c.execute("UPDATE pendencies SET status='Recebida', received_at=CURRENT_TIMESTAMP, document_id=? WHERE id=?", (document_id, pendency_id))
                        case_event(c, case_id or (pendency_row['case_id'] if pendency_row else None), user['id'], 'pendency', 'Documento da pendência enviado', visible_to_client=1)
                        self.audit_action(c, user['id'], 'documento de pendência', pendency_row['title'], entity='pendency', entity_id=pendency_id, client_id=client, case_id=case_id or None)
                    os.replace(temp, final)
                    self.audit_action(c, user['id'], 'documento', 'cliente=' + str(client) + ' arquivo=' + stored, entity='document', client_id=client, case_id=case_id or None, after={'filename': Path(filename or '').name[:160], 'source': 'cliente' if user['role'] == 'client' else 'escritório', 'case_id': case_id or None})
                if user['role'] == 'client':
                    return self.redirect('/cliente')
                self.flash('Documento enviado com sucesso.')
                return self.redirect(safe_admin_return(fields, '/admin/arquivos'))
            if user['role'] not in ('admin', 'staff') or not path.startswith('/admin/'):
                return self.forbidden()
            redirect_to = '/admin'
            with db() as c:
                if path == '/admin/compromisso/editar':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    appointment_id = to_int(fields, 'appointment_id')
                    appointment = c.execute("SELECT * FROM appointments WHERE id=? AND deleted_at=''", (appointment_id,)).fetchone()
                    if not appointment or not self.can_edit_appointment(c, user, appointment):
                        return self.forbidden()
                    title = text_field(fields, 'title', 150, True, 'título')
                    kind = str(fields.get('kind', 'compromisso'))
                    if kind not in TASK_KIND_LABELS:
                        raise ValidationError('Tipo de evento inválido.')
                    client = to_int(fields, 'client_id', required=False)
                    case_id = to_int(fields, 'case_id', required=False)
                    if case_id:
                        case_row = c.execute("SELECT * FROM cases WHERE id=? AND deleted_at=''", (case_id,)).fetchone()
                        if not case_row or not self.can_access_case(c, user, case_id):
                            raise ValidationError('Caso inválido.')
                        if client and case_row['client_id'] != client:
                            raise ValidationError('O caso não pertence ao cliente selecionado.')
                        client = case_row['client_id']
                    if client and not self.can_manage(c, user, client):
                        return self.forbidden()
                    owner_id = to_int(fields, 'owner_id', required=False) or user['id']
                    if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('admin','staff') AND active=1 AND deleted_at=''", (owner_id,)).fetchone():
                        raise ValidationError('Responsável inválido.')
                    raw_when = text_field(fields, 'when_at', 50, True, 'data e hora')
                    try:
                        when_dt = datetime.datetime.strptime(raw_when, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        raise ValidationError('Data e hora inválidas.')
                    location = text_field(fields, 'location', 300)
                    notes = text_field(fields, 'notes', 1000)
                    status = str(fields.get('status', appointment['status']))
                    if status not in ('pendente', 'realizado', 'cancelado'):
                        raise ValidationError('Situação inválida.')
                    reminder_choice = str(fields.get('reminder_choice', 'global'))
                    if reminder_choice not in ('none', '1h', '1d', 'global'):
                        raise ValidationError('Opção de lembrete inválida.')
                    privacy = str(fields.get('privacy', appointment['privacy'] or 'internal'))
                    if privacy not in ('private', 'internal', 'client'):
                        raise ValidationError('Privacidade inválida.')
                    participant_ids = selected_participant_ids(fields)
                    for participant_id in participant_ids:
                        if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('admin','staff') AND active=1 AND deleted_at=''", (participant_id,)).fetchone():
                            raise ValidationError('Participante inválido.')
                    when_at = when_dt.strftime('%Y-%m-%d %H:%M')
                    if reminder_choice == 'none':
                        reminder_at = ''
                    else:
                        reminder_hours = 24 if reminder_choice == '1d' else (1 if reminder_choice == '1h' else max(1, int(setting(c, 'appointment_reminder_hours', '24') or 24)))
                        reminder_at = (when_dt - datetime.timedelta(hours=reminder_hours)).strftime('%Y-%m-%d %H:%M')
                    c.execute("UPDATE appointments SET title=?,kind=?,client_id=?,case_id=?,owner_id=?,when_at=?,location=?,notes=?,status=?,reminder_choice=?,reminder_at=?,privacy=?,reminder_sent=0 WHERE id=?", (title, kind, client or None, case_id or None, owner_id, when_at, location, notes, status, reminder_choice, reminder_at, privacy, appointment_id))
                    c.execute('DELETE FROM appointment_participants WHERE appointment_id=?', (appointment_id,))
                    for participant_id in participant_ids:
                        c.execute('INSERT OR IGNORE INTO appointment_participants(appointment_id,user_id) VALUES(?,?)', (appointment_id, participant_id))
                    touch_case(c, case_id or None)
                    self.audit_action(c, user['id'], 'editar compromisso', title, entity='appointment', entity_id=appointment_id, client_id=client or None, case_id=case_id or None, before={'title': appointment['title'], 'when_at': appointment['when_at'], 'status': appointment['status'], 'owner_id': appointment['owner_id'], 'reminder_choice': appointment['reminder_choice'], 'privacy': appointment['privacy']}, after={'title': title, 'when_at': when_at, 'status': status, 'owner_id': owner_id, 'reminder_choice': reminder_choice, 'privacy': privacy, 'participants': participant_ids})
                    redirect_to = '/admin/compromisso?appointment_id=' + str(appointment_id)
                elif path == '/admin/compromisso/excluir':
                    appointment_id = to_int(fields, 'appointment_id')
                    appointment = c.execute("SELECT * FROM appointments WHERE id=? AND deleted_at=''", (appointment_id,)).fetchone()
                    if not appointment:
                        raise ValidationError('Evento não encontrado.')
                    private_owner = appointment['owner_id'] or appointment['created_by']
                    if (appointment['privacy'] or 'internal') == 'private' and private_owner != user['id']:
                        return self.forbidden()
                    if not (is_super(user) or appointment['created_by'] == user['id']):
                        return self.forbidden()
                    c.execute("UPDATE appointments SET deleted_at=CURRENT_TIMESTAMP,deleted_by=? WHERE id=?", (user['id'], appointment_id))
                    self.audit_action(c, user['id'], 'excluir compromisso', appointment['title'], entity='appointment', entity_id=appointment_id, client_id=appointment['client_id'], case_id=appointment['case_id'], before={'title': appointment['title'], 'when_at': appointment['when_at']})
                    redirect_to = '/admin/compromissos'
                elif path == '/admin/compromisso/status':
                    if user['role'] not in ('admin', 'staff') or not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    appointment_id = to_int(fields, 'appointment_id')
                    appointment = c.execute("SELECT * FROM appointments WHERE id=? AND deleted_at=''", (appointment_id,)).fetchone()
                    if not appointment:
                        raise ValidationError('Compromisso não encontrado.')
                    if not self.can_edit_appointment(c, user, appointment):
                        return self.forbidden()
                    status = str(fields.get('status', 'pendente'))
                    if status not in ('pendente', 'realizado', 'cancelado'):
                        raise ValidationError('Status de compromisso inválido.')
                    c.execute('UPDATE appointments SET status=? WHERE id=?', (status, appointment_id))
                    if appointment['case_id']:
                        case_event(c, appointment['case_id'], user['id'], 'appointment_status', 'Compromisso: ' + status, visible_to_client=1)
                        touch_case(c, appointment['case_id'])
                    if appointment['client_id']:
                        notify(c, appointment['client_id'], 'appointment', 'Compromisso atualizado', appointment['title'] + ' — ' + status, '/cliente/compromissos', appointment['client_id'], appointment['case_id'], 'appointment-status-' + str(appointment_id) + '-' + status + '-' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
                    self.audit_action(c, user['id'], 'alterar compromisso', appointment['title'], entity='appointment', entity_id=appointment_id, client_id=appointment['client_id'], case_id=appointment['case_id'], before={'status': appointment['status']}, after={'status': status})
                    redirect_to = '/admin/compromisso?appointment_id=' + str(appointment_id)
                elif path == '/admin/documento/status':
                    if user['role'] not in ('admin', 'staff') or not has_permission(c, user, 'manage_documents'):
                        return self.forbidden()
                    document_id = to_int(fields, 'doc_id')
                    document = c.execute("SELECT * FROM documents WHERE id=? AND deleted_at=''", (document_id,)).fetchone()
                    if not document:
                        raise ValidationError('Documento não encontrado.')
                    allowed = self.can_access_case(c, user, document['case_id']) if document['case_id'] else self.can_manage(c, user, document['client_id'])
                    if not allowed:
                        return self.forbidden()
                    status = str(fields.get('status', 'aguardando_analise'))
                    if status not in DOCUMENT_STATUS_LABELS:
                        raise ValidationError('Status de documento inválido.')
                    analysis_notes = text_field(fields, 'analysis_notes', 5000)
                    reviewed = 1 if status in ('analisado', 'aceito', 'disponibilizado') else 0
                    c.execute('UPDATE documents SET status=?,analysis_notes=?,reviewed=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?', (status, analysis_notes, reviewed, user['id'], document_id))
                    case_event(c, document['case_id'], user['id'], 'document_status', 'Documento ' + document['filename'] + ': ' + DOCUMENT_STATUS_LABELS[status], visible_to_client=1)
                    touch_case(c, document['case_id'])
                    notify(c, document['client_id'], 'document', 'Documento atualizado', document['filename'] + ' — ' + DOCUMENT_STATUS_LABELS[status], '/cliente/documentos', document['client_id'], document['case_id'], 'doc-status-' + str(document_id) + '-' + status + '-' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
                    self.audit_action(c, user['id'], 'analisar documento', document['filename'], entity='document', entity_id=document_id, client_id=document['client_id'], case_id=document['case_id'], after={'status': status, 'analysis_notes': analysis_notes})
                    redirect_to = '/admin/documento?doc_id=' + str(document_id)
                elif path == '/admin/pendencia':

                    if user['role'] not in ('admin', 'staff') or not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    client = to_int(fields, 'client_id')
                    if not self.can_manage(c, user, client):
                        return self.forbidden()
                    case_id = 0
                    if str(fields.get('case_id', '')).strip():
                        case_id = to_int(fields, 'case_id')
                        case_row = c.execute("SELECT * FROM cases WHERE id=? AND deleted_at=''", (case_id,)).fetchone()
                        if not case_row or case_row['client_id'] != client or not self.can_access_case(c, user, case_id):
                            raise ValidationError('Caso inválido para este cliente.')
                    title = text_field(fields, 'title', 200, True, 'título')
                    description = text_field(fields, 'description', 5000)
                    due_at = text_field(fields, 'due_at', 20)
                    cursor = c.execute("INSERT INTO pendencies(client_id,case_id,created_by,title,description,due_at,status) VALUES(?,?,?,?,?,?,'Aberta')", (client, case_id or None, user['id'], title, description, due_at))
                    pendency_id = cursor.lastrowid
                    case_event(c, case_id or None, user['id'], 'pendency', 'Pendência criada: ' + title, visible_to_client=1)
                    notify(c, client, 'pendency', 'Nova pendência', title, '/cliente/pendencias', client, case_id or None, 'pendency-' + str(pendency_id) + '-client')
                    self.audit_action(c, user['id'], 'criar pendência', title, entity='pendency', entity_id=pendency_id, client_id=client, case_id=case_id or None, after={'title': title, 'due_at': due_at})
                    redirect_to = '/admin/pendencias'
                elif path == '/admin/pendencia/status':
                    if user['role'] not in ('admin', 'staff') or not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    pendency_id = to_int(fields, 'pendency_id')
                    pendency = c.execute('SELECT * FROM pendencies WHERE id=?', (pendency_id,)).fetchone()
                    if not pendency:
                        raise ValidationError('Pendência não encontrada.')
                    if not self.can_manage(c, user, pendency['client_id']):
                        return self.forbidden()
                    status = str(fields.get('status', 'Aberta'))
                    if status not in ('Aberta', 'Recebida', 'Em análise', 'Atendida'):
                        raise ValidationError('Status de pendência inválido.')
                    review_notes = text_field(fields, 'review_notes', 5000)
                    c.execute('UPDATE pendencies SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP,review_notes=? WHERE id=?', (status, user['id'], review_notes, pendency_id))
                    case_event(c, pendency['case_id'], user['id'], 'pendency_status', 'Pendência: ' + status, visible_to_client=1)
                    notify(c, pendency['client_id'], 'pendency', 'Pendência atualizada', pendency['title'] + ' — ' + status, '/cliente/pendencias', pendency['client_id'], pendency['case_id'], 'pendency-status-' + str(pendency_id) + '-' + status + '-' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
                    self.audit_action(c, user['id'], 'analisar pendência', pendency['title'], entity='pendency', entity_id=pendency_id, client_id=pendency['client_id'], case_id=pendency['case_id'], after={'status': status, 'review_notes': review_notes})
                    redirect_to = '/admin/pendencias'
                elif path == '/admin/atendimento-visitante/responder' or path == '/admin/atendimento-visitante/encerrar':
                    if user['role'] not in ('admin', 'staff'):
                        return self.forbidden()
                    guest_id = to_int(fields, 'guest_id')
                    session = c.execute('SELECT * FROM guest_sessions WHERE id=?', (guest_id,)).fetchone()
                    if not session:
                        raise ValidationError('Atendimento não encontrado.')
                    if path.endswith('/responder'):
                        if session['status'] != 'open':
                            raise ValidationError('Este atendimento está encerrado.')
                        body = text_field(fields, 'body', 3000, True, 'resposta')
                        c.execute("INSERT INTO guest_messages(guest_id,sender_role,sender_id,body,read_by_staff) VALUES(?,'staff',?,?,1)", (guest_id, user['id'], body))
                        c.execute('UPDATE guest_sessions SET updated=CURRENT_TIMESTAMP WHERE id=?', (guest_id,))
                        if session['contact_id']:
                            c.execute("UPDATE contacts SET status=CASE WHEN status='novo' THEN 'em_atendimento' ELSE status END,responsible_id=COALESCE(responsible_id,?),updated=CURRENT_TIMESTAMP WHERE id=?", (user['id'], session['contact_id']))
                        self.audit_action(c, user['id'], 'responder visitante', session['name'], entity='guest_session', entity_id=guest_id, after={'body': body[:200]})
                        redirect_to = '/admin/atendimento-visitante?guest_id=' + str(guest_id)
                    else:
                        c.execute("UPDATE guest_sessions SET status='closed',updated=CURRENT_TIMESTAMP WHERE id=?", (guest_id,))
                        if session['contact_id']:
                            c.execute("UPDATE contacts SET status='respondido',updated=CURRENT_TIMESTAMP WHERE id=?", (session['contact_id'],))
                        self.audit_action(c, user['id'], 'encerrar atendimento visitante', session['name'], entity='guest_session', entity_id=guest_id, before={'status': session['status']}, after={'status': 'closed'})
                        redirect_to = '/admin/contatos'
                elif path == '/admin/contato/status':
                    if not is_super(user):
                        return self.forbidden()
                    contact_id = to_int(fields, 'contact_id')
                    contact = c.execute('SELECT * FROM contacts WHERE id=?', (contact_id,)).fetchone()
                    if not contact:
                        raise ValidationError('Contato não encontrado.')
                    status = str(fields.get('status', ''))
                    if status not in ('novo', 'em_atendimento', 'respondido', 'nao_classificado'):
                        raise ValidationError('Situação do contato inválida.')
                    raw_responsible = str(fields.get('responsible_id', '')).strip()
                    responsible = to_int(fields, 'responsible_id') if raw_responsible else None
                    if responsible and not c.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND is_super=1 AND active=1 AND deleted_at=''", (responsible,)).fetchone():
                        raise ValidationError('Responsável inválido.')
                    c.execute('UPDATE contacts SET status=?,responsible_id=?,updated=CURRENT_TIMESTAMP WHERE id=?', (status, responsible, contact_id))
                    c.execute("UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND dedupe_key=? AND read_at=''", (user['id'], 'contact-' + str(contact_id) + '-u' + str(user['id'])))
                    self.audit_action(c, user['id'], 'atualizar contato', contact['name'], entity='contact', entity_id=contact_id, before={'status': contact['status'], 'responsible_id': contact['responsible_id']}, after={'status': status, 'responsible_id': responsible})
                    redirect_to = '/admin/contatos'
                elif path == '/admin/cliente/interno':
                    if user['role'] not in ('admin', 'staff') or not has_permission(c, user, 'create_clients'):
                        return self.forbidden()
                    name = text_field(fields, 'name', 150, True, 'nome')
                    phone = text_field(fields, 'phone', 40)
                    owner = user['id'] if user['role'] == 'staff' else 0
                    if user['role'] == 'admin' and str(fields.get('owner_staff_id', '')).strip():
                        owner = to_int(fields, 'owner_staff_id')
                        if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('staff','admin') AND deleted_at=''", (owner,)).fetchone():
                            raise ValidationError('Responsável inválido.')
                    placeholder = 'cliente-' + secrets.token_hex(12) + '@interno.local'
                    cursor = c.execute('INSERT INTO users(name,email,password,role,active,must_change,portal_enabled,phone,created_by,owner_staff_id) VALUES(?,?,?,?,1,0,0,?,?,?)', (name, placeholder, pwd(secrets.token_urlsafe(24)), 'client', phone, user['id'], owner or None))
                    new_client = cursor.lastrowid
                    if owner:
                        c.execute('INSERT OR IGNORE INTO assignments(staff_id,client_id) VALUES(?,?)', (owner, new_client))
                    self.audit_action(c, user['id'], 'criar cliente interno', name, entity='user', entity_id=new_client, client_id=new_client, after={'name': name, 'phone': phone, 'portal_enabled': 0, 'owner_staff_id': owner or None})
                    redirect_to = '/admin/cliente?client_id=' + str(new_client)
                elif path == '/admin/cliente':
                    if user['role'] not in ('admin', 'staff') or not has_permission(c, user, 'create_clients'):
                        return self.forbidden()
                    name = text_field(fields, 'name', 150, True, 'nome')
                    email = email_field(fields)
                    phone = text_field(fields, 'phone', 40)
                    password = password_field(fields, 'password')
                    confirm = password_field(fields, 'confirm')
                    if password != confirm:
                        raise ValidationError('A confirmação da senha não confere.')
                    check_password_strength(password)
                    owner = user['id'] if user['role'] == 'staff' else 0
                    if user['role'] == 'admin' and str(fields.get('owner_staff_id', '')).strip():
                        owner = to_int(fields, 'owner_staff_id')
                        if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('staff','admin') AND deleted_at=''", (owner,)).fetchone():
                            raise ValidationError('Responsável inválido.')
                    try:
                        cursor = c.execute('INSERT INTO users(name,email,password,role,active,must_change,phone,created_by,owner_staff_id) VALUES(?,?,?,?,1,1,?,?,?)', (name, email, pwd(password), 'client', phone, user['id'], owner or None))
                    except IntegrityError:
                        raise ValidationError('E-mail já cadastrado.')
                    new_client = cursor.lastrowid
                    if owner:
                        c.execute('INSERT OR IGNORE INTO assignments(staff_id,client_id) VALUES(?,?)', (owner, new_client))
                    self.audit_action(c, user['id'], 'criar cliente', email, entity='user', entity_id=new_client, client_id=new_client, after={'name': name, 'email': email, 'phone': phone, 'owner_staff_id': owner or None})
                    redirect_to = '/admin/clientes'
                elif path == '/admin/cliente/portal':
                    if not has_permission(c, user, 'create_clients'):
                        return self.forbidden()
                    client = to_int(fields, 'client_id')
                    client_row = c.execute("SELECT * FROM users WHERE id=? AND role='client' AND deleted_at=''", (client,)).fetchone()
                    if not client_row or not self.can_manage(c, user, client):
                        return self.forbidden()
                    email = email_field(fields)
                    password = password_field(fields, 'password')
                    confirm = password_field(fields, 'confirm')
                    if password != confirm:
                        raise ValidationError('A confirmação da senha não confere.')
                    check_password_strength(password)
                    if c.execute('SELECT 1 FROM users WHERE email=? AND id<>?', (email, client)).fetchone():
                        raise ValidationError('Este e-mail já está vinculado a outra conta.')
                    c.execute('UPDATE users SET email=?,password=?,portal_enabled=1,must_change=1,active=1 WHERE id=?', (email, pwd(password), client))
                    self.audit_action(c, user['id'], 'habilitar acesso ao portal', client_row['name'], entity='user', entity_id=client, client_id=client, before={'portal_enabled': client_row['portal_enabled'], 'email': client_row['email']}, after={'portal_enabled': 1, 'email': email})
                    redirect_to = '/admin/cliente?client_id=' + str(client)
                elif path == '/admin/cliente/editar':
                    if not has_permission(c, user, 'create_clients'):
                        return self.forbidden()
                    client = to_int(fields, 'client_id')
                    client_row = c.execute("SELECT * FROM users WHERE id=? AND role='client' AND deleted_at=''", (client,)).fetchone()
                    if not client_row:
                        raise ValidationError('Cliente não encontrado.')
                    if not self.can_manage(c, user, client):
                        return self.forbidden()
                    name = text_field(fields, 'name', 150, True, 'nome')
                    phone = text_field(fields, 'phone', 40)
                    active = 1 if fields.get('active') == '1' else 0
                    email = client_row['email']
                    owner = client_row['owner_staff_id']
                    if user['role'] == 'admin':
                        email = email_field(fields) if str(fields.get('email', '')).strip() else client_row['email']
                        raw_owner = str(fields.get('owner_staff_id', '')).strip()
                        owner = to_int(fields, 'owner_staff_id') if raw_owner else None
                        if owner and not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('staff','admin') AND deleted_at=''", (owner,)).fetchone():
                            raise ValidationError('Responsável inválido.')
                    before = {k: client_row[k] for k in ('name', 'email', 'phone', 'active', 'owner_staff_id')}
                    try:
                        c.execute('UPDATE users SET name=?,email=?,phone=?,active=?,owner_staff_id=? WHERE id=?', (name, email, phone, active, owner, client))
                    except IntegrityError:
                        raise ValidationError('E-mail já cadastrado.')
                    if user['role'] == 'admin':
                        if owner:
                            c.execute('INSERT OR IGNORE INTO assignments(staff_id,client_id) VALUES(?,?)', (owner, client))
                    new_password = fields.get('password', '')
                    if new_password:
                        password = password_field(fields, 'password')
                        check_password_strength(password)
                        c.execute('UPDATE users SET password=?,must_change=1 WHERE id=?', (pwd(password), client))
                    self.audit_action(c, user['id'], 'editar cliente', email, entity='user', entity_id=client, client_id=client, before=before, after={'name': name, 'email': email, 'phone': phone, 'active': active, 'owner_staff_id': owner})
                    redirect_to = '/admin/clientes'
                elif path == '/admin/delete':
                    if not is_super(user):
                        return self.forbidden()
                    entity = str(fields.get('entity', ''))
                    record_id = to_int(fields, 'record_id')
                    if entity == 'client':
                        row = c.execute("SELECT * FROM users WHERE id=? AND role='client' AND deleted_at=''", (record_id,)).fetchone()
                    elif entity == 'case':
                        row = c.execute("SELECT * FROM cases WHERE id=? AND deleted_at=''", (record_id,)).fetchone()
                    elif entity == 'document':
                        row = c.execute("SELECT * FROM documents WHERE id=? AND deleted_at=''", (record_id,)).fetchone()
                    else:
                        raise ValidationError('Registro inválido.')
                    if not row:
                        raise ValidationError('Registro não encontrado ou já excluído.')
                    before = {k: row[k] for k in row.keys() if k not in ('password',)}
                    c.execute("UPDATE " + {'client': 'users', 'case': 'cases', 'document': 'documents'}[entity] + " SET deleted_at=CURRENT_TIMESTAMP,deleted_by=? WHERE id=?", (user['id'], record_id))
                    self.audit_action(c, user['id'], 'mover para lixeira', entity + ' #' + str(record_id), entity=entity, entity_id=record_id, client_id=row['id'] if entity == 'client' else row['client_id'], case_id=row['id'] if entity == 'case' else row['case_id'] if entity == 'document' else None, before=before)
                    redirect_to = '/admin/lixeira'
                elif path == '/admin/restore':
                    if not is_super(user):
                        return self.forbidden()
                    entity = str(fields.get('entity', ''))
                    record_id = to_int(fields, 'record_id')
                    table = {'client': 'users', 'case': 'cases', 'document': 'documents'}.get(entity)
                    if not table:
                        raise ValidationError('Registro inválido.')
                    row = c.execute('SELECT * FROM ' + table + " WHERE id=? AND deleted_at<>''", (record_id,)).fetchone()
                    if not row:
                        raise ValidationError('Registro não encontrado na lixeira.')
                    c.execute('UPDATE ' + table + " SET deleted_at='',deleted_by=NULL WHERE id=?", (record_id,))
                    self.audit_action(c, user['id'], 'restaurar registro', entity + ' #' + str(record_id), entity=entity, entity_id=record_id, client_id=row['id'] if entity == 'client' else row['client_id'], case_id=row['id'] if entity == 'case' else row['case_id'] if entity == 'document' else None, after={'restored': True})
                    redirect_to = '/admin/lixeira'
                elif path == '/admin/purge':
                    if not is_super(user):
                        return self.forbidden()
                    if str(fields.get('confirm', '')).strip() != 'EXCLUIR':
                        raise ValidationError('Digite EXCLUIR para confirmar a exclusão definitiva.')
                    entity = str(fields.get('entity', ''))
                    record_id = to_int(fields, 'record_id')
                    if entity == 'document':
                        row = c.execute("SELECT * FROM documents WHERE id=? AND deleted_at<>''", (record_id,)).fetchone()
                        if not row:
                            raise ValidationError('Documento não encontrado na lixeira.')
                        before = dict(row)
                        if row['stored']:
                            try:
                                (UP / row['stored']).unlink()
                            except OSError:
                                pass
                        c.execute('DELETE FROM documents WHERE id=?', (record_id,))
                        self.audit_action(c, user['id'], 'excluir definitivamente', row['filename'], entity='document', entity_id=record_id, client_id=row['client_id'], case_id=row['case_id'], before=before)
                    elif entity == 'case':
                        row = c.execute("SELECT * FROM cases WHERE id=? AND deleted_at<>''", (record_id,)).fetchone()
                        if not row:
                            raise ValidationError('Caso não encontrado na lixeira.')
                        before = dict(row)
                        documents = c.execute('SELECT stored FROM documents WHERE case_id=?', (record_id,)).fetchall()
                        for document in documents:
                            if document['stored']:
                                try:
                                    (UP / document['stored']).unlink()
                                except OSError:
                                    pass
                        self.audit_action(c, user['id'], 'excluir definitivamente', 'Caso #' + str(record_id), entity='case', entity_id=record_id, client_id=row['client_id'], case_id=record_id, before=before)
                        for table in ('notifications', 'pendencies', 'documents', 'messages', 'requests', 'updates', 'appointments', 'case_events', 'case_assignments'):
                            c.execute('DELETE FROM ' + table + ' WHERE case_id=?', (record_id,))
                        c.execute('DELETE FROM cases WHERE id=?', (record_id,))
                    elif entity == 'client':
                        row = c.execute("SELECT * FROM users WHERE id=? AND role='client' AND deleted_at<>''", (record_id,)).fetchone()
                        if not row:
                            raise ValidationError('Cliente não encontrado na lixeira.')
                        before = {k: row[k] for k in row.keys() if k != 'password'}
                        documents = c.execute('SELECT stored FROM documents WHERE client_id=?', (record_id,)).fetchall()
                        for document in documents:
                            if document['stored']:
                                try:
                                    (UP / document['stored']).unlink()
                                except OSError:
                                    pass
                        self.audit_action(c, user['id'], 'excluir definitivamente', row['email'], entity='user', entity_id=record_id, client_id=record_id, before=before)
                        c.execute('DELETE FROM notifications WHERE user_id=? OR client_id=?', (record_id, record_id))
                        c.execute('DELETE FROM pendencies WHERE client_id=?', (record_id,))
                        c.execute('DELETE FROM documents WHERE client_id=?', (record_id,))
                        c.execute('DELETE FROM messages WHERE client_id=?', (record_id,))
                        c.execute('DELETE FROM requests WHERE client_id=?', (record_id,))
                        c.execute('DELETE FROM updates WHERE client_id=?', (record_id,))
                        c.execute('DELETE FROM appointments WHERE client_id=?', (record_id,))
                        c.execute('DELETE FROM case_events WHERE case_id IN (SELECT id FROM cases WHERE client_id=?) OR actor_id=?', (record_id, record_id))
                        c.execute('DELETE FROM case_assignments WHERE case_id IN (SELECT id FROM cases WHERE client_id=?)', (record_id,))
                        c.execute('DELETE FROM cases WHERE client_id=?', (record_id,))
                        c.execute('DELETE FROM assignments WHERE client_id=?', (record_id,))
                        c.execute('DELETE FROM users WHERE id=?', (record_id,))
                    else:
                        raise ValidationError('Registro inválido.')
                    redirect_to = '/admin/lixeira'
                elif path == '/admin/permissoes':
                    if not is_super(user):
                        return self.forbidden()
                    target = to_int(fields, 'user_id')
                    target_row = c.execute("SELECT * FROM users WHERE id=? AND role IN ('admin','staff') AND deleted_at=''", (target,)).fetchone()
                    if not target_row:
                        raise ValidationError('Usuário inválido.')
                    before = {r['action']: r['allowed'] for r in c.execute('SELECT action,allowed FROM permissions WHERE user_id=?', (target,))}
                    after = {}
                    for action, label in PERMISSION_ACTIONS:
                        allowed = 1 if fields.get(action) == '1' else 0
                        after[action] = allowed
                        c.execute('INSERT INTO permissions(user_id,action,allowed,created_by) VALUES(?,?,?,?) ON CONFLICT(user_id,action) DO UPDATE SET allowed=excluded.allowed, created_by=excluded.created_by', (target, action, allowed, user['id']))
                    self.audit_action(c, user['id'], 'alterar permissões', target_row['email'], entity='user', entity_id=target, before=before, after=after)
                    redirect_to = '/admin/permissoes'
                elif path == '/admin/configuracoes':
                    if not is_super(user):
                        return self.forbidden()
                    unread_hours = to_int(fields, 'unread_hours')
                    stale_hours = to_int(fields, 'stale_hours')
                    reminder_hours = to_int(fields, 'appointment_reminder_hours')
                    for key, value in [('unread_hours', unread_hours), ('stale_hours', stale_hours), ('appointment_reminder_hours', reminder_hours), ('email_notifications', '1' if fields.get('email_notifications') == '1' else '0'), ('chat_online', '1' if fields.get('chat_online') == '1' else '0')]:
                        c.execute("INSERT INTO settings(key,value,updated_by,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP", (key, str(value), user['id']))
                    self.audit_action(c, user['id'], 'alterar configurações', 'parâmetros gerais', entity='settings', after={'unread_hours': unread_hours, 'stale_hours': stale_hours, 'appointment_reminder_hours': reminder_hours, 'email_notifications': fields.get('email_notifications') == '1', 'chat_online': fields.get('chat_online') == '1'})
                    redirect_to = '/admin/configuracoes'
                elif path == '/admin/caso/equipe':
                    if not (is_super(user) or user['role'] == 'admin') or not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    case_id = to_int(fields, 'case_id')
                    staff_id = to_int(fields, 'staff_id')
                    case_row = c.execute("SELECT * FROM cases WHERE id=? AND deleted_at=''", (case_id,)).fetchone()
                    if not case_row:
                        raise ValidationError('Caso não encontrado.')
                    operation = str(fields.get('operation', ''))
                    if operation == 'add':
                        person = c.execute("SELECT id,name FROM users WHERE id=? AND role IN ('admin','staff') AND active=1 AND deleted_at=''", (staff_id,)).fetchone()
                        if not person:
                            raise ValidationError('Profissional inválido.')
                        c.execute('INSERT OR IGNORE INTO case_assignments(case_id,staff_id) VALUES(?,?)', (case_id, staff_id))
                        if c.execute('SELECT changes()').fetchone()[0]:
                            case_event(c, case_id, user['id'], 'assignment', 'Profissional vinculado: ' + person['name'], visible_to_client=0)
                            if staff_id != user['id']:
                                notify(c, staff_id, 'case', 'Você foi vinculado a um atendimento', case_row['title'], '/admin/caso/historico?case_id=' + str(case_id), case_row['client_id'], case_id, 'case-team-' + str(case_id) + '-' + str(staff_id) + '-' + str(time.time_ns()))
                    elif operation == 'remove':
                        if case_row['responsible_id'] == staff_id:
                            raise ValidationError('Altere o responsável principal antes de remover este vínculo.')
                        cursor = c.execute('DELETE FROM case_assignments WHERE case_id=? AND staff_id=?', (case_id, staff_id))
                        if not cursor.rowcount:
                            raise ValidationError('Vínculo não encontrado.')
                        case_event(c, case_id, user['id'], 'assignment', 'Vínculo de profissional removido', visible_to_client=0)
                    else:
                        raise ValidationError('Operação inválida.')
                    self.audit_action(c, user['id'], 'alterar equipe do caso', operation, entity='case', entity_id=case_id, client_id=case_row['client_id'], case_id=case_id, after={'operation': operation, 'staff_id': staff_id})
                    redirect_to = '/admin/caso/historico?case_id=' + str(case_id)
                elif path == '/admin/caso':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    client = to_int(fields, 'client_id')
                    if not self.can_manage(c, user, client):
                        return self.forbidden()
                    title = text_field(fields, 'title', 200, True, 'título do caso')
                    case_number = text_field(fields, 'case_number', 80)
                    area = text_field(fields, 'area', 80)
                    status = str(fields.get('status', 'Em andamento'))
                    if status not in ('Em andamento', 'Aguardando cliente', 'Concluído', 'Informativo', 'Suspenso'):
                        raise ValidationError('Status de caso inválido.')
                    description = text_field(fields, 'description', 10000)
                    responsible_id = user['id'] if user['role'] == 'staff' else 0
                    if user['role'] == 'admin' and str(fields.get('responsible_id', '')).strip():
                        responsible_id = to_int(fields, 'responsible_id')
                        if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('staff','admin') AND active=1 AND deleted_at=''", (responsible_id,)).fetchone():
                            raise ValidationError('Responsável inválido.')
                    cursor = c.execute("INSERT INTO cases(client_id,title,original_title,case_number,area,status,description,responsible_id,created_by,source) VALUES(?,?,?,?,?,?,?,?,?,'interno')", (client, title, title, case_number, area, status, description, responsible_id or None, user['id']))
                    case_id = cursor.lastrowid
                    if responsible_id:
                        c.execute('INSERT OR IGNORE INTO case_assignments(case_id,staff_id) VALUES(?,?)', (case_id, responsible_id))
                    case_event(c, case_id, user['id'], 'created', 'Atendimento criado pelo escritório', visible_to_client=1)
                    if responsible_id:
                        case_event(c, case_id, user['id'], 'assignment', 'Responsável atribuído', visible_to_client=0)
                    touch_case(c, case_id)
                    notify(c, client, 'case', 'Novo atendimento registrado', title, '/cliente', client, case_id, 'case-' + str(case_id) + '-client')
                    created_case = c.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
                    for uid in case_audience(c, created_case):
                        if uid != user['id']:
                            notify(c, uid, 'case', 'Novo atendimento atribuído', title, '/admin/casos', client, case_id, 'case-' + str(case_id) + '-u' + str(uid))
                    self.audit_action(c, user['id'], 'criar caso', title, entity='case', entity_id=case_id, client_id=client, case_id=case_id, after={'title': title, 'status': status, 'responsible_id': responsible_id or None})
                    redirect_to = '/admin/casos'
                elif path == '/admin/caso/editar':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    case_id = to_int(fields, 'case_id')
                    case_row = c.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
                    if not case_row:
                        raise ValidationError('Caso não encontrado.')
                    if user['role'] == 'client' or not self.can_access_case(c, user, case_id):
                        return self.forbidden()
                    title = text_field(fields, 'title', 200, True, 'título do caso')
                    case_number = text_field(fields, 'case_number', 80)
                    area = text_field(fields, 'area', 80)
                    status = str(fields.get('status', 'Em andamento'))
                    if status not in ('Em andamento', 'Aguardando cliente', 'Concluído', 'Informativo', 'Suspenso'):
                        raise ValidationError('Status de caso inválido.')
                    description = text_field(fields, 'description', 10000)
                    responsible_id = case_row['responsible_id']
                    if user['role'] == 'admin':
                        raw_responsible = str(fields.get('responsible_id', '')).strip()
                        responsible_id = to_int(fields, 'responsible_id') if raw_responsible else None
                        if responsible_id and responsible_id != case_row['responsible_id'] and not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('staff','admin') AND active=1 AND deleted_at=''", (responsible_id,)).fetchone():
                            raise ValidationError('Responsável inválido.')
                        if responsible_id:
                            c.execute('INSERT OR IGNORE INTO case_assignments(case_id,staff_id) VALUES(?,?)', (case_id, responsible_id))
                    before = {k: case_row[k] for k in ('title', 'case_number', 'area', 'status', 'description', 'responsible_id')}
                    c.execute('UPDATE cases SET title=?,case_number=?,area=?,status=?,description=?,responsible_id=?,updated=CURRENT_TIMESTAMP,last_activity_at=CURRENT_TIMESTAMP WHERE id=?', (title, case_number, area, status, description, responsible_id, case_id))
                    if case_row['title'] != title:
                        case_event(c, case_id, user['id'], 'rename', 'Título alterado', old_title=case_row['title'], new_title=title, visible_to_client=0)
                    if case_row['status'] != status:
                        case_event(c, case_id, user['id'], 'status', 'Status alterado', from_status=case_row['status'], to_status=status, visible_to_client=1)
                    if responsible_id != case_row['responsible_id']:
                        case_event(c, case_id, user['id'], 'assignment', 'Responsável alterado', visible_to_client=0)
                    change_stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                    if case_row['status'] != status:
                        notify(c, case_row['client_id'], 'case', 'Atualização no atendimento', 'Status: ' + status, '/cliente', case_row['client_id'], case_id, 'case-status-' + str(case_id) + '-' + status + '-' + change_stamp)
                    if responsible_id and responsible_id != case_row['responsible_id']:
                        notify(c, responsible_id, 'case', 'Caso atribuído a você', title, '/admin/casos', case_row['client_id'], case_id, 'case-assign-' + str(case_id) + '-' + str(responsible_id) + '-' + change_stamp)
                    self.audit_action(c, user['id'], 'editar caso', title, entity='case', entity_id=case_id, client_id=case_row['client_id'], case_id=case_id, before=before, after={'title': title, 'case_number': case_number, 'area': area, 'status': status, 'description': description, 'responsible_id': responsible_id})
                    redirect_to = '/admin/casos'
                elif path == '/admin/seguranca/iniciar':
                    if not is_super(user):
                        return self.forbidden()
                    with db() as c:
                        account = c.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
                        if account['totp_enabled']:
                            return self.security_page(user, c, message='O MFA já está ativado. Desative-o antes de gerar uma nova chave.')
                        secret = totp_secret()
                        c.execute("UPDATE users SET totp_secret=?,totp_enabled=0,totp_last_step=0,recovery_codes='',recovery_generated_at='' WHERE id=?", (secret, user['id']))
                        self.audit_action(c, user['id'], 'iniciar configuração de MFA', user['email'], entity='user', entity_id=user['id'])
                    redirect_to = '/admin/seguranca'
                elif path == '/admin/seguranca/confirmar':
                    if not is_super(user):
                        return self.forbidden()
                    code = text_field(fields, 'code', 20, True, 'código')
                    with db() as c:
                        account = c.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
                        if account['totp_enabled']:
                            return self.security_page(user, c, message='O MFA já está ativado.')
                        if not account['totp_secret']:
                            return self.security_page(user, c, message='Gere uma nova chave para iniciar a configuração.')
                        step = verify_totp(account['totp_secret'], code, 0)
                        if not step:
                            return self.security_page(user, c, message='Código inválido ou expirado. Confira o horário do dispositivo e tente novamente.')
                        codes = new_recovery_codes()
                        hashes = [recovery_hash(item) for item in codes]
                        c.execute("UPDATE users SET totp_enabled=1,totp_confirmed_at=CURRENT_TIMESTAMP,totp_last_step=0,recovery_codes=?,recovery_generated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(hashes), user['id']))
                        self.audit_action(c, user['id'], 'ativar MFA', user['email'], entity='user', entity_id=user['id'])
                        c.commit()
                        return self.security_page(user, c, codes=codes, message='MFA ativado com sucesso. Guarde os códigos de recuperação agora.')
                elif path == '/admin/seguranca/desativar':
                    if not is_super(user):
                        return self.forbidden()
                    current = password_field(fields, 'password')
                    code = text_field(fields, 'code', 20, True, 'código')
                    with db() as c:
                        account = c.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
                        if not account['totp_enabled']:
                            return self.security_page(user, c, message='O MFA não está ativado.')
                        if not verify(current, account['password']):
                            return self.security_page(user, c, message='Senha atual incorreta.')
                        if not verify_totp(account['totp_secret'], code, 0):
                            return self.security_page(user, c, message='Código do app inválido ou expirado.')
                        c.execute("UPDATE users SET totp_secret='',totp_enabled=0,totp_last_step=0,totp_confirmed_at='',recovery_codes='',recovery_generated_at='' WHERE id=?", (user['id'],))
                        self.audit_action(c, user['id'], 'desativar MFA', user['email'], entity='user', entity_id=user['id'])
                    redirect_to = '/admin/seguranca'
                elif path == '/admin/seguranca/recuperacao':
                    if not is_super(user):
                        return self.forbidden()
                    current = password_field(fields, 'password')
                    code = text_field(fields, 'code', 20, True, 'código')
                    with db() as c:
                        account = c.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
                        if not account['totp_enabled']:
                            return self.security_page(user, c, message='Ative o MFA antes de gerar códigos de recuperação.')
                        if not verify(current, account['password']):
                            return self.security_page(user, c, message='Senha atual incorreta.')
                        if not verify_totp(account['totp_secret'], code, 0):
                            return self.security_page(user, c, message='Código do app inválido ou expirado.')
                        codes = new_recovery_codes()
                        hashes = [recovery_hash(item) for item in codes]
                        c.execute('UPDATE users SET recovery_codes=?,recovery_generated_at=CURRENT_TIMESTAMP WHERE id=?', (json.dumps(hashes), user['id']))
                        self.audit_action(c, user['id'], 'regenerar códigos de recuperação MFA', user['email'], entity='user', entity_id=user['id'])
                        c.commit()
                        return self.security_page(user, c, codes=codes, message='Novos códigos gerados. Os códigos anteriores foram invalidados.')
                elif path == '/admin/user/mfa-reset':
                    if not is_super(user):
                        return self.forbidden()
                    target = to_int(fields, 'user_id')
                    target_row = c.execute("SELECT * FROM users WHERE id=? AND deleted_at=''", (target,)).fetchone()
                    if not target_row:
                        raise ValidationError('Usuário inválido.')
                    c.execute("UPDATE users SET totp_secret='',totp_enabled=0,totp_last_step=0,totp_confirmed_at='',recovery_codes='',recovery_generated_at='' WHERE id=?", (target,))
                    self.audit_action(c, user['id'], 'redefinir MFA', target_row['email'], entity='user', entity_id=target, before={'totp_enabled': target_row['totp_enabled']}, after={'totp_enabled': 0})
                    redirect_to = '/admin/usuarios'
                elif path == '/admin/user/edit':
                    if not is_super(user):
                        return self.forbidden()
                    target = to_int(fields, 'user_id')
                    target_row = c.execute('SELECT * FROM users WHERE id=?', (target,)).fetchone()
                    if not target_row:
                        raise ValidationError('Usuário não encontrado.')
                    name = text_field(fields, 'name', 150, True, 'nome')
                    email = email_field(fields)
                    role = str(fields.get('role', 'client'))
                    if role not in ('client', 'staff', 'admin'):
                        raise ValidationError('Perfil inválido.')
                    kind = str(fields.get('staff_kind', 'lawyer'))
                    if kind not in ('lawyer', 'employee'):
                        raise ValidationError('Função inválida.')
                    active = 1 if fields.get('active') == '1' else 0
                    new_super = 1 if role == 'admin' and fields.get('is_super') == '1' else 0
                    if target == user['id'] and not active:
                        raise ValidationError('Você não pode desativar sua própria conta.')
                    if target_row['is_super'] and (not new_super or not active):
                        others = c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_super=1 AND active=1 AND id<>?", (target,)).fetchone()[0]
                        if others == 0:
                            raise ValidationError('Mantenha ao menos um super admin ativo.')
                    before = {k: target_row[k] for k in ('name', 'email', 'role', 'staff_kind', 'active', 'is_super')}
                    try:
                        c.execute('UPDATE users SET name=?,email=?,role=?,staff_kind=?,active=?,is_super=? WHERE id=?', (name, email, role, kind if role == 'staff' else '', active, new_super, target))
                    except IntegrityError:
                        raise ValidationError('E-mail já cadastrado.')
                    new_password = fields.get('password', '')
                    if new_password:
                        password = password_field(fields, 'password')
                        check_password_strength(password)
                        c.execute('UPDATE users SET password=?,must_change=1 WHERE id=?', (pwd(password), target))
                    self.audit_action(c, user['id'], 'editar usuário', email, entity='user', entity_id=target, before=before, after={'name': name, 'email': email, 'role': role, 'staff_kind': kind if role == 'staff' else '', 'active': active, 'is_super': new_super})
                    redirect_to = '/admin/usuarios'
                elif path == '/admin/user':
                    if not is_super(user):
                        return self.forbidden()
                    name = text_field(fields, 'name', 150, True, 'nome')
                    email = email_field(fields)
                    role = str(fields.get('role', 'client'))
                    if role not in ('client', 'staff', 'admin'):
                        raise ValidationError('Perfil inválido.')
                    kind = str(fields.get('staff_kind', 'lawyer'))
                    if kind not in ('lawyer', 'employee'):
                        raise ValidationError('Função inválida.')
                    initial = password_field(fields, 'password')
                    check_password_strength(initial)
                    is_super_flag = 1 if role == 'admin' and fields.get('is_super') == '1' else 0
                    try:
                        c.execute('INSERT INTO users(name,email,password,role,staff_kind,is_super) VALUES(?,?,?,?,?,?)', (name, email, pwd(initial), role, kind if role == 'staff' else '', is_super_flag))
                    except IntegrityError:
                        raise ValidationError('E-mail já cadastrado.')
                    self.audit_action(c, user['id'], 'criar usuário', email, entity='user', after={'name': name, 'email': email, 'role': role, 'staff_kind': kind if role == 'staff' else '', 'is_super': is_super_flag})
                elif path == '/admin/toggle':
                    if not is_super(user):
                        return self.forbidden()
                    target = to_int(fields, 'user_id')
                    target_row = c.execute("SELECT active FROM users WHERE id=? AND role='client'", (target,)).fetchone()
                    if not target_row:
                        raise ValidationError('Cliente inválido.')
                    c.execute('UPDATE users SET active=1-active WHERE id=?', (target,))
                    self.audit_action(c, user['id'], 'alterar acesso', str(target), entity='user', entity_id=target, client_id=target, before={'active': target_row['active']}, after={'active': 1 - target_row['active']})
                elif path == '/admin/reset':
                    if not is_super(user):
                        return self.forbidden()
                    target = to_int(fields, 'user_id')
                    new_password = password_field(fields, 'password')
                    check_password_strength(new_password)
                    if not c.execute('SELECT 1 FROM users WHERE id=?', (target,)).fetchone():
                        raise ValidationError('Usuário inválido.')
                    c.execute('UPDATE users SET password=?,must_change=1 WHERE id=?', (pwd(new_password), target))
                    self.audit_action(c, user['id'], 'redefinir senha', 'user=' + str(target), entity='user', entity_id=target)
                elif path == '/admin/assign' or path == '/admin/unassign':
                    if not (is_super(user) or user['role'] == 'admin'):
                        return self.forbidden()
                    if path == '/admin/assign':
                        staff_id = to_int(fields, 'staff_id')
                        client_id = to_int(fields, 'client_id')
                        if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('staff','admin') AND active=1 AND deleted_at=''", (staff_id,)).fetchone():
                            raise ValidationError('Funcionário inválido.')
                        if not c.execute("SELECT 1 FROM users WHERE id=? AND role='client'", (client_id,)).fetchone():
                            raise ValidationError('Cliente inválido.')
                        c.execute('INSERT OR IGNORE INTO assignments(staff_id,client_id) VALUES(?,?)', (staff_id, client_id))
                        self.audit_action(c, user['id'], 'atribuir cliente', 'staff=' + str(staff_id) + ' cliente=' + str(client_id), entity='assignment', client_id=client_id, after={'staff_id': staff_id, 'client_id': client_id})
                    else:
                        assignment_id = to_int(fields, 'assignment_id')
                        assignment_row = c.execute('SELECT * FROM assignments WHERE id=?', (assignment_id,)).fetchone()
                        if not assignment_row:
                            raise ValidationError('Vínculo não encontrado.')
                        if fields.get('client_id') and to_int(fields, 'client_id') != assignment_row['client_id']:
                            raise ValidationError('Vínculo inválido para este cliente.')
                        owner = c.execute('SELECT owner_staff_id FROM users WHERE id=?', (assignment_row['client_id'],)).fetchone()
                        if owner and owner['owner_staff_id'] == assignment_row['staff_id']:
                            raise ValidationError('Altere o responsável principal antes de remover este vínculo.')
                        c.execute('DELETE FROM assignments WHERE id=?', (assignment_id,))
                        self.audit_action(c, user['id'], 'remover atribuição', str(assignment_id), entity='assignment', entity_id=assignment_id, client_id=assignment_row['client_id'] if assignment_row else None, before=dict(assignment_row) if assignment_row else None)
                elif path == '/admin/tarefa':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    title = text_field(fields, 'title', 180, True, 'título')
                    description = text_field(fields, 'description', 5000)
                    client = to_int(fields, 'client_id', required=False)
                    case_id = to_int(fields, 'case_id', required=False)
                    if client and not self.can_manage(c, user, client):
                        return self.forbidden()
                    if case_id:
                        case_row = c.execute("SELECT * FROM cases WHERE id=? AND deleted_at=''", (case_id,)).fetchone()
                        if not case_row or not self.can_access_case(c, user, case_id):
                            return self.forbidden()
                        if client and case_row['client_id'] != client:
                            raise ValidationError('O caso não pertence ao cliente selecionado.')
                        client = case_row['client_id']
                    assigned = to_int(fields, 'assigned_to', required=False) or user['id']
                    if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('admin','staff') AND active=1 AND deleted_at=''", (assigned,)).fetchone():
                        raise ValidationError('Responsável inválido.')
                    if is_employee(user) and assigned != user['id']:
                        return self.forbidden()
                    priority = str(fields.get('priority', 'normal'))
                    if priority not in TASK_PRIORITY_LABELS:
                        raise ValidationError('Prioridade inválida.')
                    due_raw = str(fields.get('due_at', '')).strip()
                    due_at = ''
                    if due_raw:
                        try:
                            due_at = datetime.datetime.strptime(due_raw, '%Y-%m-%dT%H:%M').strftime('%Y-%m-%d %H:%M')
                        except ValueError:
                            raise ValidationError('Prazo inválido.')
                    source_message_id = to_int(fields, 'source_message_id', required=False)
                    if source_message_id:
                        source_message = c.execute("SELECT m.*,cv.visibility,cv.case_id FROM messages m JOIN conversations cv ON cv.id=m.conversation_id WHERE m.id=?", (source_message_id,)).fetchone()
                        if not source_message or source_message['visibility'] != 'internal':
                            raise ValidationError('Mensagem de origem inválida.')
                        if case_id and source_message['case_id'] and case_id != source_message['case_id']:
                            raise ValidationError('A mensagem pertence a outro caso.')
                        if source_message['case_id']:
                            case_id = source_message['case_id']
                            if not self.can_access_case(c, user, case_id):
                                return self.forbidden()
                        client = source_message['client_id']
                        if not self.can_manage(c, user, client):
                            return self.forbidden()
                    document_id = to_int(fields, 'document_id', required=False)
                    if document_id:
                        document = c.execute("SELECT * FROM documents WHERE id=? AND deleted_at=''", (document_id,)).fetchone()
                        if not document or not (self.can_access_case(c, user, document['case_id']) if document['case_id'] else self.can_manage(c, user, document['client_id'])):
                            raise ValidationError('Documento inválido.')
                    collaborator_ids = [int(key[len('collaborator_'):]) for key, value in fields.items() if key.startswith('collaborator_') and str(value) == '1' and key[len('collaborator_'):].isdigit()]
                    for collaborator_id in collaborator_ids:
                        if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('admin','staff') AND active=1 AND deleted_at=''", (collaborator_id,)).fetchone():
                            raise ValidationError('Colaborador inválido.')
                    task_id = c.execute("INSERT INTO tasks(title,description,client_id,case_id,assigned_to,created_by,due_at,priority,status,source_message_id,document_id) VALUES(?,?,?,?,?,?,?,?,'pendente',?,?)", (title, description, client or None, case_id or None, assigned, user['id'], due_at, priority, source_message_id or None, document_id or None)).lastrowid
                    for collaborator_id in collaborator_ids:
                        c.execute('INSERT OR IGNORE INTO task_collaborators(task_id,user_id) VALUES(?,?)', (task_id, collaborator_id))
                    if assigned != user['id']:
                        notify(c, assigned, 'task', 'Nova tarefa atribuída', title + ((' — prazo ' + fmt_when(due_at)) if due_at else ''), '/admin/tarefa?task_id=' + str(task_id), client or None, case_id or None, 'task-' + str(task_id) + '-u' + str(assigned))
                    for collaborator_id in collaborator_ids:
                        if collaborator_id not in (user['id'], assigned):
                            notify(c, collaborator_id, 'task', 'Você foi incluído em uma tarefa', title, '/admin/tarefa?task_id=' + str(task_id), client or None, case_id or None, 'task-' + str(task_id) + '-c' + str(collaborator_id))
                    self.audit_action(c, user['id'], 'criar tarefa', title, entity='task', entity_id=task_id, client_id=client or None, case_id=case_id or None, after={'title': title, 'description': description, 'due_at': due_at, 'priority': priority, 'assigned_to': assigned, 'collaborators': collaborator_ids, 'document_id': document_id})
                    redirect_to = '/admin/tarefas'
                elif path == '/admin/tarefa/subtarefa':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    task_id = to_int(fields, 'task_id')
                    task = c.execute("SELECT * FROM tasks WHERE id=? AND deleted_at=''", (task_id,)).fetchone()
                    if not task:
                        raise ValidationError('Tarefa não encontrada.')
                    collaborator = c.execute('SELECT 1 FROM task_collaborators WHERE task_id=? AND user_id=?', (task_id, user['id'])).fetchone()
                    if user['role'] != 'admin' and task['assigned_to'] != user['id'] and task['created_by'] != user['id'] and not collaborator:
                        return self.forbidden()
                    operation = str(fields.get('operation', ''))
                    if operation == 'add':
                        title = text_field(fields, 'title', 300, True, 'subtarefa')
                        c.execute('INSERT INTO task_subtasks(task_id,title) VALUES(?,?)', (task_id, title))
                    else:
                        subtask_id = to_int(fields, 'subtask_id')
                        subtask = c.execute('SELECT * FROM task_subtasks WHERE id=? AND task_id=?', (subtask_id, task_id)).fetchone()
                        if not subtask:
                            raise ValidationError('Subtarefa não encontrada.')
                        if operation == 'toggle':
                            c.execute('UPDATE task_subtasks SET completed=1-completed WHERE id=?', (subtask_id,))
                        elif operation == 'delete':
                            c.execute('DELETE FROM task_subtasks WHERE id=?', (subtask_id,))
                        else:
                            raise ValidationError('Operação inválida.')
                    self.audit_action(c, user['id'], 'atualizar subtarefa', task['title'], entity='task', entity_id=task_id, client_id=task['client_id'], case_id=task['case_id'], after={'operation': operation})
                    redirect_to = '/admin/tarefa?task_id=' + str(task_id)
                elif path == '/admin/tarefa/editar':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    task_id = to_int(fields, 'task_id')
                    task = c.execute("SELECT * FROM tasks WHERE id=? AND deleted_at=''", (task_id,)).fetchone()
                    if not task:
                        raise ValidationError('Tarefa não encontrada.')
                    if user['role'] != 'admin' and task['assigned_to'] != user['id'] and task['created_by'] != user['id']:
                        return self.forbidden()
                    title = text_field(fields, 'title', 180, True, 'título')
                    description = text_field(fields, 'description', 5000)
                    client = to_int(fields, 'client_id', required=False)
                    case_id = to_int(fields, 'case_id', required=False)
                    if client and not self.can_manage(c, user, client):
                        return self.forbidden()
                    if case_id:
                        case_row = c.execute("SELECT * FROM cases WHERE id=? AND deleted_at=''", (case_id,)).fetchone()
                        if not case_row or not self.can_access_case(c, user, case_id):
                            return self.forbidden()
                        if client and case_row['client_id'] != client:
                            raise ValidationError('O caso não pertence ao cliente selecionado.')
                        client = case_row['client_id']
                    assigned = to_int(fields, 'assigned_to', required=False) or user['id']
                    if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('admin','staff') AND active=1 AND deleted_at=''", (assigned,)).fetchone():
                        raise ValidationError('Responsável inválido.')
                    if is_employee(user) and assigned != user['id']:
                        return self.forbidden()
                    priority = str(fields.get('priority', 'normal'))
                    status = str(fields.get('status', 'pendente'))
                    if priority not in TASK_PRIORITY_LABELS or status not in TASK_STATUS_LABELS:
                        raise ValidationError('Prioridade ou situação inválida.')
                    due_raw = str(fields.get('due_at', '')).strip()
                    due_at = ''
                    if due_raw:
                        try:
                            due_at = datetime.datetime.strptime(due_raw, '%Y-%m-%dT%H:%M').strftime('%Y-%m-%d %H:%M')
                        except ValueError:
                            raise ValidationError('Prazo inválido.')
                    document_id = to_int(fields, 'document_id', required=False)
                    if document_id:
                        document = c.execute("SELECT * FROM documents WHERE id=? AND deleted_at=''", (document_id,)).fetchone()
                        if not document or not (self.can_access_case(c, user, document['case_id']) if document['case_id'] else self.can_manage(c, user, document['client_id'])):
                            raise ValidationError('Documento inválido.')
                    collaborator_ids = [int(key[len('collaborator_'):]) for key, value in fields.items() if key.startswith('collaborator_') and str(value) == '1' and key[len('collaborator_'):].isdigit()]
                    for collaborator_id in collaborator_ids:
                        if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('admin','staff') AND active=1 AND deleted_at=''", (collaborator_id,)).fetchone():
                            raise ValidationError('Colaborador inválido.')
                    c.execute("UPDATE tasks SET title=?,description=?,client_id=?,case_id=?,assigned_to=?,due_at=?,priority=?,status=?,completed_at=?,document_id=?,updated=CURRENT_TIMESTAMP WHERE id=?", (title, description, client or None, case_id or None, assigned, due_at, priority, status, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status == 'concluida' else '', document_id or None, task_id))
                    c.execute('DELETE FROM task_collaborators WHERE task_id=?', (task_id,))
                    for collaborator_id in collaborator_ids:
                        c.execute('INSERT OR IGNORE INTO task_collaborators(task_id,user_id) VALUES(?,?)', (task_id, collaborator_id))
                    if assigned != task['assigned_to']:
                        notify(c, assigned, 'task', 'Tarefa atribuída a você', title, '/admin/tarefa?task_id=' + str(task_id), client or None, case_id or None, 'task-' + str(task_id) + '-reassign-' + str(assigned))
                    self.audit_action(c, user['id'], 'editar tarefa', title, entity='task', entity_id=task_id, client_id=client or None, case_id=case_id or None, before={'title': task['title'], 'description': task['description'], 'due_at': task['due_at'], 'priority': task['priority'], 'status': task['status'], 'assigned_to': task['assigned_to']}, after={'title': title, 'description': description, 'due_at': due_at, 'priority': priority, 'status': status, 'assigned_to': assigned, 'collaborators': collaborator_ids, 'document_id': document_id})
                    redirect_to = '/admin/tarefa?task_id=' + str(task_id)
                elif path == '/admin/tarefa/excluir':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    task_id = to_int(fields, 'task_id')
                    task = c.execute("SELECT * FROM tasks WHERE id=? AND deleted_at=''", (task_id,)).fetchone()
                    if not task:
                        raise ValidationError('Tarefa não encontrada.')
                    if user['role'] != 'admin' and task['created_by'] != user['id']:
                        return self.forbidden()
                    c.execute("UPDATE tasks SET deleted_at=CURRENT_TIMESTAMP,deleted_by=? WHERE id=?", (user['id'], task_id))
                    self.audit_action(c, user['id'], 'excluir tarefa', task['title'], entity='task', entity_id=task_id, client_id=task['client_id'], case_id=task['case_id'], before={'title': task['title']})
                    redirect_to = '/admin/tarefas'
                elif path == '/admin/tarefa/status':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    task_id = to_int(fields, 'task_id')
                    task = c.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
                    if not task:
                        raise ValidationError('Tarefa não encontrada.')
                    if user['role'] != 'admin' and task['assigned_to'] != user['id'] and task['created_by'] != user['id']:
                        return self.forbidden()
                    status = str(fields.get('status', 'pendente'))
                    if status not in TASK_STATUS_LABELS:
                        raise ValidationError('Situação inválida.')
                    c.execute("UPDATE tasks SET status=?,completed_at=?,updated=CURRENT_TIMESTAMP WHERE id=?", (status, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status == 'concluida' else '', task_id))
                    self.audit_action(c, user['id'], 'atualizar tarefa', task['title'], entity='task', entity_id=task_id, client_id=task['client_id'], case_id=task['case_id'], before={'status': task['status']}, after={'status': status})
                    redirect_to = '/admin/tarefas'
                elif path == '/admin/documento-interno/editar':
                    if not has_permission(c, user, 'manage_documents'):
                        return self.forbidden()
                    document_id = to_int(fields, 'doc_id')
                    document = c.execute("SELECT * FROM internal_documents WHERE id=? AND deleted_at=''", (document_id,)).fetchone()
                    if not document or not self.can_view_internal_document(c, user, document):
                        return self.forbidden()
                    if user['role'] != 'admin' and document['uploaded_by'] != user['id']:
                        return self.forbidden()
                    title = text_field(fields, 'title', 180, True, 'título')
                    category = text_field(fields, 'category', 100)
                    client = to_int(fields, 'client_id', required=False)
                    case_id = to_int(fields, 'case_id', required=False)
                    visibility = str(fields.get('visibility', 'equipe'))
                    if visibility not in ('equipe', 'caso'):
                        raise ValidationError('Visibilidade inválida.')
                    if visibility == 'caso' and not case_id:
                        raise ValidationError('Selecione o caso para um documento restrito à equipe do caso.')
                    if client and not self.can_manage(c, user, client):
                        return self.forbidden()
                    if case_id:
                        case_row = c.execute("SELECT * FROM cases WHERE id=? AND deleted_at=''", (case_id,)).fetchone()
                        if not case_row or not self.can_access_case(c, user, case_id):
                            return self.forbidden()
                        if client and case_row['client_id'] != client:
                            raise ValidationError('O caso não pertence ao cliente selecionado.')
                        client = case_row['client_id']
                    c.execute("UPDATE internal_documents SET title=?,category=?,client_id=?,case_id=?,visibility=? WHERE id=?", (title, category, client or None, case_id or None, visibility, document_id))
                    self.audit_action(c, user['id'], 'editar documento interno', title, entity='internal_document', entity_id=document_id, client_id=client or None, case_id=case_id or None, before={'title': document['title'], 'category': document['category'], 'visibility': document['visibility']}, after={'title': title, 'category': category, 'visibility': visibility})
                    redirect_to = '/admin/documento-interno?doc_id=' + str(document_id)
                elif path == '/admin/documento-interno/excluir':
                    if not has_permission(c, user, 'manage_documents'):
                        return self.forbidden()
                    document_id = to_int(fields, 'doc_id')
                    document = c.execute("SELECT * FROM internal_documents WHERE id=? AND deleted_at=''", (document_id,)).fetchone()
                    if not document or not self.can_view_internal_document(c, user, document):
                        return self.forbidden()
                    if user['role'] != 'admin' and document['uploaded_by'] != user['id']:
                        return self.forbidden()
                    c.execute("UPDATE internal_documents SET deleted_at=CURRENT_TIMESTAMP,deleted_by=? WHERE id=?", (user['id'], document_id))
                    self.audit_action(c, user['id'], 'excluir documento interno', document['title'], entity='internal_document', entity_id=document_id, client_id=document['client_id'], case_id=document['case_id'], before={'title': document['title'], 'filename': document['filename']})
                    redirect_to = '/admin/documentos-internos'
                elif path == '/admin/documento-interno':
                    if not has_permission(c, user, 'manage_documents'):
                        return self.forbidden()
                    title = text_field(fields, 'title', 180, True, 'título')
                    category = text_field(fields, 'category', 100)
                    client = to_int(fields, 'client_id', required=False)
                    case_id = to_int(fields, 'case_id', required=False)
                    visibility = str(fields.get('visibility', 'equipe'))
                    if visibility not in ('equipe', 'caso'):
                        raise ValidationError('Visibilidade inválida.')
                    if visibility == 'caso' and not case_id:
                        raise ValidationError('Selecione o caso para um documento restrito à equipe do caso.')
                    if client and not self.can_manage(c, user, client):
                        return self.forbidden()
                    if case_id:
                        case_row = c.execute("SELECT * FROM cases WHERE id=? AND deleted_at=''", (case_id,)).fetchone()
                        if not case_row or not self.can_access_case(c, user, case_id):
                            return self.forbidden()
                        if client and case_row['client_id'] != client:
                            raise ValidationError('O caso não pertence ao cliente selecionado.')
                        client = case_row['client_id']
                    filename, payload, _mime = files.get('file', ('', b'', ''))
                    allowed = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.txt': 'text/plain'}
                    extension = Path(filename or '').suffix.lower()
                    if extension not in allowed or not payload or len(payload) > MAX_FILE:
                        return self.error_page('Arquivo recusado', 'Permitidos: PDF, PNG, JPG e TXT, até 10 MB.', 400, user)
                    signatures = {'.pdf': payload.startswith(b'%PDF-'), '.png': payload.startswith(b'\x89PNG\r\n\x1a\n'), '.jpg': payload.startswith(b'\xff\xd8\xff'), '.jpeg': payload.startswith(b'\xff\xd8\xff'), '.txt': b'\x00' not in payload}
                    if not signatures[extension]:
                        return self.forbidden()
                    stored = secrets.token_hex(24) + extension
                    temp = UP / (stored + '.tmp')
                    temp.write_bytes(payload)
                    if not scan_file(temp):
                        temp.unlink(missing_ok=True)
                        return self.error_page('Arquivo recusado', 'O arquivo não passou na verificação de segurança.', 400, user)
                    final = UP / stored
                    document_id = c.execute("INSERT INTO internal_documents(title,category,client_id,case_id,filename,stored,mime,size,uploaded_by,visibility) VALUES(?,?,?,?,?,?,?,?,?,?)", (title, category, client or None, case_id or None, Path(filename or '').name[:160], stored, allowed[extension], len(payload), user['id'], visibility)).lastrowid
                    os.replace(temp, final)
                    self.audit_action(c, user['id'], 'enviar documento interno', title, entity='internal_document', entity_id=document_id, client_id=client or None, case_id=case_id or None, after={'filename': Path(filename or '').name[:160], 'visibility': visibility})
                    redirect_to = '/admin/documentos-internos'
                elif path == '/admin/update' or path == '/admin/appointment':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    client = to_int(fields, 'client_id', required=False)
                    case_id = 0
                    if str(fields.get('case_id', '')).strip():
                        case_id = to_int(fields, 'case_id')
                        case_row = c.execute('SELECT * FROM cases WHERE id=? AND deleted_at=\'\'', (case_id,)).fetchone()
                        if not case_row or not self.can_access_case(c, user, case_id):
                            raise ValidationError('Caso inválido.')
                        if client and case_row['client_id'] != client:
                            raise ValidationError('O caso não pertence ao cliente selecionado.')
                        client = case_row['client_id']
                    if path.endswith('update'):
                        if not client:
                            raise ValidationError('Selecione o cliente da atualização.')
                        if not self.can_manage(c, user, client):
                            return self.forbidden()
                    elif client and not self.can_manage(c, user, client):
                        return self.forbidden()
                    title = text_field(fields, 'title', 150, True, 'título')
                    if path.endswith('update'):
                        body = text_field(fields, 'body', 5000, True, 'descrição')
                        cursor = c.execute('INSERT INTO updates(client_id,case_id,title,body,author_id) VALUES(?,?,?,?,?)', (client, case_id or None, title, body, user['id']))
                        update_id = cursor.lastrowid
                        touch_case(c, case_id or None)
                        notify(c, client, 'update', 'Nova atualização do escritório', title, '/cliente', client, case_id or None, 'update-' + str(update_id) + '-client')
                        self.audit_action(c, user['id'], 'publicar atualização', title, entity='update', client_id=client, case_id=case_id or None, after={'title': title, 'body': body})
                    else:
                        raw_when = text_field(fields, 'when_at', 50, True, 'data e hora')
                        try:
                            when_dt = datetime.datetime.strptime(raw_when, '%Y-%m-%dT%H:%M')
                        except ValueError:
                            raise ValidationError('Data e hora inválidas.')
                        notes = text_field(fields, 'notes', 1000)
                        kind = str(fields.get('kind', 'compromisso'))
                        if kind not in TASK_KIND_LABELS:
                            raise ValidationError('Tipo de compromisso inválido.')
                        location = text_field(fields, 'location', 300)
                        owner_id = to_int(fields, 'owner_id', required=False) or user['id']
                        if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('admin','staff') AND active=1 AND deleted_at=''", (owner_id,)).fetchone():
                            raise ValidationError('Responsável interno inválido.')
                        reminder_choice = str(fields.get('reminder_choice', 'global'))
                        if reminder_choice not in ('none', '1h', '1d', 'global'):
                            raise ValidationError('Opção de lembrete inválida.')
                        privacy = str(fields.get('privacy', 'internal'))
                        if privacy not in ('private', 'internal', 'client'):
                            raise ValidationError('Privacidade inválida.')
                        participant_ids = selected_participant_ids(fields)
                        for participant_id in participant_ids:
                            if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('admin','staff') AND active=1 AND deleted_at=''", (participant_id,)).fetchone():
                                raise ValidationError('Participante inválido.')
                        when_at = when_dt.strftime('%Y-%m-%d %H:%M')
                        if reminder_choice == 'none':
                            reminder_at = ''
                        else:
                            reminder_hours = 24 if reminder_choice == '1d' else (1 if reminder_choice == '1h' else max(1, int(setting(c, 'appointment_reminder_hours', '24') or 24)))
                            reminder_at = (when_dt - datetime.timedelta(hours=reminder_hours)).strftime('%Y-%m-%d %H:%M')
                        cursor = c.execute('INSERT INTO appointments(client_id,case_id,title,when_at,notes,created_by,status,reminder_at,kind,owner_id,location,reminder_choice,privacy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (client or None, case_id or None, title, when_at, notes, user['id'], 'pendente', reminder_at, kind, owner_id, location, reminder_choice, privacy))
                        appointment_id = cursor.lastrowid
                        for participant_id in participant_ids:
                            c.execute('INSERT OR IGNORE INTO appointment_participants(appointment_id,user_id) VALUES(?,?)', (appointment_id, participant_id))
                        touch_case(c, case_id or None)
                        if client and privacy == 'client':
                            notify(c, client, 'appointment', 'Novo compromisso', title + ' — ' + when_at, '/cliente', client, case_id or None, 'appointment-' + str(appointment_id) + '-client')
                            for uid in client_audience(c, client, case_id or None):
                                if uid != user['id']:
                                    notify(c, uid, 'appointment', 'Novo compromisso', title + ' — ' + when_at, '/admin', client, case_id or None, 'appointment-' + str(appointment_id) + '-u' + str(uid))
                        if owner_id != user['id']:
                            notify(c, owner_id, 'appointment', 'Compromisso sob sua responsabilidade', title + ' — ' + when_at, '/admin/compromisso?appointment_id=' + str(appointment_id), client or None, case_id or None, 'appointment-' + str(appointment_id) + '-owner')
                        for participant_id in participant_ids:
                            if participant_id not in (user['id'], owner_id):
                                notify(c, participant_id, 'appointment', 'Você foi incluído em um compromisso', title + ' — ' + when_at, '/admin/compromisso?appointment_id=' + str(appointment_id), client or None, case_id or None, 'appointment-' + str(appointment_id) + '-p' + str(participant_id))
                        self.audit_action(c, user['id'], 'criar compromisso', title, entity='appointment', client_id=client or None, case_id=case_id or None, after={'title': title, 'when_at': when_at, 'notes': notes, 'reminder_at': reminder_at, 'reminder_choice': reminder_choice, 'kind': kind, 'owner_id': owner_id, 'location': location, 'privacy': privacy, 'participants': participant_ids})
                    redirect_to = '/admin/atualizacoes' if path == '/admin/update' else '/admin/compromissos'
                elif path == '/admin/respond':
                    if not has_permission(c, user, 'manage_cases'):
                        return self.forbidden()
                    request_id = to_int(fields, 'request_id')
                    status = str(fields.get('status', 'Pendente'))
                    if status not in ('Pendente', 'Em andamento', 'Respondida', 'Concluída', 'Informativo'):
                        raise ValidationError('Status inválido.')
                    response = text_field(fields, 'response', 5000)
                    request_row = c.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
                    if not request_row:
                        raise ValidationError('Solicitação não encontrada.')
                    if not self.can_manage(c, user, request_row['client_id']):
                        return self.forbidden()
                    responded_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    c.execute('UPDATE requests SET response=?,status=?,responded_by=?,responded_at=?,last_activity_at=CURRENT_TIMESTAMP WHERE id=?', (response, status, user['id'], responded_at, request_id))
                    touch_case(c, request_row['case_id'])
                    notify(c, request_row['client_id'], 'request', 'Resposta recebida', response[:200], '/cliente', request_row['client_id'], request_row['case_id'], 'request-' + str(request_id) + '-response-' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
                    self.audit_action(c, user['id'], 'responder solicitação', str(request_id), entity='request', entity_id=request_id, client_id=request_row['client_id'], case_id=request_row['case_id'], before={'response': request_row['response'], 'status': request_row['status']}, after={'response': response, 'status': status, 'responded_by': user['id']})
                    redirect_to = '/admin/solicitacoes'
                elif path == '/admin/post':
                    title = text_field(fields, 'title', 150, True, 'título')
                    category = text_field(fields, 'category', 80, True, 'categoria')
                    body = text_field(fields, 'body', 10000, True, 'texto')
                    cursor = c.execute('INSERT INTO posts(title,category,body,published) VALUES(?,?,?,?)', (title, category, body, bool_flag(fields, 'published')))
                    self.audit_action(c, user['id'], 'criar conteúdo', title, entity='post', entity_id=cursor.lastrowid, after={'title': title, 'category': category})
                    redirect_to = '/admin/conteudos'
                elif path == '/admin/faq':
                    category = str(fields.get('category', 'Geral')).strip()[:120] or 'Geral'
                    question = text_field(fields, 'question', 300, True, 'pergunta')
                    answer = text_field(fields, 'answer', 3000, True, 'resposta')
                    sort_order = to_int(fields, 'sort_order', required=False)
                    cursor = c.execute('INSERT INTO faqs(question,answer,published,category,sort_order) VALUES(?,?,?,?,?)', (question, answer, bool_flag(fields, 'published'), category, sort_order))
                    self.audit_action(c, user['id'], 'criar faq', question, entity='faq', entity_id=cursor.lastrowid, after={'question': question, 'category': category, 'sort_order': sort_order, 'published': bool_flag(fields, 'published')})
                    redirect_to = '/admin/faq'
                elif path == '/admin/faq/editar':
                    faq_id = to_int(fields, 'faq_id')
                    faq_row = c.execute('SELECT * FROM faqs WHERE id=?', (faq_id,)).fetchone()
                    if not faq_row:
                        raise ValidationError('Pergunta não encontrada.')
                    category = str(fields.get('category', 'Geral')).strip()[:120] or 'Geral'
                    question = text_field(fields, 'question', 300, True, 'pergunta')
                    answer = text_field(fields, 'answer', 3000, True, 'resposta')
                    sort_order = to_int(fields, 'sort_order', required=False)
                    published = bool_flag(fields, 'published')
                    c.execute("UPDATE faqs SET category=?,question=?,answer=?,sort_order=?,published=?,updated=CURRENT_TIMESTAMP WHERE id=?", (category, question, answer, sort_order, published, faq_id))
                    self.audit_action(c, user['id'], 'editar faq', question, entity='faq', entity_id=faq_id, before={'category': faq_row['category'], 'question': faq_row['question'], 'published': faq_row['published'], 'sort_order': faq_row['sort_order']}, after={'category': category, 'question': question, 'published': published, 'sort_order': sort_order})
                    redirect_to = '/admin/faq'
                elif path == '/admin/review':
                    if not has_permission(c, user, 'manage_documents'):
                        return self.forbidden()
                    document = c.execute('SELECT * FROM documents WHERE id=?', (to_int(fields, 'doc_id'),)).fetchone()
                    if not document:
                        raise ValidationError('Documento não encontrado.')
                    if not self.can_manage(c, user, document['client_id']):
                        return self.forbidden()
                    c.execute('UPDATE documents SET reviewed=1-reviewed WHERE id=?', (document['id'],))
                    self.audit_action(c, user['id'], 'revisar documento', str(document['id']), entity='document', entity_id=document['id'], client_id=document['client_id'], case_id=document['case_id'], before={'reviewed': document['reviewed']}, after={'reviewed': 1 - document['reviewed']})
                elif path == '/admin/chat-equipe':
                    if user['role'] not in ('admin', 'staff'):
                        return self.forbidden()
                    filename, payload, _mime = files.get('file', ('', b'', ''))
                    has_file = bool(filename and payload)
                    body = text_field(fields, 'body', 5000, not has_file, 'mensagem')
                    attachment = {'filename': '', 'stored': '', 'mime': '', 'size': 0}
                    if has_file:
                        extension = Path(filename).suffix.lower()
                        allowed = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.txt': 'text/plain'}
                        if extension not in allowed or len(payload) > MAX_FILE:
                            raise ValidationError('Anexo inválido. Permitidos: PDF, PNG, JPG e TXT, até 10 MB.')
                        signatures = {'.pdf': payload.startswith(b'%PDF-'), '.png': payload.startswith(b'\x89PNG\r\n\x1a\n'), '.jpg': payload.startswith(b'\xff\xd8\xff'), '.jpeg': payload.startswith(b'\xff\xd8\xff'), '.txt': b'\x00' not in payload}
                        if not signatures[extension]:
                            raise ValidationError('O anexo não corresponde ao formato informado.')
                        stored = 'equipe-' + secrets.token_hex(20) + extension
                        temp = UP / (stored + '.tmp')
                        temp.write_bytes(payload)
                        if not scan_file(temp):
                            temp.unlink(missing_ok=True)
                            raise ValidationError('O anexo não passou na verificação de segurança.')
                        os.replace(temp, UP / stored)
                        attachment = {'filename': Path(filename).name[:160], 'stored': stored, 'mime': allowed[extension], 'size': len(payload)}
                    message_id = c.execute("INSERT INTO team_chat_messages(sender_id,body,attachment_filename,attachment_stored,attachment_mime,attachment_size) VALUES(?,?,?,?,?,?)", (user['id'], body, attachment['filename'], attachment['stored'], attachment['mime'], attachment['size'])).lastrowid
                    for uid in mentioned_user_ids(c, body):
                        c.execute('INSERT OR IGNORE INTO team_chat_mentions(message_id,user_id) VALUES(?,?)', (message_id, uid))
                        if uid != user['id']:
                            notify(c, uid, 'mention', 'Você foi mencionado no chat da equipe', body[:200], '/admin/chat-equipe', dedupe_key='team-mention-' + str(message_id) + '-u' + str(uid))
                    c.execute('INSERT OR IGNORE INTO team_chat_reads(message_id,user_id) VALUES(?,?)', (message_id, user['id']))
                    self.audit_action(c, user['id'], 'mensagem no chat da equipe', body[:200], entity='team_chat', entity_id=message_id, after={'attachment': attachment['filename']})
                    redirect_to = '/admin/chat-equipe'
                elif path == '/admin/mensagem':
                    if not has_permission(c, user, 'send_messages'):
                        return self.forbidden()
                    client = to_int(fields, 'client_id')
                    case_id = 0
                    if str(fields.get('case_id', '')).strip():
                        case_id = to_int(fields, 'case_id')
                        case_row = c.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
                        if not case_row or case_row['client_id'] != client or not self.can_access_case(c, user, case_id):
                            raise ValidationError('Caso inválido para este cliente.')
                    body = text_field(fields, 'body', 5000, True, 'mensagem')
                    if not self.can_manage(c, user, client):
                        return self.forbidden()
                    visibility = 'internal' if fields.get('visibility') == 'internal' else 'client'
                    reveal_identity = 1 if visibility == 'client' and fields.get('reveal_identity') == '1' else 0
                    subject = text_field(fields, 'subject', 200, False, 'assunto')
                    selected_case = c.execute('SELECT title FROM cases WHERE id=?', (case_id,)).fetchone() if case_id else None
                    conversation_id = create_conversation(c, client, case_id, subject or (selected_case['title'] if selected_case else ('Relato interno' if visibility == 'internal' else 'Contato geral')), visibility, user['id'])
                    cursor = c.execute('INSERT INTO messages(client_id,case_id,conversation_id,sender_id,sender_role,visibility,reveal_identity,body,read_by_client,read_by_staff) VALUES(?,?,?,?,?,?,?,?,?,1)', (client, case_id or None, conversation_id, user['id'], user['role'], visibility, reveal_identity, body, 1 if visibility == 'internal' else 0))
                    message_id = cursor.lastrowid
                    touch_case(c, case_id or None)
                    if visibility == 'client':
                        notify(c, client, 'message', 'Nova mensagem do escritório', body[:200], '/conversas/' + str(conversation_id), client, case_id or None, 'message-' + str(message_id) + '-client')
                    else:
                        case_row = c.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone() if case_id else None
                        audience = case_audience(c, case_row) if case_row else client_audience(c, client)
                        for uid in audience:
                            if uid != user['id']:
                                notify(c, uid, 'internal', 'Novo relato interno', body[:200], '/conversas/' + str(conversation_id), client, case_id or None, 'internal-' + str(message_id) + '-u' + str(uid))
                        for uid in mentioned_user_ids(c, body):
                            c.execute('INSERT OR IGNORE INTO message_mentions(message_id,user_id) VALUES(?,?)', (message_id, uid))
                            if uid != user['id']:
                                notify(c, uid, 'mention', 'Você foi mencionado em uma conversa interna', body[:200], '/conversas/' + str(conversation_id), client, case_id or None, 'mention-' + str(message_id) + '-u' + str(uid))
                    self.audit_action(c, user['id'], 'mensagem ao cliente' if visibility == 'client' else 'relato interno', body[:200], entity='message', client_id=client, case_id=case_id or None, after={'visibility': visibility, 'reveal_identity': reveal_identity})
                    redirect_to = '/conversas/' + str(conversation_id)
                else:
                    return self.forbidden()
            self.flash('Operação concluída com sucesso.')
            return self.redirect(safe_admin_return(fields, redirect_to))
        except ValidationError as error:
            return self.error_page('Dados inválidos', str(error), 400, user)
        except Exception:
            traceback.print_exc()
            return self.error_page('Erro interno', 'Não foi possível concluir a operação. Tente novamente.', 500, user)


def local_network_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('8.8.8.8', 80))
            return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'


def run():
    init()
    sys.modules.setdefault('app', sys.modules[__name__])
    from flask_app import flask_app
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8080'))
    print(f'AMBIENTE DE TESTES (Flask): http://127.0.0.1:{port}')
    print(f'Acesso na rede local: http://{local_network_ip()}:{port}')
    print('Para liberar no Windows, execute o comando de firewall documentado no README.')
    flask_app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    run()
