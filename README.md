# Zip codes with City of Amsterdam Areas

[![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/) [![MPL 2.0](https://img.shields.io/badge/license-MPLv2.0-blue.svg)](https://www.mozilla.org/en-US/MPL/2.0/)

This docker creates a zip code table in Postgres with the different Amsterdam areas using their names and code identifiers which is used for example in this Tableau area map boilerplate:
https://github.com/Amsterdam/tableau-desktop-repository

The importer downloads the national INSPIRE address web feature service (WFS) and the City of Amsterdam Area WFS service:
- https://geodata.nationaalgeoregister.nl/inspireadressen/wfs
- https://map.data.amsterdam.nl/maps/gebieden

## How to run
```
git clone https://github.com/amsterdam/zip_codes_with_amsterdam_areas.git
cd zip_codes_with_amsterdam_areas
docker-compose up -d database
docker-compose build importer
docker-compose up importer
```

You can login into the database using localhost:5444 and the username and password used in the docker-compose.yml

## How to run locally

### Create and login to a virtual environment and install packages
```
virtualenv --python=$(which python3) venv
source venv/bin/activate
pip install -r requirements.txt
```
### Start the database in a docker and run import script
```
docker-compose up -d database
cd importer
./import-dev.sh
```
