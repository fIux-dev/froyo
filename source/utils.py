import logging
import os
import subprocess

from pathlib import Path
from typing import Optional

LOG = logging.getLogger(__name__)


def open_file(filename: Path):
    """Attempt to open file with default system application. Cross-platform."""
    LOG.info(f"Trying to open {filename} in default system application...")
    try:
        os.startfile(str(filename))
    except AttributeError:
        subprocess.call(["open", str(filename)])


def series_id_from_url(url: str) -> Optional[int]:
    """Get the series ID from an archiveofourown.org website url
    Args:
        url (str): Series URL 
    Returns:
        int: Series ID
    """
    split_url = url.split("/")
    try:
        index = split_url.index("series")
    except ValueError:
        return
    if len(split_url) >= index + 1:
        series_id = split_url[index + 1].split("?")[0]
        if series_id.isdigit():
            return int(series_id)
    return
