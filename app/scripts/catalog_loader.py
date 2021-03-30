import logging

import intake

from .baseloader import Loader
from ..core.config import settings
from ..store import CENTRAL_STORE

logging.root.setLevel(level=logging.INFO)
logger = logging.getLogger('uvicorn')


class LoadDataCatalog(Loader):
    """ Threading example class
    The run() method will be started and it will run in the background
    until the application exits.
    """

    def __init__(self):
        """ Constructor
        :type interval: int
        :param interval: Check interval, in seconds
        """
        Loader.__init__(self)
        self._name = "DataCatalogLoader"

        self.start()

    def run(self):
        """ Method that runs forever """
        while self._in_progress:
            logger.info("Data Catalog loading...")
            catalog = intake.open_catalog(settings.DATA_CATALOG_FILE)
            CENTRAL_STORE["intake_catalog"] = catalog
            logger.info("Dataset Catalog loaded.")
            self._in_progress = False
