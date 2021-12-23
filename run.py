#!/usr/bin/env python3

import logging
import os

from source import constants

from source.engine import Engine

LOG = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s [%(name)s] [%(threadName)s] [%(levelname)s] %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S%p",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(constants.LOG_FILE, mode="w"),
        logging.StreamHandler(),
    ],
)


def main() -> None:
    engine = Engine(os.getcwd())
    engine.run()


if __name__ == "__main__":
    main()
