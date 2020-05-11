import concurrent.futures
import threading
import logging
from .core.config import FILE_SYSTEMS
from .store import DATASETS_STORE
from .models import XRDataset

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

DATA_BUCKET = 'ooi-data'
FS = FILE_SYSTEMS['aws_s3']

# TODO: Grab straight from s3 using listdir.
URLS = list(
    filter(
        lambda zg: zg != 'data_availability',
        FS.listdir(DATA_BUCKET, detail=False),
    )
)


class LoadDatasets:
    """ Threading example class
    The run() method will be started and it will run in the background
    until the application exits.
    """

    def __init__(self, app):
        """ Constructor
        :type interval: int
        :param interval: Check interval, in seconds
        """
        self._app = app
        self._urls = URLS
        self._in_progress = True

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):
        """ Method that runs forever """
        while self._in_progress:
            logger.info("Datasets loading...")
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=10
            ) as executor:
                # Start the load operations and mark each future with its URL
                future_to_url = {
                    executor.submit(self.load_dataset, url): url
                    for url in self._urls[:20]
                }
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    data = future.result()
                    if data:
                        logger.info(f"{url} loaded.")

            self._in_progress = False
            logger.info("Datasets loaded.")

    def load_dataset(self, url):
        try:
            xrd = XRDataset(url, mounted=True)
            xrd.set_ds()
            DATASETS_STORE[xrd.dataset_id] = xrd
            self._app.mount(
                f"/{xrd.dataset_id}", DATASETS_STORE[xrd.dataset_id].app
            )
            logger.info(f"Loaded: {url}")
        except Exception as e:
            logger.warning(e)
            logger.info(f"Skipping: {url}")
