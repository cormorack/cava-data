import concurrent.futures
import threading
import logging
from .store import DATASETS_STORE
from .models import XRDataset

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

# TODO: Grab straight from s3 using listdir.
URLS = [
    "s3://io2data-test/data/CE02SHBP-LJ01D-06-CTDBPN106-streamed-ctdbp_no_sample",
    "s3://io2data-test/data/CE02SHBP-LJ01D-09-PCO2WB103-streamed-pco2w_b_sami_data_record",
    "s3://io2data-test/data/CE02SHBP-LJ01D-10-PHSEND103-streamed-phsen_data_record",
    "s3://io2data-test/data/CE04OSBP-LJ01C-06-CTDBPO108-streamed-ctdbp_no_sample",
    "s3://io2data-test/data/CE04OSBP-LJ01C-09-PCO2WB104-streamed-pco2w_b_sami_data_record",
    "s3://io2data-test/data/CE04OSBP-LJ01C-10-PHSEND107-streamed-phsen_data_record",
    "s3://io2data-test/data/CE04OSPD-DP01B-01-CTDPFL105-recovered_inst-dpc_ctd_instrument_recovered",
    "s3://io2data-test/data/CE04OSPD-DP01B-03-FLCDRA103-recovered_inst-dpc_flcdrtd_instrument_recovered",
    "s3://io2data-test/data/CE04OSPD-DP01B-04-FLNTUA103-recovered_inst-dpc_flnturtd_instrument_recovered",
    "s3://io2data-test/data/CE04OSPD-DP01B-06-DOSTAD105-recovered_inst-dpc_optode_instrument_recovered",
    "s3://io2data-test/data/CE04OSPS-PC01B-4A-CTDPFA109-streamed-ctdpf_optode_sample",
    "s3://io2data-test/data/CE04OSPS-PC01B-4B-PHSENA106-streamed-phsen_data_record",
    "s3://io2data-test/data/CE04OSPS-PC01B-4D-PCO2WA105-streamed-pco2w_a_sami_data_record",
    "s3://io2data-test/data/CE04OSPS-SF01B-2A-CTDPFA107-streamed-ctdpf_sbe43_sample",
    "s3://io2data-test/data/CE04OSPS-SF01B-2B-PHSENA108-streamed-phsen_data_record",
    "s3://io2data-test/data/CE04OSPS-SF01B-3A-FLORTD104-streamed-flort_d_data_record",
    "s3://io2data-test/data/CE04OSPS-SF01B-3C-PARADA102-streamed-parad_sa_sample",
    "s3://io2data-test/data/CE04OSPS-SF01B-4A-NUTNRA102-streamed-nutnr_a_sample",
    "s3://io2data-test/data/CE04OSPS-SF01B-4F-PCO2WA102-streamed-pco2w_a_sami_data_record",
    "s3://io2data-test/data/RS01SBPD-DP01A-01-CTDPFL104-recovered_inst-dpc_ctd_instrument_recovered",
    "s3://io2data-test/data/RS01SBPD-DP01A-03-FLCDRA102-recovered_inst-dpc_flcdrtd_instrument_recovered",
    "s3://io2data-test/data/RS01SBPD-DP01A-04-FLNTUA102-recovered_inst-dpc_flnturtd_instrument_recovered",
    "s3://io2data-test/data/RS01SBPD-DP01A-06-DOSTAD104-recovered_inst-dpc_optode_instrument_recovered",
    "s3://io2data-test/data/RS01SBPS-PC01A-4A-CTDPFA103-streamed-ctdpf_optode_sample",
    "s3://io2data-test/data/RS01SBPS-PC01A-4B-PHSENA102-streamed-phsen_data_record",
    "s3://io2data-test/data/RS01SBPS-PC01A-4C-FLORDD103-streamed-flort_d_data_record",
    "s3://io2data-test/data/RS01SBPS-SF01A-2A-CTDPFA102-streamed-ctdpf_sbe43_sample",
    "s3://io2data-test/data/RS01SBPS-SF01A-2D-PHSENA101-streamed-phsen_data_record",
    "s3://io2data-test/data/RS01SBPS-SF01A-3A-FLORTD101-streamed-flort_d_data_record",
    "s3://io2data-test/data/RS01SBPS-SF01A-3C-PARADA101-streamed-parad_sa_sample",
    "s3://io2data-test/data/RS01SBPS-SF01A-4A-NUTNRA101-streamed-nutnr_a_sample",
    "s3://io2data-test/data/RS01SBPS-SF01A-4F-PCO2WA101-streamed-pco2w_a_sami_data_record",
    "s3://io2data-test/data/RS01SLBS-LJ01A-12-CTDPFB101-streamed-ctdpf_optode_sample",
    "s3://io2data-test/data/RS03ASHS-MJ03B-10-CTDPFB304-streamed-ctdpf_optode_sample",
    "s3://io2data-test/data/RS03AXBS-LJ03A-12-CTDPFB301-streamed-ctdpf_optode_sample",
    "s3://io2data-test/data/RS03AXPD-DP03A-01-CTDPFL304-recovered_inst-dpc_ctd_instrument_recovered",
    "s3://io2data-test/data/RS03AXPD-DP03A-03-FLCDRA302-recovered_inst-dpc_flcdrtd_instrument_recovered",
    "s3://io2data-test/data/RS03AXPD-DP03A-03-FLNTUA302-recovered_inst-dpc_flnturtd_instrument_recovered",
    "s3://io2data-test/data/RS03AXPD-DP03A-06-DOSTAD304-recovered_inst-dpc_optode_instrument_recovered",
    "s3://io2data-test/data/RS03AXPS-PC03A-4A-CTDPFA303-streamed-ctdpf_optode_sample",
    "s3://io2data-test/data/RS03AXPS-PC03A-4B-PHSENA302-streamed-phsen_data_record",
    "s3://io2data-test/data/RS03AXPS-PC03A-4C-FLORDD303-streamed-flort_d_data_record",
    "s3://io2data-test/data/RS03AXPS-SF03A-2A-CTDPFA302-streamed-ctdpf_sbe43_sample",
    "s3://io2data-test/data/RS03AXPS-SF03A-2D-PHSENA301-streamed-phsen_data_record",
    "s3://io2data-test/data/RS03AXPS-SF03A-3A-FLORTD301-streamed-flort_d_data_record",
    "s3://io2data-test/data/RS03AXPS-SF03A-3C-PARADA301-streamed-parad_sa_sample",
    "s3://io2data-test/data/RS03AXPS-SF03A-4A-NUTNRA301-streamed-nutnr_a_sample",
    "s3://io2data-test/data/RS03AXPS-SF03A-4F-PCO2WA301-streamed-pco2w_a_sami_data_record",
]


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
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # Start the load operations and mark each future with its URL
                future_to_url = {
                    executor.submit(self.load_dataset, url): url
                    for url in self._urls
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
            logger.info(f"Loading: {url}")
            xrd = XRDataset(url, mounted=True)
            xrd.set_ds()
            DATASETS_STORE[xrd.dataset_id] = xrd
            self._app.mount(f"/{xrd.dataset_id}", DATASETS_STORE[xrd.dataset_id].app)
        except Exception as e:
            logger.warning(e)
            logger.info(f"Skipping: {url}")
