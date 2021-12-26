VALID_FILETYPES = {"AZW3", "EPUB", "HTML", "MOBI", "PDF"}

DATA_DIR = "data"
BOOKMARKS_DIR = "bookmarks"

DEFAULT_DOWNLOADS_DIR = "Downloads/ao3d"
DEFAULT_DOWNLOADS_FILETYPE = "PDF"
DEFAULT_CONCURRENCY_LIMIT = 20

INITIAL_WAIT_TIME_IN_SECONDS = 10

LOG_FILE = "log.txt"
CONFIGURATION_FILE = "settings.ini"

CONFIGURATION_FILE_TEMPLATE = """; ao3d config file
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
; threads. This will make bulk downloading a lot faster.
should_use_threading={}
concurrency_limit={}
should_rate_limit={}
"""
