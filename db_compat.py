"""Camada de compatibilidade SQLite/PostgreSQL.

SQLite continua sendo o padrão da suíte de testes. Quando ``DATABASE_URL``
aponta para PostgreSQL, esta camada adapta placeholders ``?``, lastrowid,
INSERT OR IGNORE, GROUP_CONCAT e transações sem exigir reescrita das consultas
existentes no restante da aplicação.
"""
from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import unquote

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if DATABASE_URL.lower().startswith('postgres://'):
    DATABASE_URL = 'postgresql://' + DATABASE_URL[len('postgres://'):]
IS_POSTGRES = DATABASE_URL.lower().startswith('postgresql://')
SQLITE_URL_PATH = None
if DATABASE_URL.lower().startswith('sqlite:///'):
    SQLITE_URL_PATH = Path(unquote(DATABASE_URL[len('sqlite:///'):]))

if IS_POSTGRES:
    import psycopg
    from psycopg.rows import tuple_row
    IntegrityError = psycopg.IntegrityError
else:
    psycopg = None
    IntegrityError = sqlite3.IntegrityError

_NO_ID_TABLES = {'settings', 'message_reads', 'team_chat_reads', 'schema_migrations'}


class CompatRow(Mapping):
    def __init__(self, values, columns):
        self._values = tuple(values)
        self._columns = tuple(columns)
        self._map = dict(zip(self._columns, self._values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]

    def __iter__(self):
        return iter(self._columns)

    def __len__(self):
        return len(self._columns)

    def keys(self):
        return self._columns


def _pg_row_factory(cursor):
    columns = [column.name for column in (cursor.description or [])]
    return lambda values: CompatRow(values, columns)


class CompatCursor:
    def __init__(self, cursor, connection):
        self._cursor = cursor
        self._connection = connection
        self.lastrowid = 0
        self.rowcount = -1

    def execute(self, sql, params=()):
        original = str(sql)
        translated = self._connection.translate_sql(original)
        has_returning = bool(re.search(r'\bRETURNING\b', translated, re.I))
        table_match = re.search(r'^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)', translated, re.I)
        append_returning = bool(table_match and table_match.group(1).lower() not in _NO_ID_TABLES and not has_returning)
        if append_returning:
            translated = translated.rstrip().rstrip(';') + ' RETURNING id'
        if params:
            # psycopg usa % como marcador; % literais precisam ser escapados.
            translated = re.sub(r'%(?![s%])', '%%', translated)
            self._cursor.execute(translated, params)
        else:
            # Sem par?metros, n?o passar uma tupla vazia: ela faria o psycopg
            # interpretar % literais de DDL/consultas como placeholders.
            self._cursor.execute(translated)
        self.lastrowid = 0
        if append_returning:
            row = self._cursor.fetchone()
            if row:
                self.lastrowid = row[0]
        self.rowcount = self._cursor.rowcount
        self._connection._last_rowcount = max(0, self.rowcount)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)

    def close(self):
        return self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class CompatConnection:
    def __init__(self, connection):
        self._connection = connection
        self._last_rowcount = 0

    def translate_sql(self, sql):
        text = str(sql)
        if not IS_POSTGRES:
            return text
        original = text
        text = re.sub(r'\bGROUP_CONCAT\s*\(', 'STRING_AGG(', text, flags=re.I)
        ignore = bool(re.search(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', text, re.I))
        text = re.sub(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT INTO', text, flags=re.I)
        if ignore and not re.search(r'\bON\s+CONFLICT\b', text, re.I):
            text = text.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
        if re.search(r'\bSELECT\s+changes\s*\(\s*\)', text, re.I):
            text = re.sub(r'\bSELECT\s+changes\s*\(\s*\)', 'SELECT ' + str(self._last_rowcount), text, flags=re.I)
        return text.replace('?', '%s')

    def execute(self, sql, params=()):
        return CompatCursor(self._connection.cursor(row_factory=_pg_row_factory), self).execute(sql, params)

    def executescript(self, script):
        for statement in str(script).split(';'):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        return False


def connect(path):
    if IS_POSTGRES:
        return CompatConnection(psycopg.connect(DATABASE_URL))
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA busy_timeout=5000')
    return connection


def table_columns(connection, table):
    if IS_POSTGRES:
        rows = connection.execute(
            "SELECT column_name AS name, is_nullable, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=? ORDER BY ordinal_position",
            (table,),
        ).fetchall()
        return [{'name': row['name'], 'notnull': row['is_nullable'] == 'NO', 'type': row['data_type']} for row in rows]
    return connection.execute('PRAGMA table_info(' + table + ')').fetchall()


def postgres_schema(sqlite_ddl):
    text = str(sqlite_ddl)
    if not IS_POSTGRES:
        return text
    return re.sub(r'\bid\s+INTEGER\s+PRIMARY\s+KEY\b', 'id SERIAL PRIMARY KEY', text, flags=re.I)
