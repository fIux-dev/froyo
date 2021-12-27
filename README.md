# ao3d
<img src="https://user-images.githubusercontent.com/96564770/147402142-b44336ea-278f-49c3-83cc-9d97ad115688.png" alt="screenshot" width="600">

**[video preview (outdated)](https://imgur.com/a/mhInPfK)**

A small graphical application for batch downloading works from [Archive Of Our Own](https://archiveofourown.org/) (AO3)

### Features
* Batch downloading works to supported formats (AZW3, EPUB, HTML, 
MOBI, PDF)
* Download individual works by their URLs
* Download works in a series
* Download all bookmarks in your account (public and private)
* Download all works and (public) bookmarks from another user
* Supports multi-threaded requests and retrying after being rate limited


## Installation
**Requirements**: [Python](https://www.python.org/) >= 3.8 (with the [pip](https://pypi.org/project/pip/) package manager)

1. Clone the repository (or download the .ZIP).
```
$ git clone https://github.com/fIux-dev/ao3d.git
```
2. Go into the `ao3d` directory and install the required packages.
```
$ cd ao3d
$ pip install -r requirements.txt
```
3. Run.
```
$ python3 ao3d.py
```

## Usage
Please see the [video preview](https://imgur.com/a/mhInPfK) for an example of how to interact with the application.

It is not required to log in to download works, however some functionality may be restricted. Certain works may be 
restricted to logged-in users and cannot be viewed in a guest session. In addition, bookmarks can only be imported
when logged in.

It is advisable to keep browsing of AO3 through the browser to a minimum while using the application. This is because
rate limiting is shared across all your connections. If you are being rate limited in the application, you will also
see a "Retry later" message when trying to access AO3 in the browser.

### Settings

<img src="https://user-images.githubusercontent.com/96564770/147402186-7a79905a-74cc-4d03-870a-56aa44ff2059.png" alt="screenshot" width="600">

#### AO3 Login
A username and password can be entered in this section to authenticate with AO3. This will allow you to import
bookmarks from your account, as well as view restricted works that are only available to logged-in users.
It is not recommended to select "Remember me" on public computers.

#### Downloads
This section controls settings for the downloads. The directory the downloaded files will be saved to can be
specified here. By default, it should be the `Downloads` folder in your home directory. If you are logged in,
the downloads will appear in a subfolder with the same name as your AO3 username. A filetype for the downloads
can also be selected from the supported formats.

#### Engine
This section controls behaviors of the application itself. Allowing multithreading will give slightly more
responsive performance. The concurency limit sets the maximum number of parallel requests.

Rate limiting is not enabled by default, instead the application attempts to retry with a timeout in between
requests if a rate limit error occurs. If this is still insufficient for your use case, enabling rate limit will 
limit the number of requests to 12 per minute. This should prevent any rate limiting errors, which is useful if you
want to add e.g. an author or a series with a large number of works and will prevent those requests from failing.
However, this will slow down the application significantly.

### Troubleshooting
A `log.txt` file is generated in the same directory as the application when it is run. If you encounter any crashes 
or errors, please create an issue and attach this log file.

## Known issues
* A black screen is shown for a bit when the application first starts. This is due to font loading taking a while.
* Bookmarked series cannot be downloaded yet. A workaround is to bookmark each 
work in the series individually.
* Closing the application while requests are ongoing can take a while to respond.
* Ctrl+C through the command-line will not terminate the application cleanly. This may cause issues with the log
file not being written completely, etc.
* If you have a lot of bookmarks and/or works, the downloader will likely be rate limited by AO3. Right now, 
attempting to add works/bookmarks from a user or works from a series while you are being rate limited is fatal.
No works IDs will be added since this requires sending a request to AO3 to get the work list. If this is a problem,
please try selecting the use rate limiting option and leave the application open for a while.

## License

[MIT](https://choosealicense.com/licenses/mit/)
