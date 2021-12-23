# ao3d
Utility for downloading works from [AO3](https://archiveofourown.org/) (Archive Of Our Own)

## Installation
**Requirements**: [Python](https://www.python.org/) >= 3.8 (with the [pip](https://pypi.org/project/pip/) package manager), [Git](https://git-scm.com/)

1. Clone the repository.
```
$ git clone https://github.com/fIux-dev/ao3d.git
```
2. Go into the `ao3d` directory and install the required packages.
```
$ cd ao3d
$ pip install -r requirements.txt
```
3. Copy `settings.ini.example` to `settings.ini` in the `ao3d` directory, enter
your AO3 credentials and uncomment the lines (remove the semicolon at the start
of the lines) in the copied settings file:
```
[credentials]
username=<your AO3 username>
password=<your AO3 password>
```
4. Run.
```
$ python3 ao3d.py
```

## Usage
When run, ao3d will download all bookmarked works for the account. In addition, it will hash 
the chapters titles and texts on disk, so that the next time it is run, it will only attempt
to download works that have had their content changed since the last run.

By default, downloaded files will be in the `download` subdirectory in the `ao3d` directory,
and the default filetype for downloads is PDF. A custom download location and filetype can be 
specified in settings.ini.

ao3d saves all its data to the `data` subdirectory in the `ao3d` folder.

For more information about the configuration file (settings.ini), please read the comments in
that file.


## Features
* Mult-threaded downloading of bookmarks to supported formats (AZW3, EPUB, HTML, 
MOBI, PDF)

## Known issues
* Right now bookmarked series cannot be downloaded. A workaround is to bookmark each 
work in the series individually.

## License

[MIT](https://choosealicense.com/licenses/mit/)
