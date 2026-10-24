from alembic import context
from app.db import Base, engine


def include_object(obj, name, type_, reflected, compare_to):
    # LangGraph manages these tables with its own versioned setup. Alembic must
    # still report drift for every other unexpected application table.
    checkpoint_tables = {"checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes"}
    return not (type_ == "table" and reflected and compare_to is None and name in checkpoint_tables)


def run_migrations():
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=Base.metadata, compare_type=True, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
