from .config import settings

if settings.checkpoint_url:
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(settings.checkpoint_url) as saver:
        saver.setup()
