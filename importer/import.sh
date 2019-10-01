-#!/usr/bin/env bash

set -u   # crash on missing env variables
set -e   # stop on any error

# Download all bag data from the Netherlands from a prepared postgres db (takes 2 hours):
# curl "https://data.nlextract.nl/bag/postgis/bag-laatst.backup" --output /data/bag-laatst.backup
# pg_restore --no-owner --no-privileges -d bag /data/bag-laatst.backup

# This contains also panden, but was too slow (1000 per page)
#python download_from_wfs.py -u https://geodata.nationaalgeoregister.nl/bag/wfs -s 28992 -l ligplaats,standplaats,verblijfsobject -o /data -d ../docker-compose-nlextract.yml -f bag:woonplaats,Amsterdam

# Download address coordinates of Amsterdam (15.000 per page request)
python download_from_wfs.py -u https://geodata.nationaalgeoregister.nl/inspireadressen/wfs -s 28992 -l inspireadressen -o /data -j json -d docker-compose.yml  -p 1 -f inspireadressen:woonplaats,Amsterdam

# Download all areas
python download_from_wfs.py -u https://map.data.amsterdam.nl/maps/gebieden -s 28992 -l stadsdeel,gebiedsgerichtwerken,buurtcombinatie,buurt -o /data -j geojson  -p 1 -d docker-compose.yml

# Merge geopoint of zip codes and join area names and codes on each zip code with lat lon
python run_sql.py -s zip_codes_with_areas.sql -d docker-compose.yml -p 1