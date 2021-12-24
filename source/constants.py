VALID_FILETYPES = {"AZW3", "EPUB", "HTML", "MOBI", "PDF"}

DATA_DIR = "data"
BOOKMARKS_DIR = "bookmarks"

DEFAULT_DOWNLOADS_DIR = "downloads"
DEFAULT_DOWNLOADS_FILETYPE = "PDF"
DEFAULT_CONCURRENCY_LIMIT = 20

LOG_FILE = "log.txt"
CONFIGURATION_FILE = "settings.ini"

CONFIGURATION_FILE_TEMPLATE = """
; ao3d config file example
;
; This is an example configuration file.
; Lines beginning with the `;` character indicate a comment and will not be
; processed.
; Please make a copy of this file as `settings.ini` and make your changes in
; the new file.

; If no username and password is specified in this section, the tool will run
; in guest mode.
;
; Some AO3 features are not available while browsing in guest mode. If you would
; like to login and access bookmarks, etc. you can specify your credentials for
; AO3 in this section.
[credentials]
username={}
password={}

; This section controls settings for downloads. By default, files will be 
; downloaded to the 'downloads' folder in the same file as the tool.
; Valid choices for filetype include: AZW3, EPUB, HTML, MOBI, PDF
[downloads]
directory={}
filetype={}

; This section controls settings for how the tool behaves.
; Threading enables multiple downloads to occur concurrently in different CPU
; threads. This will make bulk downloading a lot faster.
[engine]
should_use_threading={}
concurrency_limit={}
should_rate_limit={}
"""
