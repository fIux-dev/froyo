# ao3d
Utility for downloading works from [AO3](https://archiveofourown.org/) (Archive Of Our Own)

## Installation
**Requirements**: [Python](https://www.python.org/) >= 3.8 (with the [pip](https://pypi.org/project/pip/) package manager), (Git)[https://git-scm.com/]

1. Clone the repository.
```
$ git clone https://github.com/fIux-dev/ao3d.git
```
2. Go into the tool directory and install the required packages.
```
$ cd ao3d
$ pip install -r requirements.txt
```
3. Copy `settings.ini.example` to `settings.ini` in the tool directory, enter
your AO3 credentials and uncomment the lines (remove the semicolon at the start
of the lines) in the copied settings file:
```
[credentials]
username=<your AO3 username>
password=<your AO3 password>
```
4. Run.
```
$ python ao3d.py
```

## Features
* Mult-threaded downloading of bookmarks to supported formats (AZW3, EPUB, HTML, 
MOBI, PDF)

## License

[MIT](https://choosealicense.com/licenses/mit/)