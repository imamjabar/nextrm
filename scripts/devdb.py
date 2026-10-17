"""Disposable PostgreSQL databases for tests, benchmarks and validation scripts."""
import os
import subprocess
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
PORT = os.environ.get('NEXTRM_PGPORT', '54417')
ADMIN_DSN = os.environ.get('NEXTRM_PG_ADMIN_DSN', f'postgresql://127.0.0.1:{PORT}/postgres')


def _admin():
    return psycopg.connect(ADMIN_DSN, autocommit=True, connect_timeout=3)


def ensure_server():
    try:
        _admin().close()
    except psycopg.OperationalError:
        subprocess.run([str(ROOT / 'scripts/dev_db.sh'), 'start'], check=True, stdout=subprocess.DEVNULL)
        _admin().close()


def url(name):
    parsed = make_url(ADMIN_DSN.replace('postgresql://', 'postgresql+psycopg://', 1))
    return parsed.set(database=name).render_as_string(hide_password=False)


def drop(name):
    with _admin() as conn:
        conn.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(name)))


def create(name, template=None):
    statement = sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name))
    if template:
        statement += sql.SQL(' TEMPLATE {}').format(sql.Identifier(template))
    with _admin() as conn:
        conn.execute(statement)


def clone(name, template):
    drop(name)
    create(name, template)
