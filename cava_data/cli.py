import uvicorn
from cava_data.core.config import settings


def serve():
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
