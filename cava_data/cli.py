import subprocess
import argparse
from gunicorn.app.base import BaseApplication
from cava_data.core.config import settings


class StandaloneApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def serve():
    if not settings.DEVELOPMENT:
        from cava_data.main import app

        options = {
            'bind': f"{settings.HOST}:{settings.PORT}",
            'host': settings.HOST,
            'port': settings.PORT,
            'workers': settings.WORKERS,
            'worker_class': settings.WORKER_CLASS,
            'loglevel': settings.LOG_LEVEL,
            'graceful_timeout': settings.GRACEFUL_TIMEOUT,
            'timeout': settings.TIMEOUT,
            'keepalive': settings.KEEP_ALIVE,
        }
        StandaloneApplication(app, options).run()
    else:
        import uvicorn

        uvicorn.run(
            "cava_data.main:app",
            host=settings.HOST,
            port=settings.PORT,
            log_level=settings.LOG_LEVEL,
            loop=settings.LOOP,
            http=settings.HTTP,
            workers=settings.WORKERS,
            reload=settings.DEVELOPMENT,
        )


def worker():
    package_name = __name__.split('.')[0]
    default_tasks = f'{package_name}.api.workers.tasks'
    parser = argparse.ArgumentParser(prog="Data worker")
    parser.add_argument('--tasks', type=str, default='')
    parser.add_argument('--log-level', type=str, default='info')
    parser.add_argument('--pool', type=str, default='gevent')
    parser.add_argument('--queue', type=str, default='')

    args = parser.parse_args()

    if args.tasks:
        tasks = args.tasks
    else:
        tasks = default_tasks

    if args.queue:
        queue = args.queue
    else:
        queue = str(settings.DATA_QUEUE)

    cmd = [
        'celery',
        '-A',
        tasks,
        'worker',
        '-E',
        '-l',
        args.log_level,
        '-Q',
        queue,
        '-c',
        '1',
        '-P',
        args.pool,
    ]

    subprocess.run(cmd)
