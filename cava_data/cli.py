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
            reload=settings.DEVELOPMENT
        )
