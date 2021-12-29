# froyo
![demo](https://user-images.githubusercontent.com/96564770/147512988-590491d0-95ed-4a22-95fa-7f5b70ad39e5.gif)

A small graphical application for batch downloading works from [Archive Of Our Own](https://archiveofourown.org/) (AO3). 

Curate a **f**ic **r**epo **o**f **y**our **o**wn today :)

### Features
* Batch downloading works to supported formats (AZW3, EPUB, HTML, 
MOBI, PDF)
* Download individual works by their URLs
* Download works in a series
* Download all bookmarks in your account (public and private)
* Download all works and (public) bookmarks from another user
* Download works in any arbitrary AO3 search result, collection or tag
* Supports multi-threaded requests and retrying after being rate limited


## Installation

### Pre-compiled executable binaries
The latest binary releases can be found [here](https://github.com/fIux-dev/froyo/releases). Please download the appropriate
binary for your platform version, unzip the folder and run the executable. No installation is required.

### Running from source
If you are using another platform, you can run the application from source as 
long as Python is supported on your platform.

**Requirements**: [Python](https://www.python.org/) >= 3.8 (with the [pip](https://pypi.org/project/pip/) package manager)

1. Clone the repository (or download the .ZIP).
```
$ git clone https://github.com/fIux-dev/froyo.git
```
2. Go into the `froyo` directory and install the required packages.
```
$ cd froyo
$ pip install wheel
$ pip install -r requirements.txt
```
3. Run.
```
$ python3 froyo.py
```

### Building the binary for release
1. Peform the same first two steps in the above **Running from source** section.
2. Install PyInstaller.
```
$ pip install pyinstaller
```
2. Build the executable with PyInstaller. After running this step, there should be
a new folder generated named `dist/`. The binary will be inside this folder.
```
$ pyinstaller --noconsole --onefile froyo.py
```
3. Copy static resources to the distribution folder.
```
$ cp -r resources dist/resources
```
4. Now the `dist/` folder containing the binary is ready for distribution.

## Usage

### Downloading works, series, bookmarks
Please see the animated previews for an example of how to interact with the application.

It is not required to log in to download works, however some functionality may be restricted. Certain works may be 
restricted to logged-in users and cannot be viewed in a guest session. In addition, bookmarks can only be imported
when logged in.

### Downloading works from any AO3 listing
![generic2](https://user-images.githubusercontent.com/96564770/147620737-962799e6-580f-4565-975a-53ac2ca4ac50.gif)

To download all works in a tag, collection, or search result, use the `Add generic URL` button. You can simply
paste the URL listing the works in the field and select a page range to download. Use the range `1 to 0` to get
works in all pages of the listing.

**Note: Search appears to be rate limited a lot more aggressively than just accessing works by ID. It is highly 
recommended to turn on rate limiting if you are going to download multiple pages of results. Downloading a large number
of works is not tested, so you may run into issues.**

### Rate limiting

![retry](https://user-images.githubusercontent.com/96564770/147513133-33017c3a-a642-4b2a-98d1-34eb67acfe7c.gif)

If you are attempting to download a large number of works, you may be rate limited by AO3. The application will attempt
to retry requests that failed due to rate limiting, however, if you find that you are still getting errors trying
to load series or users, you can try enabling the rate limit option in settings.

It is advisable to keep browsing of AO3 through the browser to a minimum while using the application. This is because
rate limiting is shared across all your connections. If you are being rate limited in the application, you will also
see a "Retry later" message when trying to access AO3 in the browser.

### Settings

![image](https://user-images.githubusercontent.com/96564770/147513187-614338a3-23f4-400a-9dda-bd3a539d9b46.png)

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
responsive performance. The concurency limit sets the maximum number of parallel worker threads.

Rate limiting is not enabled by default, instead the application attempts to retry with a timeout in between
requests if a rate limit error occurs. If you are attempting to download all works or bookmarks from a user or
series and the number of works is very large, it is recommended to turn on rate limiting. This will limit the number
of requests to 12 per minute, and will slow down the speed of the application significantly, but should prevent
any issues with being able to load users or series.

### Troubleshooting
A `log.txt` file is generated in the same directory as the application when it is run. If you encounter any crashes 
or errors, please create an issue and attach this log file.

## Known issues
* A black screen is shown for a bit when the application first starts. This is due to font loading taking a while.
* Bookmarked series cannot be downloaded yet. A workaround is to bookmark each work in the series individually.
* Currently it is not possible to cancel loading bookmarks, series, user works, user bookmarks, generic URL pages
until the individual works are loaded. A workaround is to restart the application.
* If you have saved a login in your settings file, and you are currently being rate limited by AO3, you will not
be able to start up the application and will see a message about rate limiting. A workaround is to clear your
login information in `settings.ini`.
* Clicking `Download all` while bookmarks, series, collections, etc. are loading will not download the individual
works in them. At least the individual work IDs must be loaded for the download to be queued.
* Closing the application while requests are ongoing can take a while to respond, in order to terminate all
background threads cleanly. If rate limiting is enabled, closing the application will take even longer and may
appear to freeze as it is shutting down.
* `Ctrl + C` through the command-line will not terminate the application cleanly. This may cause issues with the log
file not being written completely, etc.
* If you have a lot of bookmarks and/or works, the downloader will likely be rate limited by AO3. Right now, 
attempting to add works/bookmarks from a user or works from a series can potentially fail if the list is very large.
This is because even if the request is retried, we may be rate limited trying to fetch the entire list again on retry. 
The workaround is to enable the rate limiting flag in the settings. Alternatively, you can attempt to submit the page
as a generic URL instead to have individual retry attempts per page.
* Enabling rate limiting is pretty buggy, you may see some unexpected errors like `pop from empty list`. These 
originate from the AO3 API's `requester` module and show up when rate limiting occurs. Please attempt to retry the 
download when the work appears to be loaded.

## License

[MIT](https://choosealicense.com/licenses/mit/)
