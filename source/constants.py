AO3_DOMAIN = "archiveofourown.org"
VALID_FILETYPES = {"AZW3", "EPUB", "HTML", "MOBI", "PDF"}
AO3_SORT_BY = {
    "Author": "authors_to_sort_on",
    "Title": "title_to_sort_on",
    "Date Posted": "created_at",
    "Date Update": "revised_at",
    "Word Count": "word_count",
    "Hits": "hits",
    "Kudos": "kudos_count",
    "Comments": "comments_count",
    "Bookmarks": "bookmarks_count",
}
AO3_TAG_FIELDS = (
    "warnings",
    "categories",
    "fandoms",
    "characters",
    "relationships",
    "additional_tags",
)
AO3_RATINGS = {
    "Not Rated": 9,
    "General Audiences": 10,
    "Teen And Up Audiences": 11,
    "Mature": 12,
    "Explicit": 13,
}
AO3_WARNINGS = {
    "Creator Chose Not To Use Archive Warnings": 14,
    "No Archive Warnings Apply": 16,
    "Graphic Depictions Of Violence": 17,
    "Major Character Death": 18,
    "Rape/Non-Con": 19,
    "Underage": 20,
}
AO3_CATEGORIES = {
    "Gen": 21,
    "F/M": 22,
    "M/M": 23,
    "F/F": 116,
    "Multi": 2246,
    "Other": 24,
}
AO3_CROSSOVER_OPTIONS = [
    "Include crossovers",
    "Exclude crossovers",
    "Show only crossovers",
]

DATA_DIR = "data"
BOOKMARKS_DIR = "bookmarks"

DEFAULT_DOWNLOADS_DIR = "Downloads/froyo"
DEFAULT_DOWNLOADS_FILETYPE = "PDF"
DEFAULT_CONCURRENCY_LIMIT = 20

INITIAL_SECONDS_BEFORE_RETRY = 10

LOG_FILE = "log.txt"
CONFIGURATION_FILE = "settings.ini"

CONFIGURATION_FILE_TEMPLATE = """; froyo config file
;
; Please only edit manually if you know what you're doing. Otherwise, prefer
; to configure settings using the GUI instead.
;
; Lines beginning with the `;` character indicate a comment and will not be
; processed.

[credentials]
; This section controls settings for AO3 authentication.
; If no username and password is specified in this section, the tool will run
; in guest mode.
;
; Some AO3 features are not available while browsing in guest mode. If you would
; like to login and access bookmarks, etc. you can specify your credentials for
; AO3 in this section.
username={}
password={}

[downloads]
; This section controls settings for downloads. By default, files will be 
; downloaded to the 'downloads' folder in the same file as the tool.
; Valid choices for filetype include: AZW3, EPUB, HTML, MOBI, PDF
directory={}
filetype={}

[engine]
; This section controls settings for how the tool behaves.
; Threading enables multiple downloads to occur concurrently in different CPU
; threads. This will make bulk downloading a lot faster. The concurrency limit
; controls how many simultaneous requests can be running at the same time.
; Rate limiting will limit the number of requests to AO3 to 12 per minute.
should_use_threading={}
concurrency_limit={}
should_rate_limit={}
"""
