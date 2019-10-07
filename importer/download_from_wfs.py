#!/usr/bin/env python3
import requests
import subprocess
import yaml
import time
import json
import os
from math import ceil
import argparse
from datetime import datetime
import xml.etree.ElementTree as ET
import logging


def logger():
    """
    Setup basic logging for console.

    Usage:
        Initialize the logger by adding the code at the top of your script:
        ``logger = logger()``

    TODO: add log file export
    """
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S')
    logger = logging.getLogger(__name__)
    return logger


logger = logger()


class NonZeroReturnCode(Exception):
    """Used for subprocess error messages."""
    pass


def scrub(line):
    """Hide the login credentials of Postgres in the console."""
    out = []
    for x in line:
        if x.strip().startswith('PG:'):
            out.append('PG: <CONNECTION STRING REDACTED>')
        else:
            out.append(x)
    return out


def psycopg_connection_string(docker_compose_path="docker-compose.yml"):
    """
    Postgres connection string for psycopg2.

    Args:
      full docker-compose path file

    Returns:
        Returns the psycopg required connection string: 'PG:host= port= user= dbname= password='
    """

    config = yaml.load(open(docker_compose_path), Loader=yaml.SafeLoader)
    env = config["services"]["importer"]["environment"]

    pg_config = 'host={} port={} user={} dbname={} password={}'.format(
            env['DATABASE_HOST'],
            os.getenv('DATABASE_PORT', env['DATABASE_PORT']),
            env['DATABASE_USER'],
            env['DATABASE_NAME'],
            env['DATABASE_PASSWORD']
        )
    # logger.info("pg_string obtained from {}".format(docker_compose_path))
    return pg_config


def run_command_sync(cmd, allow_fail=False):
    """
    Run a string in the command line.

    Args:
        1. cmd: command line code formatted as a list::

            ['ogr2ogr', '-overwrite', '-t_srs', 'EPSG:28992','-nln',layer_name,'-F' ,'PostgreSQL' ,pg_str ,url]

        2. Optional: allow_fail: True or false to return error code

    Returns:
        Excuted program or error message.
    """
    # logger.info('Running %s', scrub(cmd))
    p = subprocess.Popen(cmd)
    p.wait()

    if p.returncode != 0 and not allow_fail:
        raise NonZeroReturnCode

    return p.returncode


def wfs_filter(filter_properties):
    """
    Add a key,value as a literal string to return a filter statement for a WFS request.
    """
    if filter_properties:
        key, value = filter_properties[0].split(',')
        filter_xml = "<Filter><PropertyIsEqualTo><PropertyName>{}</PropertyName><Literal>{}</Literal></PropertyIsEqualTo></Filter>".format(key, value)
    else:
        filter_xml = None
    return filter_xml


def get_number_of_features(url_wfs, layer_name, filter_properties):
    """
    Get total features to shift startindex number to retrieve all features
    """
    parameters = {
        "REQUEST": "GetFeature",
        "TYPENAME": layer_name,
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "FILTER": wfs_filter(filter_properties),
        "RESULTTYPE": "hits"
    }
    logger.info("Requesting number of features from {}, layer: {}".format(
        url_wfs, layer_name))
    request_number_of_features = requests.get(url_wfs, params=parameters)
    root = ET.fromstring(request_number_of_features.text)
    number_of_features = root.attrib['numberMatched']
    logger.info("Total of {} features in layer: {}".format(number_of_features, layer_name))
    return int(number_of_features)


def get_layers_from_wfs(url_wfs):
    """
        Get all layer names in WFS service, print and return them in a list.
    """
    layer_names = []
    parameters = {
        "REQUEST": "GetCapabilities",
        "SERVICE": "WFS"
    }

    getcapabilities = requests.get(url_wfs, params=parameters)
    # print(getcapabilities.text)
    root = ET.fromstring(getcapabilities.text)

    for neighbor in root.iter('{http://www.opengis.net/wfs/2.0}FeatureType'):
        # neighbor[0]==name, neighbor[1]==title
        logger.info("layername: " + neighbor[1].text)
        layer_names.append(neighbor[1].text)
    return layer_names


def get_layer_from_wfs(url_wfs, layer_name, srs, filter_properties, startindex, outputformat, retry_count=3):
    """
    Get layer from a wfs service.
    Args:
        1. url_wfs: full url of the WFS including https, excluding /?::

            https://map.data.amsterdam.nl/maps/gebieden

        2. layer_name: Title of the layer::

            stadsdeel

        3. srs: coordinate system number, excluding EPSG::

            28992

        4. filter_properties: key, value pair as a literal string, for example bag:woonplaats,Amsterdam
        
        5. outputformat: leave empty to return standard GML,
           else define json, geojson, txt, shapezip::

            geojson
        
        6. startindex: index of feature, starting at 0
        
    Returns:
        The layer in the specified output format.
    """  # noqa

    parameters = {
        "REQUEST": "GetFeature",
        "TYPENAME": layer_name,
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "SRSNAME": "EPSG:{}".format(srs),
        "FILTER": wfs_filter(filter_properties),
        "STARTINDEX": startindex,
        "OUTPUTFORMAT": outputformat
    }

    logger.debug("Requesting data from {}, layer: {}".format(
        url_wfs, layer_name))

    retry = 0

    # webrequests sometimes fail..
    while retry < retry_count:
        response = requests.get(url_wfs, params=parameters)
        logger.debug(url_wfs, parameters)
        logger.debug(response)
        if response.status_code == 400:
            logger.info("Wrongly formed WFS, please correct fields described in error message:\n{}".format(response.content))
            continue
        if response.status_code != 200:
            time.sleep(3)
            # try again..
            retry += 1
        else:
            # status 200. succes.
            break
    if outputformat in ('geojson, json'):
        geojson = response.json()
        # max_features = len(geojson["features"])
        # logger.info("{} features returned.".format(str(max_features)))
        return geojson
    return response


def load_geojson_to_postgres(full_path, layer_name, srs, docker_compose_path, overwrite_append):
    """
    Get a geojson and load it into postgres using ogr2ogr
    and the docker compose file is used to get the login environment fields.

    The Schema is default to public or must be created beforehand.
    """

    config = yaml.load(open(docker_compose_path), Loader=yaml.SafeLoader)
    env = config["services"]["importer"]["environment"]

    schema = os.getenv('DATABASE_SCHEMA', env['DATABASE_SCHEMA'])
    pg_str =psycopg_connection_string(docker_compose_path)
    if overwrite_append == '-append':
        cmd = [
            'ogr2ogr',
            overwrite_append,
            '-t_srs', "EPSG:{}".format(srs),
            '-nln', layer_name,
            '-lco', 'SCHEMA={}'.format(schema),
            '-F', 'PostgreSQL', 'PG:' + pg_str,
            full_path
        ]
    else:
        cmd = [
            'ogr2ogr',
            overwrite_append,
            '-t_srs', "EPSG:{}".format(srs),
            '-nln', layer_name,
            '-lco', 'SCHEMA={}'.format(schema),
            '-F', 'PostgreSQL', 'PG:' + pg_str,
            full_path
        ]
    run_command_sync(cmd)


def get_multiple_geojson_from_wfs(url_wfs, srs, layer_names, output_folder, output_format, docker_postgres, filter_properties):
    """
    Get all layers and save them as a geojson

    Args:
        1. url_wfs: full url of the WFS including https, excluding /?::

            https://map.data.amsterdam.nl/maps/gebieden

        2. layer_names: single or multiple titles of the layers, separated
           by a comma without spaces::

            stadsdeel,buurtcombinatie,gebiedsgerichtwerken,buurt

        3. srs: coordinate system number, excluding EPSG::

            28992

        4. output_folder: define the folder to save the files::

            path_to_folder/another_folder
    """
    layer_names = layer_names.split(',')

    for layer_name in layer_names:
        number_of_features = get_number_of_features(url_wfs, layer_name, filter_properties)
        geojson = get_layer_from_wfs(url_wfs, layer_name, srs, filter_properties, 0, output_format)
        features_per_page = len(geojson["features"])
        pages = ceil(number_of_features/features_per_page)
        page = 0
        counter = 0
        overwrite_append = '-overwrite'
        while page < pages:
            filename = "{}_{}_{}.geojson".format(layer_name, datetime.now().date(), page)
            full_path = os.path.join(output_folder, filename)
            startindex = page * features_per_page
            geojson = get_layer_from_wfs(url_wfs, layer_name, srs, filter_properties, startindex, output_format)
            with open(full_path, 'w') as outfile:
                json.dump(geojson, outfile)
            if docker_postgres:
                load_geojson_to_postgres(full_path, layer_name, srs, docker_postgres, overwrite_append)
            counter += len(geojson["features"])
            logger.info("{}%  done, {} of {} added".format(round(counter/number_of_features * 100, 1), counter, number_of_features))
            page += 1
            overwrite_append = '-append'


def parser():
    """Parser function to run arguments from the command line
    and to add description to sphinx."""

    parser = argparse.ArgumentParser(description="""
    Get multiple layers as a geojson file from a WFS service.
    command line example::

      download_from_wfs https://geodata.nationaalgeoregister.nl/bag/wfs ligplaats 28992 /data ../docker-compose.yml bag:woonplaats,Amsterdam 

    """)  # noqa

    parser.add_argument(
        "-u","--url_wfs",
        type=str,
        help="WFS url, for example http://map.data.amsterdam.nl/maps/gebieden")
    parser.add_argument(
        "-s", "--srs",
        type=str,
        default="28992",
        choices=["28992", "4326"],
        help="choose srs (default: %(default)s)")
    parser.add_argument(
        "-l",'--layer_names',
        type=str,
        nargs="+",
        help="Layers to export, separated by a , for example: stadsdeel,buurtcombinatie")  # noqa
    parser.add_argument(
        "-o", "--output_folder",
        type=str,
        help="Set the output location path, for example output or projectdir/data")  # noqa
    parser.add_argument(
        "-j", "--output_format",
        type=str,
        default="json",
        choices=["json", "geojson"],
        help="choose srs (default: %(default)s)")
    parser.add_argument(
        "-d", "--docker_config",
        type=str,
        default=None,
        help="Set the location of docker-compose path, for example ../docker-compose.yml")  # noqa
    parser.add_argument(
        "-f", "--filter_properties",
        type=str,
        default=None,
        nargs="*",
        help="set name of attribute and value to filter using key,value. For example: bag:woonplaats,Amsterdam")  # noqa

    return parser


def main():
    args = parser().parse_args()
    logger.info('Using %s', args)
    get_layers_from_wfs(args.url_wfs)
    get_multiple_geojson_from_wfs(
        args.url_wfs,
        args.srs,
        args.layer_names[0],
        args.output_folder,
        args.output_format,
        args.docker_config,
        args.filter_properties
    )


if __name__ == '__main__':
    main()
