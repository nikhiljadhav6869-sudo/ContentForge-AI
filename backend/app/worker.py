from redis import Redis
from rq import Worker, Queue
from .config import settings

if __name__ == "__main__":
    connection = Redis.from_url(settings.redis_url)
    Worker([Queue("contentforge", connection=connection)], connection=connection).work()
