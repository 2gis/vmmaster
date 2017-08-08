# vmmaster
[![Build Status](https://travis-ci.org/2gis/vmmaster.svg?branch=master)](https://travis-ci.org/2gis/vmmaster)
[![Coverage](https://codecov.io/github/2gis/vmmaster/coverage.svg?branch=master)](https://codecov.io/github/2gis/vmmaster?branch=master)

## Dependencies:
+ python 2.7 only
+ tox
+ postgresql

## How to use?
### Run application

+ install dependencies:
```bash
./install_dependencies.sh
sudo pip install tox
tox -e base
```
+ create base config:
```bash
cp ./config_template.py config.py
```

+ migrations and run:
```bash
.tox/bin/python manage.py migrations
.tox/bin/python manage.py runserver
```

### Run in docker container

+ image build:
```bash
docker build --tag=<image_name>:<image_version> .
```

+ create enviroment variables file or put environment variables in docker run command

+ run migrations:
```bash
docker run -it --rm --volume /var/run/docker.sock:/var/run/docker.sock --privileged --net=host <image_name>:<images_version> python manage.py migrations
```

+ run container:
```bash
docker run -it --rm --volume /var/run/docker.sock:/var/run/docker.sock --privileged --net=host <image_name>:<images_version> python manage.py runserver
```

## Development

### Environment
```bash
./install-hooks.sh
```

### Linting
```bash
.tox/bin/flake8 vmmaster/ tests/
```


### Unittests with coverage
```bash
tox -e unit-with-coverage
```
Open coverage/index.html in web browser.


## Documentation
More [information](http://vmmaster.readthedocs.org)
