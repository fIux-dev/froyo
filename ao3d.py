import AO3
import logging
import os
import time

from source import constants, gui as gui_module
from source.engine import Engine
from source.gui import GUI

LOG = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s [%(name)s] [%(threadName)s] [%(levelname)s] %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S%p",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(constants.LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def main() -> None:
    LOG.info("Starting...")
    try:
        engine = Engine(os.getcwd())
        gui = GUI(engine)
        gui.run()
    except AO3.utils.HTTPError:
        LOG.error("Hit rate limiting error. Please try again later.")
        gui_module.display_rate_limiting_error()
        exit(1)


if __name__ == "__main__":
    main()
