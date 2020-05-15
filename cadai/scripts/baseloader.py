import threading
import logging

from ..core.config import FILE_SYSTEMS, DATA_BUCKET, CADAI_BUCKET

logging.root.setLevel(level=logging.INFO)


class Loader:
    def __init__(self):
        self._in_progress = True
        self._data_bucket = DATA_BUCKET
        self._cadai_bucket = CADAI_BUCKET
        self._fs = FILE_SYSTEMS['aws_s3']
        self._name = 'Loader'
        self._logger = logging.getLogger(self._name)

    def start(self):
        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):
        self._logger.warning("NOT IMPLEMENTED")
        pass
