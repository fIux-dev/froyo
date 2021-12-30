import AO3
import logging
import os
import sys
import time

from pathlib import Path

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


def _get_base_directory() -> Path:
    base_directory = None
    if getattr(sys, "frozen", False):
        base_directory = os.path.dirname(sys.executable)
    elif __file__:
        base_directory = os.path.dirname(__file__)
    return Path(base_directory)


def main() -> None:
    LOG.info("Starting...")
    engine = engine = Engine(_get_base_directory())
    gui = GUI(engine)
    gui.run()
    logging.shutdown()


if __name__ == "__main__":
    main()
