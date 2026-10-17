import os,sys,uuid
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]
for path in (ROOT/'scripts',ROOT/'services/api'):sys.path.insert(0,str(path))
import devdb
RUN=os.environ.setdefault('NEXTRM_TEST_RUN',uuid.uuid4().hex[:8])
TEMPLATE='nextrm_tpl_'+RUN
WORKING=f'nextrm_t_{RUN}_{os.getpid()}'
os.environ['DATABASE_URL']=devdb.url(WORKING)
os.environ['ENVIRONMENT']='test'
from app.core.database import engine,SessionLocal
from app.core.seeder import seed_demo_database

def build_template():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    devdb.ensure_server()
    devdb.drop(TEMPLATE);devdb.create(TEMPLATE)
    working_url=os.environ['DATABASE_URL'];os.environ['DATABASE_URL']=devdb.url(TEMPLATE)
    try:
        migrations=Config();migrations.set_main_option('script_location',str(ROOT/'services/api/migrations'))
        command.upgrade(migrations,'head')
        seeding=create_engine(os.environ['DATABASE_URL'])
        with Session(seeding) as db:seed_demo_database(db)
        seeding.dispose()
    finally:os.environ['DATABASE_URL']=working_url

def pytest_configure(config):
    if not hasattr(config,'workerinput'):build_template()

def pytest_unconfigure(config):
    engine.dispose();devdb.drop(WORKING)
    if not hasattr(config,'workerinput'):devdb.drop(TEMPLATE)

@pytest.fixture(scope='session')
def working_database():
    devdb.clone(WORKING,TEMPLATE)

@pytest.fixture(autouse=True)
def isolated_database(working_database):
    connection=engine.connect();outer=connection.begin()
    SessionLocal.configure(bind=connection,join_transaction_mode='create_savepoint')
    yield
    SessionLocal.configure(bind=engine,join_transaction_mode='conservative_savepoint')
    outer.rollback();connection.close()
