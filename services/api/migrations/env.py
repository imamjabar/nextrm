import os
from alembic import context
from sqlalchemy import create_engine
from app.core.database import Base
from app.models import entities, relationships
config=context.config
url=os.environ.get('DATABASE_URL')
if not url:raise RuntimeError('Set DATABASE_URL explicitly before migrations')
if context.is_offline_mode():
    context.configure(url=url,target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
else:
    engine=create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata)
        with context.begin_transaction():context.run_migrations()
