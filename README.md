# ao3d
<img src="https://user-images.githubusercontent.com/96564770/147376353-47423c0c-55cd-4426-96fc-7acff20ed21b.png" alt="screenshot" width="600">

[video preview](https://imgur.com/a/mhInPfK)

A small graphical application for batch downloading works from [AO3](https://archiveofourown.org/) (Archive Of Our Own)

### Features
* Batch downloading works to supported formats (AZW3, EPUB, HTML, 
MOBI, PDF)
* Importing and downloading all bookmarks in an account


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

### Troubleshooting
A `log.txt` file is generated in the same directory as the application when it is run. If you encounter any crashes 
or errors, please create an issue and attach this log file.

## Known issues
* Bookmarked series cannot be downloaded yet. A workaround is to bookmark each 
work in the series individually.
* If you have a lot of bookmarks and/or works, the downloader will likely be rate limited by AO3. The application will
attempt to retry the request after 10 seconds, then 20, and so on, doubling the wait time each time until the request
succeeds. In theory, this means as long as you leave the application open, it should complete the requests eventually,
it might just take a while.
* Non-alphanumeric characters render as `?` right now due to the default font being used.
* Buttons cannot be clicked while load or download requests are ongoing. This is to prevent corruption of the internal
state due to multiple threads writing to the same containers.

## License

[MIT](https://choosealicense.com/licenses/mit/)
