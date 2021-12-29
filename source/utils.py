import AO3
import logging
import os
import requests
import subprocess
import urllib.parse

from pathlib import Path
from typing import Dict, List, Optional

LOG = logging.getLogger(__name__)


def open_file(filename: Path) -> None:
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
    return None


def does_user_exist(username: str, session: requests.Session) -> bool:
    """Checks that the user is a valid AO3 user.
    Args:
        username (str): Username to check
    Returns:
        bool: True if the user exists, false otherwise
    Raises:
        AO3.utils.HttpError: If error code 429 was returned
    """
    # TODO: make this more robust
    # This is a hack to check whether the user exists or not. We rely on the
    # behavior that if the user doesn't exist, the profile page will redirect
    # to the homepage.
    profile_url = f"https://archiveofourown.org/users/{username}/profile"
    request = AO3.requester.requester.request(
        "head", profile_url, session=session, allow_redirects=False
    )
    if request.status_code == 429:
        raise AO3.utils.HTTPError(
            "We are being rate-limited. Try again in a while or reduce the "
            "number of requests."
        )
    elif request.status_code == 200:
        return True
    return False


def get_query_string(query_dict: Dict[str, List[str]], sep="&", quote=True) -> str:
    """Returns a joined query string for the (key, values) supplied.

    This supports multiple values for the same key.
    """
    query_string = sep.join(
        sep.join(
            f"{urllib.parse.quote_plus(str(key)) if quote else str(key)}={urllib.parse.quote_plus(str(value)) if quote else str(value)}"
            for value in query_dict[key]
        )
        for key in query_dict
    )
    return query_string
