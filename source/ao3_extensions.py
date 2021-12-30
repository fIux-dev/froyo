import AO3
import bs4
import logging
import requests
import urllib.parse

from math import ceil

from bs4 import BeautifulSoup
from typing import Optional, List

from AO3 import threadable
from AO3.common import get_work_from_banner
from AO3.requester import requester
from AO3.series import Series
from AO3.users import User
from AO3.works import Work

from . import constants, utils

LOG = logging.getLogger(__name__)


def get_ao3_url(url: str, page: Optional[int] = None) -> Optional[str]:
    """GIven an AO3 URL listing works that can span multiple pages, return the
    URL of the specified page.

    Returns None if the URL was not an AO3 URL.
    """
    url_parts = urllib.parse.urlparse(url)
    if url_parts.netloc != constants.AO3_DOMAIN:
        return None

    query_dict = urllib.parse.parse_qs(url_parts.query, keep_blank_values=True)
    if page is None:
        if "page" in query_dict:
            del query_dict["page"]
    else:
        query_dict["page"] = [str(page)]
    new_query_string = utils.get_query_string(query_dict)
    url_parts = url_parts._replace(query=new_query_string)
    return urllib.parse.urlunparse(url_parts)


class Results:
    url: str
    page_start: int = 1
    page_end: int = 0
    session: Optional[requests.Session] = None
    pages: int = 0

    def __init__(
        self,
        url: str,
        page_start: int = 1,
        page_end: int = 0,
        session: Optional[requests.Session] = None,
    ):
        self.url = url
        self.page_start = page_start
        self.page_end = page_end

        self.session = session
        self.pages = 0

    @threadable.threadable
    def update(self) -> None:
        """Sends a request to the AO3 website with the defined search parameters, 
        and updates all info. This function is threadable.
        """
        soup = _get(self.url, self.session)

        # Try and find the pages navigation bar at the bottom of a results page
        # The very last element is the Next -> arrow. The second last item should be
        # the total number of pages. If we can't find it, assume there's only one
        # page of results.
        try:
            pagination_element = soup.find("ol", {"role": "navigation"})
            if not isinstance(pagination_element, bs4.element.Tag):
                self.pages = 1
                return

            self.pages = int(pagination_element.find_all("li")[-2].get_text())
            if self.page_end == 0:
                self.page_end = self.pages
        except Exception as e:
            LOG.warning(
                f"Got exception trying to find number of pages for "
                f"`{self.url}`: {e}. Assuming number of pages is 1."
            )
            self.pages = 1


class ResultsPage:
    url: str
    page: int
    session: Optional[requests.Session] = None
    work_ids: List[int] = []

    def __init__(self, url: str, page: int, session: Optional[requests.Session] = None):
        self.url = url
        self.session = session
        self.page = page
        self.work_ids = []

    @threadable.threadable
    def update(self) -> None:
        """Sends a request to the AO3 website with the defined search parameters, 
        and updates all info. This function is threadable.
        """
        url = get_ao3_url(self.url, self.page)
        if url is None:
            return

        soup = _get(url, self.session)

        results = soup.find("ol", {"class": ("work", "index", "group")})
        if not isinstance(results, bs4.element.Tag):
            LOG.warning(
                f"Could not find works element on page: `{url}`. No works IDs "
                f"will be returned."
            )
            return

        work_ids = []
        for work in results.find_all("li", {"role": "article"}):
            if work.h4 is None:
                continue
            work_id = work.get("id", None)
            if work_id is None:
                continue
            work_ids.append(int(work_id.lstrip("work_")))

        self.work_ids = work_ids


def _get(url: str, session: Optional[requests.Session] = None) -> bs4.BeautifulSoup:
    """Returns the page for the search as a Soup object
    Args:
        url (str): Generic AO3 URL.
    Returns:
        bs4.BeautifulSoup: Search result's soup
    """

    if session is None:
        req = requester.request("get", url)
    else:
        req = session.get(url)
    if req.status_code == 429:
        raise AO3.utils.HTTPError(
            "We are being rate-limited. Try again in a while or reduce the "
            "number of requests."
        )
    soup = BeautifulSoup(req.content, features="lxml")
    return soup
